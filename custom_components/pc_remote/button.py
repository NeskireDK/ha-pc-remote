"""Button platform for the PC Remote integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PcRemoteClient
from .const import DOMAIN
from .coordinator import PcRemoteCoordinator
from .entity_base import PcRemoteEntityBase


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PC Remote buttons."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    client: PcRemoteClient = data["client"]
    async_add_entities([PcRemoteUpdateButton(coordinator, client, entry)])


class PcRemoteUpdateButton(PcRemoteEntityBase, ButtonEntity):
    """Button to trigger service update check."""

    _attr_has_entity_name = True
    _attr_translation_key = "check_update"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:update"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the update button."""
        super().__init__(coordinator, entry)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_check_update"

    @property
    def available(self) -> bool:
        """Only available when PC is online."""
        return super().available and self.coordinator.data.online

    async def async_press(self) -> None:
        """Trigger update check on the service."""
        await self._client.trigger_update()
