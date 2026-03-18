"""Tests for custom_components/pc_remote/media_player.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.pc_remote.api import CannotConnectError
from custom_components.pc_remote.coordinator import PcRemoteData
from custom_components.pc_remote.media_player import PcRemoteSteamPlayer, WAKE_RETRY_COUNT
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
        assert player.source_list == ["Dota 2", "Cyberpunk 2077", "Steam Big Picture"]

    def test_source_list_always_includes_big_picture(self):
        data = make_coordinator_data(steam_games=[])
        player, *_ = _make_player(data)
        assert player.source_list == ["Steam Big Picture"]


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

    def test_image_url_steam_logo_when_idle(self):
        data = make_coordinator_data(steam_running=None)
        player, *_ = _make_player(data)
        assert player.media_image_url == "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Steam_icon_logo.svg/960px-Steam_icon_logo.svg.png"

    def test_image_remotely_accessible_always_false(self):
        data = make_coordinator_data(steam_running=None)
        player, *_ = _make_player(data)
        assert player.media_image_remotely_accessible is False

    def test_image_not_remotely_accessible_when_game_running(self):
        data = make_coordinator_data(steam_running={"appId": 570, "name": "Dota 2"})
        player, *_ = _make_player(data)
        assert player.media_image_remotely_accessible is False


# ---------------------------------------------------------------------------
# async_get_browse_image
# ---------------------------------------------------------------------------

class TestBrowseImage:
    @pytest.mark.asyncio
    async def test_browse_image_fetches_artwork_for_game(self):
        """async_get_browse_image fetches from the service artwork endpoint."""
        data = make_coordinator_data()
        player, coordinator, client = _make_player(data)

        player._async_fetch_image = AsyncMock(
            return_value=(b"\xff\xd8fake-jpg", "image/jpeg")
        )

        image_bytes, content_type = await player.async_get_browse_image(
            "game", "570"
        )

        assert image_bytes == b"\xff\xd8fake-jpg"
        assert content_type == "image/jpeg"
        player._async_fetch_image.assert_awaited_once()
        call_url = player._async_fetch_image.call_args[0][0]
        assert "/api/steam/artwork/570" in call_url

    @pytest.mark.asyncio
    async def test_browse_image_returns_none_for_empty_content_id(self):
        data = make_coordinator_data()
        player, *_ = _make_player(data)

        image_bytes, content_type = await player.async_get_browse_image("game", "")
        assert image_bytes is None
        assert content_type is None

    @pytest.mark.asyncio
    async def test_browse_image_returns_none_on_fetch_failure(self):
        data = make_coordinator_data()
        player, coordinator, client = _make_player(data)

        player._async_fetch_image = AsyncMock(return_value=(None, None))

        image_bytes, content_type = await player.async_get_browse_image(
            "game", "99999"
        )

        assert image_bytes is None
        assert content_type is None


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

        # Sustained WoL loop sends one packet per second for 20 s
        assert coordinator.hass.async_add_executor_job.await_count >= 1
        coordinator.set_power_state.assert_called_once_with(True)
        # Called: before wake (BUFFERING), inside _wake_and_wait, after wake (clear)
        assert player.async_write_ha_state.call_count >= 2

    @pytest.mark.asyncio
    async def test_turn_on_wol_error_does_not_propagate(self):
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        coordinator.hass.async_add_executor_job = AsyncMock(side_effect=OSError("fail"))

        await player.async_turn_on()

        # set_power_state is called before sending WoL — error in WoL does not prevent it
        coordinator.set_power_state.assert_called_once_with(True)

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

    @pytest.mark.asyncio
    async def test_stop_sets_stop_issued_at(self):
        """async_media_stop records the timestamp so the hold window is active."""
        data = make_coordinator_data(online=True, steam_running={"appId": 570, "name": "Dota 2"})
        player, coordinator, client = _make_player(data)

        assert player._stop_issued_at is None
        await player.async_media_stop()
        assert player._stop_issued_at is not None

    def test_state_sliding_window_while_service_still_reports_running(self):
        """When stop was issued but service still reports game running, the hold
        window is extended (stop_issued_at is refreshed) so the window never
        expires while the process is still alive."""
        from homeassistant.util import dt as dt_util
        from datetime import timedelta

        data = make_coordinator_data(online=True, steam_running={"appId": 570, "name": "Dota 2"})
        player, coordinator, client = _make_player(data)

        # Simulate stop issued 25 s ago — window is approaching expiry but has margin
        old_ts = dt_util.utcnow() - timedelta(seconds=25)
        player._stop_issued_at = old_ts

        # Coordinator still reports the game as running
        coordinator.data.steam_running = {"appId": 570, "name": "Dota 2"}

        state = player.state

        assert state == MediaPlayerState.PLAYING
        # stop_issued_at must have been slid forward (refreshed to ~now)
        assert player._stop_issued_at > old_ts

    def test_state_stop_hold_window_active_after_game_exits(self):
        """Once service reports game gone, the 30 s hold window takes over so
        HA does not immediately flip to IDLE before the next poll confirms."""
        from homeassistant.util import dt as dt_util

        data = make_coordinator_data(online=True, steam_running=None)
        player, coordinator, client = _make_player(data)

        # Stop was issued 5 s ago; service now reports no game running
        player._stop_issued_at = dt_util.utcnow()
        player._last_playing = {"appId": 570, "name": "Dota 2"}

        assert player.state == MediaPlayerState.PLAYING

    def test_state_normal_playing_does_not_touch_stop_issued_at(self):
        """Without a stop in progress, state=PLAYING refreshes _last_playing
        and leaves _stop_issued_at untouched (None)."""
        data = make_coordinator_data(online=True, steam_running={"appId": 570, "name": "Dota 2"})
        player, coordinator, client = _make_player(data)

        assert player._stop_issued_at is None
        state = player.state

        assert state == MediaPlayerState.PLAYING
        assert player._last_playing == {"appId": 570, "name": "Dota 2"}
        assert player._stop_issued_at is None


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
        # 2 games + Big Picture entry
        assert len(result.children) == 3

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
    async def test_empty_games_still_includes_big_picture(self):
        data = make_coordinator_data(steam_games=[])
        player, *_ = _make_player(data)

        result = await player.async_browse_media()

        assert len(result.children) == 1
        assert result.children[0].title == "Steam Big Picture"


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


# ---------------------------------------------------------------------------
# Volume control
# ---------------------------------------------------------------------------

class TestVolumeControl:
    def test_volume_level_returns_normalized_value(self):
        data = make_coordinator_data(volume=75)
        player, *_ = _make_player(data)
        assert player.volume_level == 0.75

    def test_volume_level_returns_zero(self):
        data = make_coordinator_data(volume=0)
        player, *_ = _make_player(data)
        assert player.volume_level == 0.0

    def test_volume_level_returns_one_at_max(self):
        data = make_coordinator_data(volume=100)
        player, *_ = _make_player(data)
        assert player.volume_level == 1.0

    def test_volume_level_none_when_unavailable(self):
        data = make_coordinator_data(volume=None)
        player, *_ = _make_player(data)
        assert player.volume_level is None

    @pytest.mark.asyncio
    async def test_set_volume_level_calls_api(self):
        data = make_coordinator_data(volume=50)
        player, coordinator, client = _make_player(data)

        await player.async_set_volume_level(0.8)

        client.set_volume.assert_awaited_once_with(80)
        assert coordinator.data.volume == 80
        player.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_volume_level_rounds_correctly(self):
        data = make_coordinator_data(volume=50)
        player, coordinator, client = _make_player(data)

        await player.async_set_volume_level(0.555)

        client.set_volume.assert_awaited_once_with(56)
        assert coordinator.data.volume == 56

    def test_supported_features_include_volume_set(self):
        from homeassistant.components.media_player import MediaPlayerEntityFeature
        player, *_ = _make_player()
        assert player._attr_supported_features & MediaPlayerEntityFeature.VOLUME_SET


# ---------------------------------------------------------------------------
# _wake_and_wait (turn_on with sustained wake + health poll)
# ---------------------------------------------------------------------------

class TestWakeAndWait:
    @pytest.mark.asyncio
    async def test_turn_on_sends_sustained_wol_and_waits_for_health(self):
        """turn_on calls _send_wol_sustained, polls health, and starts fast poll."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        # Health succeeds on first poll attempt
        client.get_health = AsyncMock(return_value={"machineName": "TestPC"})

        await player.async_turn_on()

        # WoL sustained sends via async_add_executor_job
        assert coordinator.hass.async_add_executor_job.await_count >= 1
        coordinator.set_power_state.assert_called_once_with(True)
        player.async_write_ha_state.assert_called()
        # Health was polled at least once
        client.get_health.assert_awaited()

    @pytest.mark.asyncio
    async def test_turn_on_shows_buffering_during_wake(self):
        """turn_on sets _wake_target so state=BUFFERING during WoL, clears after."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)

        captured_target = None

        async def capture_wake_target():
            nonlocal captured_target
            captured_target = player._wake_target
            return True

        player._wake_and_wait = capture_wake_target
        client.get_health = AsyncMock(return_value={"machineName": "TestPC"})

        await player.async_turn_on()

        # During _wake_and_wait, wake_target was set (BUFFERING)
        assert captured_target == {"appId": 0, "name": "Waking PC..."}
        # After completion, wake_target is cleared
        assert player._wake_target is None

    @pytest.mark.asyncio
    async def test_turn_on_clears_wake_target_on_failure(self):
        """turn_on clears _wake_target even if _wake_and_wait raises."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)

        async def failing_wake():
            raise CannotConnectError("boom")

        player._wake_and_wait = failing_wake

        with pytest.raises(CannotConnectError):
            await player.async_turn_on()

        assert player._wake_target is None

    @pytest.mark.asyncio
    async def test_turn_on_without_mac_logs_error(self):
        """No MAC configured — error logged, no WoL sent."""
        data = make_coordinator_data(online=False)
        entry = make_mock_entry()
        entry.data = {"host": "192.168.1.100", "port": 5000, "api_key": "key"}
        player, coordinator, client = _make_player(data, entry=entry)

        await player.async_turn_on()

        coordinator.hass.async_add_executor_job.assert_not_awaited()
        coordinator.set_power_state.assert_not_called()
        client.get_health.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_turn_on_returns_true_when_health_succeeds(self):
        """_wake_and_wait returns True when health check passes."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        client.get_health = AsyncMock(return_value={"machineName": "TestPC"})

        result = await player._wake_and_wait()

        assert result is True

    @pytest.mark.asyncio
    async def test_turn_on_returns_false_when_health_never_succeeds(self):
        """_wake_and_wait returns False after 36 failed health polls."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        client.get_health = AsyncMock(side_effect=CannotConnectError("offline"))

        result = await player._wake_and_wait()

        assert result is False
        assert client.get_health.await_count == WAKE_RETRY_COUNT


