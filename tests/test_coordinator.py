"""Tests for custom_components/pc_remote/coordinator.py."""

from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pc_remote.api import CannotConnectError, InvalidAuthError
from custom_components.pc_remote.coordinator import (
    POWER_HOLD_SECONDS,
    PcRemoteCoordinator,
    PcRemoteData,
)
from tests.conftest import make_mock_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_coordinator(hass, client=None) -> PcRemoteCoordinator:
    client = client or make_mock_client()
    return PcRemoteCoordinator(hass, client, entry_id="entry1")


def _full_system_state() -> dict:
    return {
        "audio": {
            "devices": [{"name": "Speakers", "isDefault": True, "volume": 60}],
            "current": "Speakers",
            "volume": 60,
        },
        "monitors": [{"monitorId": "m1", "monitorName": "Dell", "isPrimary": True}],
        "steamGames": [{"appId": 570, "name": "Dota 2"}],
        "runningGame": None,
        "modes": ["Gaming", "Work"],
    }


# ---------------------------------------------------------------------------
# _async_update_data — online path via system state
# ---------------------------------------------------------------------------

class TestUpdateDataOnline:
    @pytest.mark.asyncio
    async def test_successful_poll_populates_data(self, hass):
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "TestPC", "version": "0.9.5"}
        client.get_system_state.return_value = _full_system_state()

        coord = _make_coordinator(hass, client)
        data = await coord._async_update_data()

        assert data.online is True
        assert data.machine_name == "TestPC"
        assert data.volume == 60
        assert data.modes == ["Gaming", "Work"]
        assert data.steam_games[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_steam_games_cached_when_system_state_has_none(self, hass):
        """If steamGames is empty in the response, the cached list is used."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        state = _full_system_state()
        state["steamGames"] = []
        client.get_system_state.return_value = state

        coord = _make_coordinator(hass, client)
        coord._cached_steam_games = [{"appId": 999, "name": "Cached Game"}]
        data = await coord._async_update_data()

        assert any(g["name"] == "Cached Game" for g in data.steam_games)

    @pytest.mark.asyncio
    async def test_update_interval_is_correct(self, hass):
        coord = _make_coordinator(hass)
        assert coord.update_interval == timedelta(seconds=30)


# ---------------------------------------------------------------------------
# _async_update_data — offline path
# ---------------------------------------------------------------------------

class TestUpdateDataOffline:
    @pytest.mark.asyncio
    async def test_health_failure_marks_offline(self, hass):
        client = make_mock_client()
        client.get_health.side_effect = CannotConnectError("refused")

        coord = _make_coordinator(hass, client)
        coord._cached_steam_games = [{"appId": 570, "name": "Dota 2"}]
        data = await coord._async_update_data()

        assert data.online is False

    @pytest.mark.asyncio
    async def test_offline_data_returns_cached_steam_games(self, hass):
        client = make_mock_client()
        client.get_health.side_effect = CannotConnectError("refused")

        coord = _make_coordinator(hass, client)
        coord._cached_steam_games = [{"appId": 570, "name": "Dota 2"}]
        data = await coord._async_update_data()

        assert data.steam_games[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_invalid_auth_raises_config_entry_auth_failed(self, hass):
        from homeassistant.exceptions import ConfigEntryAuthFailed

        client = make_mock_client()
        client.get_health.side_effect = InvalidAuthError("bad key")

        coord = _make_coordinator(hass, client)
        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()


# ---------------------------------------------------------------------------
# _async_update_data — fallback individual calls
# ---------------------------------------------------------------------------

class TestUpdateDataFallback:
    @pytest.mark.asyncio
    async def test_fallback_used_when_system_state_fails(self, hass):
        """When get_system_state raises, individual endpoints are called."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.side_effect = Exception("not found")
        client.get_audio_devices.return_value = [
            {"name": "Speakers", "isDefault": True, "volume": 42}
        ]
        client.get_monitors.return_value = []
        client.get_apps.return_value = []
        client.get_steam_games.return_value = [{"appId": 570, "name": "Dota 2"}]
        client.get_steam_running.return_value = None
        client.get_modes.return_value = ["Gaming"]

        coord = _make_coordinator(hass, client)
        data = await coord._async_update_data()

        assert data.online is True
        assert data.volume == 42
        assert data.current_audio_device == "Speakers"
        assert data.modes == ["Gaming"]

    @pytest.mark.asyncio
    async def test_partial_steam_failure_uses_cache(self, hass):
        """Steam games fallback to cache if get_steam_games raises."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.side_effect = Exception("no state")
        client.get_audio_devices.return_value = []
        client.get_monitors.return_value = []
        client.get_apps.return_value = []
        client.get_steam_games.side_effect = Exception("steam down")
        client.get_steam_running.return_value = None
        client.get_modes.return_value = []

        coord = _make_coordinator(hass, client)
        coord._cached_steam_games = [{"appId": 999, "name": "Fallback Game"}]
        data = await coord._async_update_data()

        assert data.steam_games[0]["name"] == "Fallback Game"



# ---------------------------------------------------------------------------
# Power override
# ---------------------------------------------------------------------------

class TestPowerOverride:
    @pytest.mark.asyncio
    async def test_power_override_skips_health_check(self, hass):
        client = make_mock_client()
        coord = _make_coordinator(hass, client)
        coord.set_power_state(True)

        data = await coord._async_update_data()

        client.get_health.assert_not_called()
        assert data.online is True

    @pytest.mark.asyncio
    async def test_power_override_expires_and_real_poll_happens(self, hass):
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.return_value = _full_system_state()

        coord = _make_coordinator(hass, client)
        # Set override with a timestamp far in the past
        coord._power_override = (True, time.monotonic() - POWER_HOLD_SECONDS - 1)

        data = await coord._async_update_data()

        client.get_health.assert_called_once()
        assert coord._power_override is None

    @pytest.mark.asyncio
    async def test_set_power_state_stores_override(self, hass):
        coord = _make_coordinator(hass)
        coord.set_power_state(False)
        assert coord._power_override is not None
        assert coord._power_override[0] is False


# ---------------------------------------------------------------------------
# Steam cache persistence
# ---------------------------------------------------------------------------

class TestSteamCache:
    @pytest.mark.asyncio
    async def test_async_load_steam_cache_populates_from_store(self, hass):
        coord = _make_coordinator(hass)
        coord._steam_games_store._data = [{"appId": 570, "name": "Dota 2"}]
        await coord.async_load_steam_cache()
        assert coord._cached_steam_games[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_async_load_steam_cache_ignores_non_list(self, hass):
        coord = _make_coordinator(hass)
        await coord.async_load_steam_cache()
        assert coord._cached_steam_games == []

    @pytest.mark.asyncio
    async def test_steam_games_saved_after_successful_fetch(self, hass):
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        state = _full_system_state()
        state["steamGames"] = [{"appId": 570, "name": "Dota 2"}]
        client.get_system_state.return_value = state

        coord = _make_coordinator(hass, client)
        await coord._async_update_data()

        saved = coord._steam_games_store._data
        assert saved is not None
        assert saved[0]["name"] == "Dota 2"


# ---------------------------------------------------------------------------
# _populate_from_system_state
# ---------------------------------------------------------------------------

class TestPopulateFromSystemState:
    @pytest.mark.asyncio
    async def test_populates_all_fields(self, hass):
        coord = _make_coordinator(hass)
        data = PcRemoteData()
        state = _full_system_state()
        coord._populate_from_system_state(data, state)

        assert data.volume == 60
        assert data.current_audio_device == "Speakers"
        assert data.steam_games[0]["name"] == "Dota 2"
        assert data.modes == ["Gaming", "Work"]
        assert data.steam_running is None

    @pytest.mark.asyncio
    async def test_handles_empty_state(self, hass):
        coord = _make_coordinator(hass)
        data = PcRemoteData()
        coord._populate_from_system_state(data, {})

        assert data.audio_devices == []
        assert data.steam_games == []
        assert data.modes == []

    @pytest.mark.asyncio
    async def test_running_game_populated(self, hass):
        coord = _make_coordinator(hass)
        data = PcRemoteData()
        state = _full_system_state()
        state["runningGame"] = {"appId": 570, "name": "Dota 2"}
        coord._populate_from_system_state(data, state)

        assert data.steam_running["appId"] == 570


# ---------------------------------------------------------------------------
# Selection persistence
# ---------------------------------------------------------------------------

class TestSelectionPersistence:
    @pytest.mark.asyncio
    async def test_load_selections_returns_dict_from_store(self, hass):
        coord = _make_coordinator(hass)
        coord._selections_store._data = {"mode": "Gaming"}
        result = await coord.load_selections()
        assert result == {"mode": "Gaming"}

    @pytest.mark.asyncio
    async def test_load_selections_returns_empty_dict_when_no_data(self, hass):
        coord = _make_coordinator(hass)
        result = await coord.load_selections()
        assert result == {}

    @pytest.mark.asyncio
    async def test_persist_selection_saves_to_store(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "Work")
        stored = await coord._selections_store.async_load()
        assert stored == {"mode": "Work"}

    @pytest.mark.asyncio
    async def test_persist_selection_merges_with_existing(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "Work")
        await coord.persist_selection("mode", "Gaming")
        stored = await coord._selections_store.async_load()
        assert stored == {"mode": "Gaming"}

    @pytest.mark.asyncio
    async def test_persist_selection_can_clear_value(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "Work")
        await coord.persist_selection("mode", None)
        stored = await coord._selections_store.async_load()
        assert stored["mode"] is None


# ---------------------------------------------------------------------------
# _restore_selections
# ---------------------------------------------------------------------------

class TestRestoreSelections:
    @pytest.mark.asyncio
    async def test_restores_mode_when_in_available_list(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "Gaming")
        data = PcRemoteData(modes=["Gaming", "Work"])
        await coord._restore_selections(data)
        assert data.current_mode == "Gaming"

    @pytest.mark.asyncio
    async def test_clears_mode_when_not_in_available_list(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "Removed")
        data = PcRemoteData(modes=["Gaming", "Work"])
        await coord._restore_selections(data)
        assert data.current_mode is None

    @pytest.mark.asyncio
    async def test_audio_change_clears_persisted_mode(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "TV")
        coord._prev_audio_device = "Speakers"

        data = PcRemoteData(
            modes=["TV", "Gaming"],
            current_audio_device="Headphones",
        )
        await coord._restore_selections(data)

        assert data.current_mode is None
        stored = await coord._selections_store.async_load()
        assert stored["mode"] is None

    @pytest.mark.asyncio
    async def test_audio_unchanged_keeps_persisted_mode(self, hass):
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "TV")
        coord._prev_audio_device = "Speakers"

        data = PcRemoteData(
            modes=["TV", "Gaming"],
            current_audio_device="Speakers",
        )
        await coord._restore_selections(data)

        assert data.current_mode == "TV"

    @pytest.mark.asyncio
    async def test_first_poll_does_not_clear_mode(self, hass):
        """On first poll _prev_audio_device is None, should not clear mode."""
        coord = _make_coordinator(hass)
        await coord.persist_selection("mode", "TV")

        data = PcRemoteData(
            modes=["TV", "Gaming"],
            current_audio_device="Speakers",
        )
        await coord._restore_selections(data)

        assert data.current_mode == "TV"
        assert coord._prev_audio_device == "Speakers"

    @pytest.mark.asyncio
    async def test_system_state_path_restores_selections(self, hass):
        """Full _async_update_data via system state restores persisted mode."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.return_value = _full_system_state()

        coord = _make_coordinator(hass, client)
        await coord.persist_selection("mode", "Gaming")

        data = await coord._async_update_data()

        assert data.current_mode == "Gaming"

    @pytest.mark.asyncio
    async def test_fallback_path_restores_selections(self, hass):
        """Full _async_update_data via fallback restores persisted mode."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.side_effect = Exception("no state")
        client.get_audio_devices.return_value = []
        client.get_monitors.return_value = []
        client.get_apps.return_value = []
        client.get_steam_games.return_value = []
        client.get_steam_running.return_value = None
        client.get_modes.return_value = ["Gaming", "Work"]

        coord = _make_coordinator(hass, client)
        await coord.persist_selection("mode", "Gaming")

        data = await coord._async_update_data()

        assert data.current_mode == "Gaming"
