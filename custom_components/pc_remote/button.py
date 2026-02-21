"""Button platform for the PC Remote integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PcRemoteClient
from .const import DOMAIN, build_device_info
from .coordinator import PcRemoteCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    client: PcRemoteClient = data["client"]
    async_add_entities([PcRemoteSleepButton(coordinator, client, entry)])


class PcRemoteSleepButton(
    CoordinatorEntity[PcRemoteCoordinator], ButtonEntity
):
    """Button that puts the PC to sleep."""

    _attr_has_entity_name = True
    _attr_name = "Sleep"
    _attr_icon = "mdi:power-sleep"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_sleep"
        self._attr_device_info = build_device_info(entry)

    async def async_press(self) -> None:
        """Send the sleep command."""
        await self._client.sleep()
