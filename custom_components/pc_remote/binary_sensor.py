"""Binary sensor platform for the PC Remote integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, DOMAIN
from .coordinator import PcRemoteCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: PcRemoteCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([PcRemoteOnlineSensor(coordinator, entry)])


class PcRemoteOnlineSensor(
    CoordinatorEntity[PcRemoteCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether the Windows PC is online."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Online"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_online"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"PC Remote ({entry.data[CONF_HOST]})",
            "manufacturer": "PC Remote",
            "model": "PC",
            "configuration_url": f"http://{entry.data[CONF_HOST]}:{entry.data['port']}",
        }

    @property
    def icon(self) -> str:
        """Return icon based on online state."""
        return "mdi:desktop-classic" if self.is_on else "mdi:desktop-classic-off"

    @property
    def is_on(self) -> bool | None:
        """Return True if the PC is online."""
        return self.coordinator.data.online