# ---------------------------------------------------------------------------
# _wait_for_steam_ready retry loop (T10)
# ---------------------------------------------------------------------------

class TestWaitForSteamReady:
    @pytest.mark.asyncio
    async def test_returns_true_when_steam_ready_immediately(self):
        data = make_coordinator_data()
        player, coordinator, client = _make_player(data)
        client.get_system_state = AsyncMock(return_value={"steamReady": True})

        result = await player._wait_for_steam_ready()

        assert result is True
        assert client.get_system_state.await_count == 1

    @pytest.mark.asyncio
    async def test_returns_true_after_retries(self):
        data = make_coordinator_data()
        player, coordinator, client = _make_player(data)
        client.get_system_state = AsyncMock(side_effect=[
            {"steamReady": False},
            {"steamReady": False},
            {"steamReady": True},
        ])

        result = await player._wait_for_steam_ready()

        assert result is True
        assert client.get_system_state.await_count == 3

    @pytest.mark.asyncio
    async def test_returns_false_when_steam_never_ready(self):
        data = make_coordinator_data()
        player, coordinator, client = _make_player(data)
        client.get_system_state = AsyncMock(return_value={"steamReady": False})

        # max_wait=10, interval=5 → 2 iterations
        result = await player._wait_for_steam_ready(max_wait=10, interval=5)

        assert result is False
        assert client.get_system_state.await_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_does_not_abort_loop(self):
        """CannotConnectError is swallowed and retrying continues."""
        data = make_coordinator_data()
        player, coordinator, client = _make_player(data)
        from custom_components.pc_remote.api import CannotConnectError as CCE
        client.get_system_state = AsyncMock(side_effect=[
            CCE("down"),
            {"steamReady": True},
        ])

        result = await player._wait_for_steam_ready()

        assert result is True


