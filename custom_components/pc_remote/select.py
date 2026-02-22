"""Select platform for the PC Remote integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PcRemoteClient
from .const import DOMAIN, build_device_info
from .coordinator import PcRemoteCoordinator


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
        PcRemoteMonitorProfileSelect(coordinator, client, entry),
        PcRemoteMonitorSoloSelect(coordinator, client, entry),
    ])


class PcRemoteAudioOutputSelect(
    CoordinatorEntity[PcRemoteCoordinator], SelectEntity
):
    """Select entity for choosing the active audio output device."""

    _attr_has_entity_name = True
    _attr_translation_key = "audio_output"
    _attr_icon = "mdi:speaker"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_audio_output"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from latest coordinator data."""
        return build_device_info(
            self._entry,
            machine_name=self.coordinator.data.machine_name,
            sw_version=self.coordinator.data.service_version,
        )

    @property
    def available(self) -> bool:
        """Available only when the PC is online."""
        return super().available and self.coordinator.data.online

    @property
    def options(self) -> list[str]:
        """Return the list of available audio output devices."""
        return [d.get("name", "") for d in self.coordinator.data.audio_devices]

    @property
    def current_option(self) -> str | None:
        """Return the currently active audio output device."""
        return self.coordinator.data.current_audio_device

    async def async_select_option(self, option: str) -> None:
        """Set the audio output device."""
        await self._client.set_audio_device(option)
        self.coordinator.set_optimistic("current_audio_device", option)
        self.async_write_ha_state()


class PcRemoteMonitorProfileSelect(
    CoordinatorEntity[PcRemoteCoordinator], SelectEntity
):
    """Select entity for choosing a monitor profile."""

    _attr_has_entity_name = True
    _attr_translation_key = "monitor_profile"
    _attr_icon = "mdi:monitor-shimmer"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_monitor_profile"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from latest coordinator data."""
        return build_device_info(
            self._entry,
            machine_name=self.coordinator.data.machine_name,
            sw_version=self.coordinator.data.service_version,
        )

    @property
    def available(self) -> bool:
        """Available only when the PC is online."""
        return super().available and self.coordinator.data.online

    @property
    def options(self) -> list[str]:
        """Return the list of available monitor profiles."""
        return self.coordinator.data.monitor_profiles

    @property
    def current_option(self) -> str | None:
        """Return the current option (not tracked)."""
        return None

    async def async_select_option(self, option: str) -> None:
        """Activate the selected monitor profile."""
        await self._client.set_monitor_profile(option)
        await self.coordinator.async_request_refresh()


class PcRemoteMonitorSoloSelect(
    CoordinatorEntity[PcRemoteCoordinator], SelectEntity
):
    """Select entity for choosing the sole active monitor."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_monitor"
    _attr_icon = "mdi:monitor"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_monitor_solo"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from latest coordinator data."""
        return build_device_info(
            self._entry,
            machine_name=self.coordinator.data.machine_name,
            sw_version=self.coordinator.data.service_version,
        )

    @property
    def available(self) -> bool:
        """Available only when the PC is online."""
        return super().available and self.coordinator.data.online

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
        """Solo the selected monitor."""
        monitor_id = self._monitor_id_for_name(option)
        if monitor_id is not None:
            await self._client.solo_monitor(monitor_id)
            await self.coordinator.async_request_refresh()
