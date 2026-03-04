"""Media player platform for the PC Remote integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from wakeonlan import send_magic_packet

from .api import CannotConnectError, PcRemoteClient
from .const import CONF_HOST, CONF_MAC_ADDRESS, CONF_PORT, DOMAIN, build_device_info
from .coordinator import PcRemoteCoordinator

_LOGGER = logging.getLogger(__name__)

_steam_logo_cache: tuple[bytes, str] | None = None


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
        self._stop_issued_at: datetime | None = None
        self._last_playing: dict | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info from latest coordinator data."""
        return build_device_info(
            self._entry,
            machine_name=self.coordinator.data.machine_name,
            sw_version=self.coordinator.data.service_version,
        )

    def _in_stop_hold_window(self) -> bool:
        """Return True if we are within 30 s of a stop command being issued."""
        if self._stop_issued_at is None:
            return False
        return (dt_util.utcnow() - self._stop_issued_at).total_seconds() < 30

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        if self._wake_target is not None:
            return MediaPlayerState.BUFFERING
        if not self.coordinator.data.online:
            return MediaPlayerState.OFF
        if self.coordinator.data.steam_running:
            # If a stop was issued, the service still reporting a running game
            # means the process has not exited yet. Slide the hold window
            # forward so it does not expire while the game is still dying, and
            # suppress the _last_playing refresh so the window does not get
            # confused about which game was last seen.
            if self._stop_issued_at is not None:
                self._stop_issued_at = dt_util.utcnow()
                return MediaPlayerState.PLAYING
            self._last_playing = self.coordinator.data.steam_running
            return MediaPlayerState.PLAYING
        # Hold optimistic playing state for 30 s after a stop command, to
        # absorb the poll-cycle lag between the game exiting and the service
        # confirming it is gone.
        if self._in_stop_hold_window():
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    def _effective_running(self) -> dict | None:
        """Return the running game, using last known game during stop hold window."""
        return (
            self.coordinator.data.steam_running
            or (self._last_playing if self._in_stop_hold_window() else None)
        )

    @property
    def media_title(self) -> str | None:
        """Return the title of the currently playing game."""
        target = self._wake_target or self._effective_running
        return target.get("name") if target else None

    @property
    def source(self) -> str | None:
        """Return the current game as the source."""
        target = self._wake_target or self._effective_running
        return target.get("name") if target else None

    @property
    def source_list(self) -> list[str]:
        """Return the list of recently played games."""
        return [g.get("name", "") for g in self.coordinator.data.steam_games]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        target = self._wake_target or self._effective_running
        attrs: dict[str, Any] = {}
        if target:
            attrs["app_id"] = target.get("appId")
            # Resolve the PC mode binding for the current/target game
            bindings = self.coordinator.data.steam_bindings
            if bindings and target.get("appId") is not None:
                app_id_str = str(target["appId"])
                game_bindings = bindings.get("gamePcModeBindings", {})
                if app_id_str in game_bindings:
                    attrs["game_pc_mode_binding"] = game_bindings[app_id_str]
                elif bindings.get("defaultPcMode"):
                    attrs["game_pc_mode_binding"] = bindings["defaultPcMode"]
        return attrs if attrs else None

    @property
    def _artwork_base_url(self) -> str:
        """Return the base URL for the service artwork endpoint."""
        host = self._entry.data[CONF_HOST]
        port = self._entry.data[CONF_PORT]
        return f"http://{host}:{port}/api/steam/artwork"

    _STEAM_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Steam_icon_logo.svg/960px-Steam_icon_logo.svg.png"

    @property
    def media_image_url(self) -> str | None:
        """Return artwork URL served from the PC's local Steam cache, or Steam logo when idle."""
        running = self._effective_running
        if running and (app_id := running.get("appId")):
            return f"{self._artwork_base_url}/{app_id}"
        if self.state == MediaPlayerState.IDLE:
            return self._STEAM_LOGO_URL
        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """All images are proxied through HA (LAN artwork or cached logo)."""
        return False

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Return media image bytes. Caches the Steam logo on first fetch."""
        running = self._effective_running
        if running and running.get("appId"):
            return await super().async_get_media_image()
        if self.state == MediaPlayerState.IDLE:
            return await self._get_steam_logo()
        return None, None

    async def async_get_browse_image(
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Fetch artwork for a game in the media browser from the service."""
        if not media_content_id:
            return None, None
        url = f"{self._artwork_base_url}/{media_content_id}"
        return await self._fetch_artwork(url)

    async def _fetch_artwork(self, url: str) -> tuple[bytes | None, str | None]:
        """Fetch an image from the service artwork endpoint (exempt from API key auth)."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    content_type = resp.content_type or "image/jpeg"
                    data = await resp.read()
                    return data, content_type
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch artwork from %s: %s", url, err)
        return None, None

    async def _get_steam_logo(self) -> tuple[bytes | None, str | None]:
        """Fetch the Steam logo once and return cached bytes on subsequent calls."""
        global _steam_logo_cache
        if _steam_logo_cache is not None:
            return _steam_logo_cache
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self._STEAM_LOGO_URL) as resp:
                if resp.status == 200:
                    content_type = resp.content_type or "image/png"
                    data = await resp.read()
                    _steam_logo_cache = (data, content_type)
                    return _steam_logo_cache
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed to fetch Steam logo: %s", err)
        return None, None

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

    async def _send_wol_sustained(self, mac: str, duration: int = 20, interval: int = 1) -> None:
        """Send WoL magic packets repeatedly for `duration` seconds."""
        end_time = dt_util.utcnow().timestamp() + duration
        while dt_util.utcnow().timestamp() < end_time:
            try:
                await self.hass.async_add_executor_job(send_magic_packet, mac)
            except (ValueError, OSError) as err:
                _LOGGER.error("Failed to send WoL packet: %s", err)
                return
            await asyncio.sleep(interval)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the PC via Wake-on-LAN (sustained 20 s retry loop)."""
        mac = self._entry.data.get(CONF_MAC_ADDRESS)
        if not mac:
            _LOGGER.error("MAC address not configured, cannot send WoL packet")
            return
        self.coordinator.set_power_state(True)
        self.async_write_ha_state()
        await self._send_wol_sustained(mac)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the PC to sleep."""
        try:
            await self._client.sleep()
        except CannotConnectError:
            pass  # PC suspended before responding — expected
        self.coordinator.set_power_state(False)
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop the currently running game."""
        if not self.coordinator.data.online:
            return
        self._stop_issued_at = dt_util.utcnow()
        await self._client.steam_stop()
        self.coordinator.data.steam_running = None
        self.async_write_ha_state()

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return browsable Steam games."""
        games = self.coordinator.data.steam_games
        base = self._artwork_base_url
        children = [
            BrowseMedia(
                media_class=MediaClass.GAME,
                media_content_id=str(g.get("appId", "")),
                media_content_type=MediaType.GAME,
                title=g.get("name", "Unknown"),
                can_play=True,
                can_expand=False,
                thumbnail=f"{base}/{g.get('appId', 0)}",
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

        # Ensure Steam is running before sending the launch command
        if not self.coordinator.data.steam_ready:
            _LOGGER.debug("Steam not ready, launching Steam Big Picture first")
            try:
                await self._client.launch_app("steam")
            except CannotConnectError as err:
                _LOGGER.warning("Failed to launch Steam: %s", err)
            await self._wait_for_steam_ready()

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
        await self._send_wol_sustained(mac)

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

        # Wait for Steam to be ready before launching
        steam_ready = await self._wait_for_steam_ready()
        if not steam_ready:
            _LOGGER.warning("Wake-and-play: Steam did not become ready within timeout")

        result = None
        try:
            result = await self._client.steam_run(app_id)
        except CannotConnectError as err:
            _LOGGER.warning("Wake-and-play: steam_run failed: %s", err)

        if result is None:
            _LOGGER.warning("Wake-and-play: game did not launch")

        self._wake_target = None
        if result:
            self.coordinator.data.steam_running = result
        await self.coordinator.async_request_refresh()

    async def _wait_for_steam_ready(self, max_wait: int = 120, interval: int = 5) -> bool:
        """Poll system state until steam_ready is true. Returns True if ready, False on timeout."""
        for _ in range(max_wait // interval):
            try:
                state = await self._client.get_system_state()
                if state.get("steamReady"):
                    return True
            except CannotConnectError:
                pass
            await asyncio.sleep(interval)
        return False
