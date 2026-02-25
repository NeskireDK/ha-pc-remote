"""Tests for custom_components/pc_remote/media_player.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pc_remote.api import CannotConnectError
from custom_components.pc_remote.coordinator import PcRemoteData
from custom_components.pc_remote.media_player import PcRemoteSteamPlayer
from tests.conftest import (
    make_coordinator_data,
    make_mock_client,
    make_mock_coordinator,
    make_mock_entry,
    wire_entity,
)

from homeassistant.components.media_player import MediaPlayerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(data: PcRemoteData | None = None, client=None, entry=None):
    coordinator = make_mock_coordinator(data)
    coordinator.available = True
    client = client or make_mock_client()
    entry = entry or make_mock_entry()
    player = PcRemoteSteamPlayer(coordinator, client, entry)
    wire_entity(player, coordinator)
    return player, coordinator, client


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class TestState:
    def test_state_is_off_when_offline(self):
        data = make_coordinator_data(online=False, steam_running=None)
        player, *_ = _make_player(data)
        assert player.state == MediaPlayerState.OFF

    def test_state_is_playing_when_game_running(self):
        data = make_coordinator_data(
            online=True,
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, *_ = _make_player(data)
        assert player.state == MediaPlayerState.PLAYING

    def test_state_is_idle_when_online_no_game(self):
        data = make_coordinator_data(online=True, steam_running=None)
        player, *_ = _make_player(data)
        assert player.state == MediaPlayerState.IDLE

    def test_state_is_buffering_when_wake_target_set(self):
        data = make_coordinator_data(online=False, steam_running=None)
        player, *_ = _make_player(data)
        player._wake_target = {"appId": 570, "name": "Dota 2"}
        assert player.state == MediaPlayerState.BUFFERING


# ---------------------------------------------------------------------------
# Media title and source
# ---------------------------------------------------------------------------

class TestMediaTitleAndSource:
    def test_media_title_returns_running_game_name(self):
        data = make_coordinator_data(
            online=True,
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, *_ = _make_player(data)
        assert player.media_title == "Dota 2"

    def test_media_title_none_when_no_game(self):
        data = make_coordinator_data(online=True, steam_running=None)
        player, *_ = _make_player(data)
        assert player.media_title is None

    def test_source_returns_running_game_name(self):
        data = make_coordinator_data(
            online=True,
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, *_ = _make_player(data)
        assert player.source == "Dota 2"

    def test_source_none_when_no_game(self):
        data = make_coordinator_data(online=True, steam_running=None)
        player, *_ = _make_player(data)
        assert player.source is None

    def test_wake_target_overrides_running_for_title(self):
        data = make_coordinator_data(
            online=False,
            steam_running=None,
        )
        player, *_ = _make_player(data)
        player._wake_target = {"appId": 999, "name": "Queued Game"}
        assert player.media_title == "Queued Game"

    def test_source_list_from_steam_games(self):
        games = [
            {"appId": 570, "name": "Dota 2"},
            {"appId": 1091500, "name": "Cyberpunk 2077"},
        ]
        data = make_coordinator_data(steam_games=games)
        player, *_ = _make_player(data)
        assert player.source_list == ["Dota 2", "Cyberpunk 2077"]

    def test_source_list_empty_when_no_games(self):
        data = make_coordinator_data(steam_games=[])
        player, *_ = _make_player(data)
        assert player.source_list == []


# ---------------------------------------------------------------------------
# Media image
# ---------------------------------------------------------------------------

class TestMediaImage:
    def test_image_url_uses_service_artwork_endpoint(self):
        data = make_coordinator_data(
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, *_ = _make_player(data)
        url = player.media_image_url
        assert "570" in url
        assert "/api/steam/artwork/" in url

    def test_image_url_none_when_no_game(self):
        data = make_coordinator_data(steam_running=None)
        player, *_ = _make_player(data)
        assert player.media_image_url is None

    def test_image_not_remotely_accessible(self):
        data = make_coordinator_data()
        player, *_ = _make_player(data)
        assert player.media_image_remotely_accessible is False


# ---------------------------------------------------------------------------
# Extra state attributes
# ---------------------------------------------------------------------------

class TestExtraAttributes:
    def test_app_id_in_attributes_when_running(self):
        data = make_coordinator_data(
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, *_ = _make_player(data)
        attrs = player.extra_state_attributes
        assert attrs["app_id"] == 570

    def test_no_attributes_when_idle(self):
        data = make_coordinator_data(steam_running=None)
        player, *_ = _make_player(data)
        assert player.extra_state_attributes is None

    def test_game_pc_mode_binding_from_per_game(self):
        data = make_coordinator_data(
            steam_running={"appId": 730, "name": "CS2"},
            steam_bindings={
                "defaultPcMode": "couch",
                "gamePcModeBindings": {"730": "desktop"},
            },
        )
        player, *_ = _make_player(data)
        attrs = player.extra_state_attributes
        assert attrs["game_pc_mode_binding"] == "desktop"

    def test_game_pc_mode_binding_falls_back_to_default(self):
        data = make_coordinator_data(
            steam_running={"appId": 999, "name": "Other Game"},
            steam_bindings={
                "defaultPcMode": "couch",
                "gamePcModeBindings": {},
            },
        )
        player, *_ = _make_player(data)
        attrs = player.extra_state_attributes
        assert attrs["game_pc_mode_binding"] == "couch"

    def test_game_pc_mode_binding_missing_when_no_bindings(self):
        data = make_coordinator_data(
            steam_running={"appId": 570, "name": "Dota 2"},
            steam_bindings=None,
        )
        player, *_ = _make_player(data)
        attrs = player.extra_state_attributes
        assert "game_pc_mode_binding" not in attrs

    def test_game_pc_mode_binding_absent_when_no_default_and_no_per_game(self):
        data = make_coordinator_data(
            steam_running={"appId": 570, "name": "Dota 2"},
            steam_bindings={
                "defaultPcMode": "",
                "gamePcModeBindings": {},
            },
        )
        player, *_ = _make_player(data)
        attrs = player.extra_state_attributes
        assert "game_pc_mode_binding" not in attrs


# ---------------------------------------------------------------------------
# async_select_source
# ---------------------------------------------------------------------------

class TestSelectSource:
    @pytest.mark.asyncio
    async def test_launches_game_when_online_confirmed(self):
        """steam_run returns confirmed game data -- used directly."""
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)
        client.steam_run = AsyncMock(return_value={"appId": 570, "name": "Dota 2"})

        await player.async_select_source("Dota 2")

        client.steam_run.assert_awaited_once_with(570)
        assert coordinator.data.steam_running == {"appId": 570, "name": "Dota 2"}

    @pytest.mark.asyncio
    async def test_launches_game_when_online_not_confirmed(self):
        """steam_run returns None -- falls back to optimistic update."""
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)
        client.steam_run = AsyncMock(return_value=None)

        await player.async_select_source("Dota 2")

        client.steam_run.assert_awaited_once_with(570)
        assert coordinator.data.steam_running == {"appId": 570, "name": "Dota 2"}

    @pytest.mark.asyncio
    async def test_game_not_found_in_list_does_nothing(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)

        await player.async_select_source("Unknown Game")

        client.steam_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_launch_failure_logs_error_does_not_raise(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)
        client.steam_run.side_effect = CannotConnectError("refused")

        # Should not raise
        await player.async_select_source("Dota 2")

        assert coordinator.data.steam_running is None

    @pytest.mark.asyncio
    async def test_offline_triggers_wake_and_play(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=False, steam_games=games)
        player, coordinator, client = _make_player(data)
        coordinator.hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())

        await player.async_select_source("Dota 2")

        assert player._wake_target == {"appId": 570, "name": "Dota 2"}
        coordinator.hass.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_game_with_no_app_id_does_nothing(self):
        """A game dict with appId=None should not trigger a launch."""
        games = [{"appId": None, "name": "Broken Game"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)

        await player.async_select_source("Broken Game")

        client.steam_run.assert_not_awaited()


# ---------------------------------------------------------------------------
# async_media_stop
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# async_turn_on / async_turn_off
# ---------------------------------------------------------------------------

class TestTurnOnOff:
    @pytest.mark.asyncio
    async def test_turn_on_sends_wol_and_sets_power_state(self):
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)

        await player.async_turn_on()

        coordinator.hass.async_add_executor_job.assert_awaited_once()
        coordinator.set_power_state.assert_called_once_with(True)
        player.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_turn_on_no_mac_does_nothing(self):
        data = make_coordinator_data(online=False)
        entry = make_mock_entry()
        entry.data = {"host": "192.168.1.100", "port": 5000, "api_key": "key"}
        player, coordinator, client = _make_player(data, entry=entry)

        await player.async_turn_on()

        coordinator.hass.async_add_executor_job.assert_not_awaited()
        coordinator.set_power_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_wol_error_does_not_propagate(self):
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        coordinator.hass.async_add_executor_job = AsyncMock(side_effect=OSError("fail"))

        await player.async_turn_on()

        coordinator.set_power_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_off_calls_sleep_and_sets_power_state(self):
        data = make_coordinator_data(online=True)
        player, coordinator, client = _make_player(data)

        await player.async_turn_off()

        client.sleep.assert_awaited_once()
        coordinator.set_power_state.assert_called_once_with(False)
        player.async_write_ha_state.assert_called_once()

    def test_supported_features_include_turn_on_off(self):
        from homeassistant.components.media_player import MediaPlayerEntityFeature
        player, *_ = _make_player()
        assert player._attr_supported_features & MediaPlayerEntityFeature.TURN_ON
        assert player._attr_supported_features & MediaPlayerEntityFeature.TURN_OFF


# ---------------------------------------------------------------------------
# async_media_stop
# ---------------------------------------------------------------------------

class TestMediaStop:
    @pytest.mark.asyncio
    async def test_stop_calls_steam_stop_and_clears_running(self):
        data = make_coordinator_data(
            online=True,
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, coordinator, client = _make_player(data)

        await player.async_media_stop()

        client.steam_stop.assert_awaited_once()
        assert coordinator.data.steam_running is None

    @pytest.mark.asyncio
    async def test_stop_does_nothing_when_offline(self):
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)

        await player.async_media_stop()

        client.steam_stop.assert_not_awaited()


# ---------------------------------------------------------------------------
# Unique ID and features
# ---------------------------------------------------------------------------

class TestEntityAttributes:
    def test_unique_id_includes_entry_id(self):
        entry = make_mock_entry(entry_id="myentry")
        data = make_coordinator_data()
        coordinator = make_mock_coordinator(data)
        client = make_mock_client()
        player = PcRemoteSteamPlayer(coordinator, client, entry)
        assert player._attr_unique_id == "myentry_steam"

    def test_supported_features_include_select_source_and_stop(self):
        from homeassistant.components.media_player import MediaPlayerEntityFeature
        player, *_ = _make_player()
        assert player._attr_supported_features & MediaPlayerEntityFeature.SELECT_SOURCE
        assert player._attr_supported_features & MediaPlayerEntityFeature.STOP

    def test_supported_features_include_browse_and_play_media(self):
        from homeassistant.components.media_player import MediaPlayerEntityFeature
        player, *_ = _make_player()
        assert player._attr_supported_features & MediaPlayerEntityFeature.BROWSE_MEDIA
        assert player._attr_supported_features & MediaPlayerEntityFeature.PLAY_MEDIA


# ---------------------------------------------------------------------------
# async_browse_media
# ---------------------------------------------------------------------------

class TestBrowseMedia:
    @pytest.mark.asyncio
    async def test_returns_root_with_children(self):
        games = [
            {"appId": 570, "name": "Dota 2"},
            {"appId": 1091500, "name": "Cyberpunk 2077"},
        ]
        data = make_coordinator_data(steam_games=games)
        player, *_ = _make_player(data)

        result = await player.async_browse_media()

        assert result.title == "Steam Games"
        assert result.can_expand is True
        assert result.can_play is False
        assert len(result.children) == 2

    @pytest.mark.asyncio
    async def test_children_have_game_properties(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(steam_games=games)
        player, *_ = _make_player(data)

        result = await player.async_browse_media()
        child = result.children[0]

        assert child.title == "Dota 2"
        assert child.media_content_id == "570"
        assert child.can_play is True
        assert child.can_expand is False
        assert "570" in child.thumbnail

    @pytest.mark.asyncio
    async def test_empty_games_returns_empty_children(self):
        data = make_coordinator_data(steam_games=[])
        player, *_ = _make_player(data)

        result = await player.async_browse_media()

        assert result.children == []


# ---------------------------------------------------------------------------
# async_play_media
# ---------------------------------------------------------------------------

class TestPlayMedia:
    @pytest.mark.asyncio
    async def test_launches_game_by_app_id(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)
        client.steam_run = AsyncMock(return_value={"appId": 570, "name": "Dota 2"})

        await player.async_play_media("game", "570")

        client.steam_run.assert_awaited_once_with(570)
        assert coordinator.data.steam_running == {"appId": 570, "name": "Dota 2"}

    @pytest.mark.asyncio
    async def test_invalid_media_id_does_nothing(self):
        player, coordinator, client = _make_player()

        await player.async_play_media("game", "not-a-number")

        client.steam_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_offline_triggers_wake_and_play(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=False, steam_games=games)
        player, coordinator, client = _make_player(data)
        coordinator.hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())

        await player.async_play_media("game", "570")

        assert player._wake_target == {"appId": 570, "name": "Dota 2"}
        coordinator.hass.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_launch_failure_does_not_raise(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        data = make_coordinator_data(online=True, steam_games=games)
        player, coordinator, client = _make_player(data)
        client.steam_run.side_effect = CannotConnectError("refused")

        await player.async_play_media("game", "570")

        assert coordinator.data.steam_running is None
