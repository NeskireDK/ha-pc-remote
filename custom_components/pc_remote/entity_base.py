"""Base entity class for the PC Remote integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import build_device_info
from .coordinator import PcRemoteCoordinator


class PcRemoteEntityBase(CoordinatorEntity[PcRemoteCoordinator]):
    """Base class for all PC Remote entities with shared device_info."""

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from latest coordinator data."""
        return build_device_info(
            self._entry,
            machine_name=self.coordinator.data.machine_name,
            sw_version=self.coordinator.data.service_version,
        )
