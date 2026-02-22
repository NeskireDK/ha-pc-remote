"""DataUpdateCoordinator for the PC Remote integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnectError, InvalidAuthError, PcRemoteClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# After an action, assume the expected state for this many seconds
# before trusting polled data again.
OPTIMISTIC_HOLD_SECONDS = 30


@dataclass
class PcRemoteData:
    """Data returned by the coordinator."""

    online: bool = False
    machine_name: str = ""
    service_version: str = ""
    audio_devices: list[dict] = field(default_factory=list)
    current_audio_device: str | None = None
    volume: int | None = None
    monitor_profiles: list[str] = field(default_factory=list)
    monitors: list[dict] = field(default_factory=list)
    apps: list[dict] = field(default_factory=list)


class PcRemoteCoordinator(DataUpdateCoordinator[PcRemoteData]):
    """Coordinator that polls the PC Remote service."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PcRemoteClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self._optimistic: dict[str, tuple[object, float]] = {}

    def set_optimistic(self, key: str, value: object) -> None:
        """Set an optimistic override that suppresses polled values temporarily."""
        self._optimistic[key] = (value, time.monotonic())

    def get_optimistic(self, key: str) -> tuple[bool, object]:
        """Return (active, value) if the key has an unexpired optimistic override."""
        entry = self._optimistic.get(key)
        if entry is None:
            return False, None
        value, timestamp = entry
        if time.monotonic() - timestamp < OPTIMISTIC_HOLD_SECONDS:
            return True, value
        del self._optimistic[key]
        return False, None

    async def _async_update_data(self) -> PcRemoteData:
        """Fetch data from the PC Remote service."""
        data = PcRemoteData()

        # Check health first
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

        # Apply optimistic online override
        active, value = self.get_optimistic("online")
        if active:
            data.online = value  # type: ignore[assignment]

        if not data.online:
            return data

        # Fetch audio state
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

        # Apply optimistic audio overrides
        active, value = self.get_optimistic("volume")
        if active:
            data.volume = value  # type: ignore[assignment]

        active, value = self.get_optimistic("current_audio_device")
        if active:
            data.current_audio_device = value  # type: ignore[assignment]

        # Fetch monitor profiles
        try:
            profiles = await self.client.get_monitor_profiles()
            data.monitor_profiles = [p.get("name", p) if isinstance(p, dict) else p for p in profiles]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch monitor profiles: %s", err)

        # Fetch monitors
        try:
            data.monitors = await self.client.get_monitors()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch monitors: %s", err)

        # Fetch apps
        try:
            data.apps = await self.client.get_apps()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch apps: %s", err)

        return data