# ---------------------------------------------------------------------------
# _wake_and_play retry and exit (T10)
# ---------------------------------------------------------------------------

class TestWakeAndPlay:
    @pytest.mark.asyncio
    async def test_clears_wake_target_when_wake_fails(self):
        """When _wake_and_wait returns False, _wake_target is cleared and steam_run not called."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        player._wake_and_wait = AsyncMock(return_value=False)

        await player._wake_and_play(570, "Dota 2")

        assert player._wake_target is None
        client.steam_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_launches_game_after_successful_wake(self):
        """When wake succeeds and Steam is ready, steam_run is called and running game is set."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        player._wake_and_wait = AsyncMock(return_value=True)
        player._wait_for_steam_ready = AsyncMock(return_value=True)
        client.steam_run = AsyncMock(return_value={"appId": 570, "name": "Dota 2"})

        await player._wake_and_play(570, "Dota 2")

        client.steam_run.assert_awaited_once_with(570)
        assert coordinator.data.steam_running == {"appId": 570, "name": "Dota 2"}
        assert player._wake_target is None

    @pytest.mark.asyncio
    async def test_clears_wake_target_even_when_steam_run_fails(self):
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        player._wake_and_wait = AsyncMock(return_value=True)
        player._wait_for_steam_ready = AsyncMock(return_value=True)
        client.steam_run = AsyncMock(side_effect=CannotConnectError("boom"))

        await player._wake_and_play(570, "Dota 2")

        assert player._wake_target is None


