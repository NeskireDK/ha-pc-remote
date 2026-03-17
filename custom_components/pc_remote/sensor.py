"""Sensor platform for the PC Remote integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, build_device_info
from .coordinator import PcRemoteCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    async_add_entities([
        PcRemoteIdleSensor(coordinator, entry),
        PcRemoteVersionSensor(coordinator, entry),
    ])


class PcRemoteIdleSensor(
    CoordinatorEntity[PcRemoteCoordinator], SensorEntity
):
    """Sensor for user idle duration on the remote PC."""

    _attr_has_entity_name = True
    _attr_translation_key = "idle_duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-sand"
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the idle duration sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_idle_duration"

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
        """Only available when PC is online."""
        return super().available and self.coordinator.data.online

    @property
    def native_value(self) -> int | None:
        """Return idle seconds."""
        return self.coordinator.data.idle_seconds


class PcRemoteVersionSensor(
    CoordinatorEntity[PcRemoteCoordinator], SensorEntity
):
    """Sensor for the service version on the remote PC."""

    _attr_has_entity_name = True
    _attr_translation_key = "service_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:tag"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the service version sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_service_version"

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
        """Only available when PC is online."""
        return super().available and self.coordinator.data.online

    @property
    def native_value(self) -> str | None:
        """Return service version string."""
        return self.coordinator.data.service_version or None
