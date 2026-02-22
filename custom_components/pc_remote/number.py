"""Number platform for the PC Remote integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
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
    """Set up the number platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    client: PcRemoteClient = data["client"]
    async_add_entities([PcRemoteVolumeNumber(coordinator, client, entry)])


class PcRemoteVolumeNumber(
    CoordinatorEntity[PcRemoteCoordinator], NumberEntity
):
    """Number entity for controlling the system volume."""

    _attr_has_entity_name = True
    _attr_translation_key = "volume"
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_volume"

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
    def native_value(self) -> float | None:
        """Return the current volume level."""
        return self.coordinator.data.volume

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume level."""
        await self._client.set_volume(int(value))
        self.coordinator.set_optimistic("volume", int(value))
        self.async_write_ha_state()
