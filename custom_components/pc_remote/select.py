"""Select platform for the PC Remote integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PcRemoteClient
from .const import DOMAIN
from .coordinator import PcRemoteCoordinator
from .entity_base import PcRemoteEntityBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    client: PcRemoteClient = data["client"]
    async_add_entities([
        PcRemoteAudioOutputSelect(coordinator, client, entry),
        PcRemoteMonitorSoloSelect(coordinator, client, entry),
        PcRemoteModeSelect(coordinator, client, entry),
    ])


class PcRemoteSelectBase(PcRemoteEntityBase, SelectEntity):
    """Base class for PC Remote select entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, entry)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"


class PcRemoteAudioOutputSelect(PcRemoteSelectBase):
    """Select entity for choosing the active audio output device."""

    _attr_translation_key = "audio_output"
    _attr_icon = "mdi:speaker"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, client, entry, "audio_output")

    @property
    def options(self) -> list[str]:
        """Return the list of available audio output devices."""
        return [d.get("name", "") for d in self.coordinator.data.audio_devices]

    @property
    def current_option(self) -> str | None:
        """Return the currently active audio output device."""
        return self.coordinator.data.current_audio_device

    async def async_select_option(self, option: str) -> None:
        """Set the audio output device, waking the PC first if needed."""
        if not await self.coordinator.async_ensure_online():
            return
        await self._client.set_audio_device(option)
        self.coordinator.data.current_audio_device = option
        self.async_write_ha_state()


class PcRemoteMonitorSoloSelect(PcRemoteSelectBase):
    """Select entity for choosing the sole active monitor."""

    _attr_translation_key = "active_monitor"
    _attr_icon = "mdi:monitor"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, client, entry, "monitor_solo")

    @property
    def options(self) -> list[str]:
        """Return the list of connected monitor names, preferring the EDID model name."""
        return [
            m.get("monitorName") or m.get("name", "")
            for m in self.coordinator.data.monitors
        ]

    @property
    def current_option(self) -> str | None:
        """Return the primary monitor name."""
        for m in self.coordinator.data.monitors:
            if m.get("isPrimary"):
                return m.get("monitorName") or m.get("name")
        return None

    def _monitor_id_for_name(self, name: str) -> str | None:
        """Resolve a display name to a monitor ID."""
        for m in self.coordinator.data.monitors:
            if (m.get("monitorName") or m.get("name")) == name:
                return m.get("monitorId")
        return None

    async def async_select_option(self, option: str) -> None:
        """Solo the selected monitor, waking the PC first if needed."""
        if not await self.coordinator.async_ensure_online():
            return
        monitor_id = self._monitor_id_for_name(option)
        if monitor_id is None:
            _LOGGER.warning("Monitor '%s' not found in known monitors", option)
            return
        await self._client.solo_monitor(monitor_id)
        await self.coordinator.async_request_refresh()


class PcRemoteModeSelect(PcRemoteSelectBase):
    """Select entity for applying a PC mode."""

    _attr_translation_key = "pc_mode"
    _attr_icon = "mdi:television-play"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, client, entry, "pc_mode")

    @property
    def options(self) -> list[str]:
        """Return the list of available PC modes."""
        return self.coordinator.data.modes

    @property
    def current_option(self) -> str | None:
        """Return the persisted mode selection."""
        return self.coordinator.data.current_mode

    async def async_select_option(self, option: str) -> None:
        """Apply the selected PC mode, waking the PC first if needed."""
        if not await self.coordinator.async_ensure_online():
            return
        await self._client.set_mode(option)
        self.coordinator.data.current_mode = option
        await self.coordinator.persist_selection("mode", option)
        self.async_write_ha_state()
