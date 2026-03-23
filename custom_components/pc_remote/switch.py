"""Switch platform for the PC Remote integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import CannotConnectError, PcRemoteClient
from .const import DOMAIN
from .coordinator import PcRemoteCoordinator
from .entity_base import PcRemoteEntityBase

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

    entities: list[SwitchEntity] = []

    # Power switch (wake/sleep)
    entities.append(PcRemotePowerSwitch(coordinator, client, entry))

    # App switches
    for app in coordinator.data.apps:
        entities.append(
            PcRemoteAppSwitch(
                coordinator,
                client,
                entry,
                app.get("key", ""),
                app.get("displayName", app.get("key", "unknown")),
            )
        )

    async_add_entities(entities)


class PcRemotePowerSwitch(PcRemoteEntityBase, SwitchEntity):
    """Switch that wakes or sleeps the PC."""

    _attr_has_entity_name = True
    _attr_translation_key = "power"
    _attr_icon = "mdi:power"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the power switch."""
        super().__init__(coordinator, entry)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_power"

    @property
    def available(self) -> bool:
        """Power switch is always available (WoL works when PC is off)."""
        return True

    @property
    def is_on(self) -> bool | None:
        """Return True if the PC is online."""
        return self.coordinator.data.online

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the PC via sustained Wake-on-LAN."""
        await self.coordinator.async_wake_and_wait()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the PC to sleep."""
        try:
            await self._client.sleep()
        except CannotConnectError:
            pass  # PC suspended before responding — expected
        self.coordinator.set_power_state(False)
        self.async_write_ha_state()


class PcRemoteAppSwitch(PcRemoteEntityBase, SwitchEntity):
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
        super().__init__(coordinator, entry)
        self._client = client
        self._app_key = app_key
        self._attr_name = display_name
        self._attr_unique_id = f"{entry.entry_id}_app_{app_key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the app is running."""
        for app in self.coordinator.data.apps:
            if app.get("key") == self._app_key:
                return app.get("isRunning")
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Launch the app, waking the PC first if needed."""
        if not await self.coordinator.async_ensure_online():
            return
        await self._client.launch_app(self._app_key)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Kill the app."""
        await self._client.kill_app(self._app_key)
        await self.coordinator.async_request_refresh()
