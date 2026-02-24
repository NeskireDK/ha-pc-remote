"""Media player platform for the PC Remote integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from wakeonlan import send_magic_packet

from .api import CannotConnectError, PcRemoteClient
from .const import CONF_MAC_ADDRESS, DOMAIN, build_device_info
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
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
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
        self._wake_target: dict | None = None
        self._wake_task: asyncio.Task | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from latest coordinator data."""
        return build_device_info(
            self._entry,
            machine_name=self.coordinator.data.machine_name,
            sw_version=self.coordinator.data.service_version,
        )

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        if self._wake_target is not None:
            return MediaPlayerState.BUFFERING
        if not self.coordinator.data.online:
            return MediaPlayerState.OFF
        if self.coordinator.data.steam_running:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        """Return the title of the currently playing game."""
        target = self._wake_target or self.coordinator.data.steam_running
        return target.get("name") if target else None

    @property
    def source(self) -> str | None:
        """Return the current game as the source."""
        target = self._wake_target or self.coordinator.data.steam_running
        return target.get("name") if target else None

    @property
    def source_list(self) -> list[str]:
        """Return the list of recently played games."""
        return [g.get("name", "") for g in self.coordinator.data.steam_games]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        target = self._wake_target or self.coordinator.data.steam_running
        return {"app_id": target.get("appId")} if target else None

    @property
    def media_image_url(self) -> str | None:
        """Return Steam CDN artwork URL for the running game."""
        running = self.coordinator.data.steam_running
        if running and (app_id := running.get("appId")):
            return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Image is hosted on Steam CDN — no proxying needed."""
        return True

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending wake-and-play task on removal."""
        if self._wake_task and not self._wake_task.done():
            self._wake_task.cancel()

    async def async_select_source(self, source: str) -> None:
        """Launch the selected game."""
        for game in self.coordinator.data.steam_games:
            if game.get("name") == source:
                app_id = game.get("appId")
                if app_id is None:
                    _LOGGER.warning("Source '%s' has no appId", source)
                    return
                await self._launch_or_wake(app_id, source)
                return
        _LOGGER.warning("Steam game not found in list: %s", source)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the PC via Wake-on-LAN."""
        mac = self._entry.data.get(CONF_MAC_ADDRESS)
        if not mac:
            _LOGGER.error("MAC address not configured, cannot send WoL packet")
            return
        try:
            await self.hass.async_add_executor_job(send_magic_packet, mac)
        except (ValueError, OSError) as err:
            _LOGGER.error("Failed to send WoL packet: %s", err)
            return
        self.coordinator.set_power_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the PC to sleep."""
        await self._client.sleep()
        self.coordinator.set_power_state(False)
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop the currently running game."""
        if not self.coordinator.data.online:
            return
        await self._client.steam_stop()
        self.coordinator.data.steam_running = None
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return browsable Steam games."""
        games = self.coordinator.data.steam_games
        children = [
            BrowseMedia(
                media_class=MediaClass.GAME,
                media_content_id=str(g.get("appId", "")),
                media_content_type=MediaType.GAME,
                title=g.get("name", "Unknown"),
                can_play=True,
                can_expand=False,
                thumbnail=f"https://cdn.cloudflare.steamstatic.com/steam/apps/{g.get('appId', 0)}/header.jpg",
            )
            for g in games
        ]
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="steam_games",
            media_content_type=MediaType.GAME,
            title="Steam Games",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Launch a Steam game by app ID from the media browser."""
        try:
            app_id = int(media_id)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid media_id for Steam game: %s", media_id)
            return

        name = next(
            (g.get("name", "") for g in self.coordinator.data.steam_games if g.get("appId") == app_id),
            f"Game {app_id}",
        )
        await self._launch_or_wake(app_id, name)

    async def _launch_or_wake(self, app_id: int, name: str) -> None:
        """Launch a game, or wake the PC first if offline."""
        if not self.coordinator.data.online:
            if self._wake_task and not self._wake_task.done():
                self._wake_task.cancel()
            self._wake_target = {"appId": app_id, "name": name}
            self.async_write_ha_state()
            self._wake_task = self.hass.async_create_task(
                self._wake_and_play(app_id, name)
            )
            return

        try:
            result = await self._client.steam_run(app_id)
        except CannotConnectError as err:
            _LOGGER.error("Failed to launch Steam game '%s': %s", name, err)
            return
        self.coordinator.data.steam_running = (
            result or {"appId": app_id, "name": name}
        )
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def _wake_and_play(self, app_id: int, source: str) -> None:
        """Wake the PC via WoL, then launch the game when Steam is ready."""
        mac = self._entry.data.get(CONF_MAC_ADDRESS)
        if not mac:
            _LOGGER.warning("Wake-and-play: MAC address not configured, cannot wake PC")
            self._wake_target = None
            self.async_write_ha_state()
            return

        # Capture target — coordinator refreshes must not clear this
        target = {"appId": app_id, "name": source}
        try:
            await self.hass.async_add_executor_job(send_magic_packet, mac)
        except (ValueError, OSError) as err:
            _LOGGER.error("Failed to send WoL packet: %s", err)

        # Poll /api/health until service responds (max 3 minutes, every 5s)
        online = False
        for _ in range(36):
            # Re-assert wake target each iteration — coordinator refreshes
            # may have cleared it
            self._wake_target = target
            await asyncio.sleep(5)
            try:
                await self._client.get_health()
                online = True
                break
            except CannotConnectError:
                continue

        if not online:
            _LOGGER.warning("Wake-and-play: PC did not come online within timeout")
            self._wake_target = None
            self.async_write_ha_state()
            return

        # Launch — service now polls internally and returns the running game
        result = None
        try:
            result = await self._client.steam_run(app_id)
        except CannotConnectError as err:
            _LOGGER.debug("Wake-and-play steam_run attempt 1: %s", err)

        # One retry after 15s if Steam wasn't ready right after boot
        if result is None:
            self._wake_target = target
            await asyncio.sleep(15)
            try:
                result = await self._client.steam_run(app_id)
            except CannotConnectError as err:
                _LOGGER.debug("Wake-and-play steam_run attempt 2: %s", err)

        if result is None:
            _LOGGER.warning("Wake-and-play: game did not launch after 2 attempts")

        self._wake_target = None
        if result:
            self.coordinator.data.steam_running = result
        await self.coordinator.async_request_refresh()
