"""DataUpdateCoordinator for the PC Remote integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnectError, InvalidAuthError, PcRemoteClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# After a power action, assume the expected state for this many seconds
# before trusting polled data again. PC takes time to sleep/wake.
POWER_HOLD_SECONDS = 60

STEAM_GAMES_STORAGE_VERSION = 1


SELECTIONS_STORAGE_VERSION = 1


@dataclass
class PcRemoteData:
    """Data returned by the coordinator."""

    online: bool = False
    machine_name: str = ""
    service_version: str = ""
    audio_devices: list[dict] = field(default_factory=list)
    current_audio_device: str | None = None
    volume: int | None = None
    monitors: list[dict] = field(default_factory=list)
    apps: list[dict] = field(default_factory=list)
    steam_games: list[dict] = field(default_factory=list)
    steam_running: dict | None = None
    modes: list[str] = field(default_factory=list)
    current_mode: str | None = None
    idle_seconds: int | None = None
    steam_bindings: dict | None = None
    steam_ready: bool | None = None
    auto_sleep_minutes: int | None = None


class PcRemoteCoordinator(DataUpdateCoordinator[PcRemoteData]):
    """Coordinator that polls the PC Remote service."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PcRemoteClient,
        entry_id: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._power_override: tuple[bool, float] | None = None
        self._steam_games_store: Store = Store(
            hass,
            STEAM_GAMES_STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}.steam_games",
        )
        self._cached_steam_games: list[dict] = []
        self._selections_store: Store = Store(
            hass,
            SELECTIONS_STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}.selections",
        )
        self._prev_audio_device: str | None = None

    async def async_load_steam_cache(self) -> None:
        """Load persisted Steam game list from storage. Call before first refresh."""
        stored = await self._steam_games_store.async_load()
        if isinstance(stored, list):
            self._cached_steam_games = stored
            _LOGGER.debug("Loaded %d Steam games from cache", len(stored))

    async def load_selections(self) -> dict:
        """Load persisted selections from storage."""
        stored = await self._selections_store.async_load()
        if isinstance(stored, dict):
            _LOGGER.debug("Loaded selections from cache: %s", stored)
            return stored
        return {}

    async def persist_selection(self, key: str, value: str | None) -> None:
        """Persist a selection to storage."""
        stored = await self._selections_store.async_load()
        selections = stored if isinstance(stored, dict) else {}
        selections[key] = value
        await self._selections_store.async_save(selections)

    def set_power_state(self, online: bool) -> None:
        """Hold an assumed power state until the next poll cycle catches up."""
        self._power_override = (online, time.monotonic())

    async def _async_update_data(self) -> PcRemoteData:
        """Fetch data from the PC Remote service."""
        data = PcRemoteData()

        # If within the optimistic window, skip the health check entirely and
        # return the assumed state. This prevents flickering during the PC
        # transition period after sleep or WoL.
        if self._power_override is not None:
            expected, timestamp = self._power_override
            if time.monotonic() - timestamp < POWER_HOLD_SECONDS:
                data.online = expected
                data.steam_games = list(self._cached_steam_games)
                return data
            self._power_override = None

        # Check health
        try:
            health = await self.client.get_health()
            data.online = True
            data.machine_name = health.get("machineName", "")
            data.service_version = health.get("version", "")
        except CannotConnectError:
            data.online = False
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err

        if not data.online:
            # Serve the last known game list so the source_list remains populated
            data.steam_games = list(self._cached_steam_games)
            return data

        # Try aggregated state endpoint first
        try:
            state = await self.client.get_system_state()
            self._populate_from_system_state(data, state)
            if data.steam_games:
                self._cached_steam_games = list(data.steam_games)
                await self._steam_games_store.async_save(self._cached_steam_games)
            if not data.steam_games:
                data.steam_games = list(self._cached_steam_games)
            await self._restore_selections(data)
            return data
        except (CannotConnectError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Aggregated state fetch failed, falling back to individual calls: %s", err)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Unexpected error fetching aggregated state, falling back: %s", err)

        # Fallback: individual calls
        try:
            data.audio_devices = await self.client.get_audio_devices()
            current = next(
                (d for d in data.audio_devices if d.get("isDefault")),
                None,
            )
            if current:
                data.current_audio_device = current.get("name")
                data.volume = current.get("volume")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch audio devices: %s", err)

        try:
            data.monitors = await self.client.get_monitors()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch monitors: %s", err)

        try:
            data.apps = await self.client.get_apps()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch apps: %s", err)

        try:
            fetched = await self.client.get_steam_games()
            if fetched:
                self._cached_steam_games = fetched
                await self._steam_games_store.async_save(fetched)
            data.steam_games = list(self._cached_steam_games)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch Steam games: %s", err)
            data.steam_games = list(self._cached_steam_games)

        try:
            data.steam_running = await self.client.get_steam_running()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch Steam running game: %s", err)

        try:
            data.modes = await self.client.get_modes()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch modes: %s", err)

        try:
            data.steam_bindings = await self.client.get_steam_bindings()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch steam bindings: %s", err)

        await self._restore_selections(data)
        return data

    async def _restore_selections(self, data: PcRemoteData) -> None:
        """Restore persisted mode/profile, invalidating stale values."""
        selections = await self.load_selections()
        mode = selections.get("mode")

        # Restore mode only if still in the available list
        if mode and mode in data.modes:
            data.current_mode = mode
        else:
            data.current_mode = None

        # Audio change detection: if the audio device changed externally, clear mode
        if (
            data.current_mode
            and self._prev_audio_device is not None
            and data.current_audio_device != self._prev_audio_device
        ):
            _LOGGER.debug(
                "Audio device changed from %s to %s, clearing persisted mode",
                self._prev_audio_device,
                data.current_audio_device,
            )
            data.current_mode = None
            await self.persist_selection("mode", None)

        self._prev_audio_device = data.current_audio_device

    def _populate_from_system_state(self, data: PcRemoteData, state: dict) -> None:
        """Populate PcRemoteData from an aggregated /api/system/state response."""
        audio = state.get("audio", {})
        data.audio_devices = audio.get("devices", [])
        data.current_audio_device = audio.get("current")
        data.volume = audio.get("volume")

        data.monitors = state.get("monitors", [])

        data.steam_games = state.get("steamGames", [])
        data.steam_running = state.get("runningGame")
        data.modes = state.get("modes", [])
        data.idle_seconds = state.get("idleSeconds")
        data.steam_bindings = state.get("steamBindings")
        data.steam_ready = state.get("steamReady")
        data.auto_sleep_minutes = state.get("autoSleepAfterMinutes")