# ---------------------------------------------------------------------------
# Artwork cache miss/hit (T11)
# ---------------------------------------------------------------------------

class TestArtworkCache:
    @pytest.mark.asyncio
    async def test_cache_miss_fetches_and_caches(self):
        """When live fetch succeeds, artwork is cached and returned via async_get_browse_image."""
        data = make_coordinator_data(
            online=True,
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, coordinator, client = _make_player(data)

        image_bytes = b"fakeimage"
        content_type = "image/jpeg"

        player._async_fetch_image = AsyncMock(return_value=(image_bytes, content_type))
        player._cache_artwork = AsyncMock()
        player._get_cached_artwork = AsyncMock(return_value=None)

        result = await player.async_get_browse_image("game", "570")

        assert result == (image_bytes, content_type)
        player._cache_artwork.assert_awaited_once_with("570", image_bytes, content_type)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_without_network_call(self):
        """When live fetch fails but cache exists, cached data is returned."""
        data = make_coordinator_data(
            online=True,
            steam_running={"appId": 570, "name": "Dota 2"},
        )
        player, coordinator, client = _make_player(data)

        cached_bytes = b"cachedimage"
        cached_ct = "image/jpeg"

        player._async_fetch_image = AsyncMock(return_value=(None, None))
        player._cache_artwork = AsyncMock()
        player._get_cached_artwork = AsyncMock(return_value=(cached_bytes, cached_ct))

        result = await player.async_get_browse_image("game", "570")

        assert result == (cached_bytes, cached_ct)
        player._cache_artwork.assert_not_awaited()


# ---------------------------------------------------------------------------
# _handle_coordinator_update and async_will_remove_from_hass (T12)
# ---------------------------------------------------------------------------

class TestCoordinatorUpdateAndRemoval:
    def test_handle_coordinator_update_restores_poll_when_online(self):
        """When fast poll is active and PC comes online, normal poll is restored."""
        data = make_coordinator_data(online=True)
        player, coordinator, client = _make_player(data)
        player._fast_poll_unsub = MagicMock()
        player._restore_normal_poll = MagicMock()

        player._handle_coordinator_update()

        player._restore_normal_poll.assert_called_once()

    def test_handle_coordinator_update_does_not_restore_when_offline(self):
        """When fast poll is active but PC still offline, do not restore."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)
        player._fast_poll_unsub = MagicMock()
        player._restore_normal_poll = MagicMock()

        player._handle_coordinator_update()

        player._restore_normal_poll.assert_not_called()

    def test_handle_coordinator_update_does_nothing_when_no_fast_poll(self):
        """When no fast poll active, normal update still happens."""
        data = make_coordinator_data(online=True)
        player, coordinator, client = _make_player(data)
        player._fast_poll_unsub = None
        player._restore_normal_poll = MagicMock()

        player._handle_coordinator_update()

        player._restore_normal_poll.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_will_remove_cancels_wake_task(self):
        """Pending wake task is cancelled on entity removal."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)

        mock_task = MagicMock()
        mock_task.done.return_value = False
        player._wake_task = mock_task

        await player.async_will_remove_from_hass()

        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_will_remove_cancels_fast_poll_timer(self):
        """Fast poll timer unsubscribe is called on entity removal."""
        data = make_coordinator_data(online=False)
        player, coordinator, client = _make_player(data)

        unsub = MagicMock()
        player._fast_poll_unsub = unsub

        await player.async_will_remove_from_hass()

        unsub.assert_called_once()
        assert player._fast_poll_unsub is None
