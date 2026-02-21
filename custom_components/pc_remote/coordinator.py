"""DataUpdateCoordinator for the PC Remote integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnectError, InvalidAuthError, PcRemoteClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class PcRemoteData:
    """Data returned by the coordinator."""

    online: bool = False
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

    async def _async_update_data(self) -> PcRemoteData:
        """Fetch data from the PC Remote service."""
        data = PcRemoteData()

        # Check health first
        try:
            await self.client.get_health()
            data.online = True
        except CannotConnectError:
            return data
        except InvalidAuthError as err:
            raise UpdateFailed("Invalid API key") from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Unexpected error polling health: %s", err)
            return data

        # Fetch audio state
        try:
            data.audio_devices = await self.client.get_audio_devices()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch audio devices: %s", err)

        try:
            current = await self.client.get_current_audio()
            data.current_audio_device = current.get("device")
            data.volume = current.get("volume")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch current audio: %s", err)

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
