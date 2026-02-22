"""Media player platform for the PC Remote integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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
    """Set up the media player platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PcRemoteCoordinator = data["coordinator"]
    client: PcRemoteClient = data["client"]
    async_add_entities([PcRemoteSteamPlayer(coordinator, client, entry)])


class PcRemoteSteamPlayer(
    CoordinatorEntity[PcRemoteCoordinator], MediaPlayerEntity
):
    """Media player entity for Steam game control."""

    _attr_has_entity_name = True
    _attr_translation_key = "steam"
    _attr_icon = "mdi:steam"
    _attr_supported_features = (
        MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(
        self,
        coordinator: PcRemoteCoordinator,
        client: PcRemoteClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_steam"

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
        """Always available — source list is shown even when PC is offline."""
        return super().available

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        if not self.coordinator.data.online:
            return MediaPlayerState.OFF
        if self.coordinator.data.steam_running:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Return the title of the currently playing game."""
        running = self.coordinator.data.steam_running
        return running.get("name") if running else None

    @property
    def source(self) -> str | None:
        """Return the current game as the source."""
        running = self.coordinator.data.steam_running
        return running.get("name") if running else None

    @property
    def source_list(self) -> list[str]:
        """Return the list of recently played games."""
        return [g.get("name", "") for g in self.coordinator.data.steam_games]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        running = self.coordinator.data.steam_running
        if running:
            return {"app_id": running.get("appId")}
        return None

    async def async_select_source(self, source: str) -> None:
        """Launch the selected game."""
        if not self.coordinator.data.online:
            _LOGGER.warning("PC is offline, cannot launch game: %s", source)
            return
        # Find the appId for the selected game name
        for game in self.coordinator.data.steam_games:
            if game.get("name") == source:
                app_id = game.get("appId")
                if app_id is not None:
                    await self._client.steam_run(app_id)
                    # Optimistic update
                    self.coordinator.data.steam_running = {
                        "appId": app_id,
                        "name": source,
                    }
                    self.async_write_ha_state()
                return
        _LOGGER.warning("Steam game not found in list: %s", source)

    async def async_media_stop(self) -> None:
        """Stop the currently running game."""
        if not self.coordinator.data.online:
            return
        await self._client.steam_stop()
        # Optimistic update
        self.coordinator.data.steam_running = None
        self.async_write_ha_state()
