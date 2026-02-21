"""Switch platform for the PC Remote integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up the switch platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    client: PcRemoteClient = data["client"]

    entities = [
        PcRemoteAppSwitch(coordinator, client, entry, app["key"], app["displayName"])
        for app in coordinator.data.apps
    ]
    async_add_entities(entities)


class PcRemoteAppSwitch(
    CoordinatorEntity[PcRemoteCoordinator], SwitchEntity
):
    """Switch that launches or kills an app on the PC."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:application"

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
        app_key: str,
        display_name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._client = client
        self._app_key = app_key
        self._attr_name = display_name
        self._attr_unique_id = f"{entry.entry_id}_app_{app_key}"
        self._attr_device_info = build_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        """Return True if the app is running."""
        for app in self.coordinator.data.apps:
            if app["key"] == self._app_key:
                return app["isRunning"]
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Launch the app."""
        await self._client.launch_app(self._app_key)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Kill the app."""
        await self._client.kill_app(self._app_key)
        await self.coordinator.async_request_refresh()
