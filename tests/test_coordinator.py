"""Tests for custom_components/pc_remote/coordinator.py."""

from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest stubs homeassistant before this import
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

def _make_coordinator(client=None) -> PcRemoteCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    client = client or make_mock_client()
    coord = PcRemoteCoordinator(hass, client, entry_id="entry1")
    return coord


def _full_system_state() -> dict:
    return {
        "audio": {
            "devices": [{"name": "Speakers", "isDefault": True, "volume": 60}],
            "current": "Speakers",
            "volume": 60,
        },
        "monitors": [{"monitorId": "m1", "monitorName": "Dell", "isPrimary": True}],
        "monitorProfiles": [{"name": "Desktop"}, {"name": "Gaming"}],
        "steamGames": [{"appId": 570, "name": "Dota 2"}],
        "runningGame": None,
        "modes": ["Gaming", "Work"],
    }


# ---------------------------------------------------------------------------
# _async_update_data — online path via system state
# ---------------------------------------------------------------------------

class TestUpdateDataOnline:
    @pytest.mark.asyncio
    async def test_successful_poll_populates_data(self):
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "TestPC", "version": "0.9.5"}
        client.get_system_state.return_value = _full_system_state()

        coord = _make_coordinator(client)
        data = await coord._async_update_data()

        assert data.online is True
        assert data.machine_name == "TestPC"
        assert data.volume == 60
        assert data.monitor_profiles == ["Desktop", "Gaming"]
        assert data.modes == ["Gaming", "Work"]
        assert data.steam_games[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_steam_games_cached_when_system_state_has_none(self):
        """If steamGames is empty in the response, the cached list is used."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        state = _full_system_state()
        state["steamGames"] = []
        client.get_system_state.return_value = state

        coord = _make_coordinator(client)
        coord._cached_steam_games = [{"appId": 999, "name": "Cached Game"}]
        data = await coord._async_update_data()

        assert any(g["name"] == "Cached Game" for g in data.steam_games)

    @pytest.mark.asyncio
    async def test_update_interval_is_correct(self):
        coord = _make_coordinator()
        assert coord.update_interval == timedelta(seconds=30)


# ---------------------------------------------------------------------------
# _async_update_data — offline path
# ---------------------------------------------------------------------------

class TestUpdateDataOffline:
    @pytest.mark.asyncio
    async def test_health_failure_marks_offline(self):
        client = make_mock_client()
        client.get_health.side_effect = CannotConnectError("refused")

        coord = _make_coordinator(client)
        coord._cached_steam_games = [{"appId": 570, "name": "Dota 2"}]
        data = await coord._async_update_data()

        assert data.online is False

    @pytest.mark.asyncio
    async def test_offline_data_returns_cached_steam_games(self):
        client = make_mock_client()
        client.get_health.side_effect = CannotConnectError("refused")

        coord = _make_coordinator(client)
        coord._cached_steam_games = [{"appId": 570, "name": "Dota 2"}]
        data = await coord._async_update_data()

        assert data.steam_games[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_invalid_auth_raises_config_entry_auth_failed(self):
        from homeassistant.exceptions import ConfigEntryAuthFailed

        client = make_mock_client()
        client.get_health.side_effect = InvalidAuthError("bad key")

        coord = _make_coordinator(client)
        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()


# ---------------------------------------------------------------------------
# _async_update_data — fallback individual calls
# ---------------------------------------------------------------------------

class TestUpdateDataFallback:
    @pytest.mark.asyncio
    async def test_fallback_used_when_system_state_fails(self):
        """When get_system_state raises, individual endpoints are called."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.side_effect = Exception("not found")
        client.get_audio_devices.return_value = [
            {"name": "Speakers", "isDefault": True, "volume": 42}
        ]
        client.get_monitor_profiles.return_value = [{"name": "Desktop"}]
        client.get_monitors.return_value = []
        client.get_apps.return_value = []
        client.get_steam_games.return_value = [{"appId": 570, "name": "Dota 2"}]
        client.get_steam_running.return_value = None
        client.get_modes.return_value = ["Gaming"]

        coord = _make_coordinator(client)
        data = await coord._async_update_data()

        assert data.online is True
        assert data.volume == 42
        assert data.current_audio_device == "Speakers"
        assert data.monitor_profiles == ["Desktop"]
        assert data.modes == ["Gaming"]

    @pytest.mark.asyncio
    async def test_partial_steam_failure_uses_cache(self):
        """Steam games fallback to cache if get_steam_games raises."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.side_effect = Exception("no state")
        client.get_audio_devices.return_value = []
        client.get_monitor_profiles.return_value = []
        client.get_monitors.return_value = []
        client.get_apps.return_value = []
        client.get_steam_games.side_effect = Exception("steam down")
        client.get_steam_running.return_value = None
        client.get_modes.return_value = []

        coord = _make_coordinator(client)
        coord._cached_steam_games = [{"appId": 999, "name": "Fallback Game"}]
        data = await coord._async_update_data()

        assert data.steam_games[0]["name"] == "Fallback Game"

    @pytest.mark.asyncio
    async def test_monitor_profile_strings_extracted_from_dicts(self):
        """Profiles returned as dicts have their 'name' extracted."""
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.side_effect = Exception("no state")
        client.get_audio_devices.return_value = []
        client.get_monitor_profiles.return_value = [
            {"name": "Desktop"},
            "Gaming",  # plain string should also work
        ]
        client.get_monitors.return_value = []
        client.get_apps.return_value = []
        client.get_steam_games.return_value = []
        client.get_steam_running.return_value = None
        client.get_modes.return_value = []

        coord = _make_coordinator(client)
        data = await coord._async_update_data()

        assert "Desktop" in data.monitor_profiles
        assert "Gaming" in data.monitor_profiles


# ---------------------------------------------------------------------------
# Power override
# ---------------------------------------------------------------------------

class TestPowerOverride:
    @pytest.mark.asyncio
    async def test_power_override_skips_health_check(self):
        client = make_mock_client()
        coord = _make_coordinator(client)
        coord.set_power_state(True)

        data = await coord._async_update_data()

        client.get_health.assert_not_called()
        assert data.online is True

    @pytest.mark.asyncio
    async def test_power_override_expires_and_real_poll_happens(self):
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        client.get_system_state.return_value = _full_system_state()

        coord = _make_coordinator(client)
        # Set override with a timestamp far in the past
        coord._power_override = (True, time.monotonic() - POWER_HOLD_SECONDS - 1)

        data = await coord._async_update_data()

        client.get_health.assert_called_once()
        assert coord._power_override is None

    @pytest.mark.asyncio
    async def test_set_power_state_stores_override(self):
        coord = _make_coordinator()
        coord.set_power_state(False)
        assert coord._power_override is not None
        assert coord._power_override[0] is False


# ---------------------------------------------------------------------------
# Steam cache persistence
# ---------------------------------------------------------------------------

class TestSteamCache:
    @pytest.mark.asyncio
    async def test_async_load_steam_cache_populates_from_store(self):
        coord = _make_coordinator()
        coord._steam_games_store.async_load = AsyncMock(
            return_value=[{"appId": 570, "name": "Dota 2"}]
        )
        await coord.async_load_steam_cache()
        assert coord._cached_steam_games[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_async_load_steam_cache_ignores_non_list(self):
        coord = _make_coordinator()
        coord._steam_games_store.async_load = AsyncMock(return_value=None)
        await coord.async_load_steam_cache()
        assert coord._cached_steam_games == []

    @pytest.mark.asyncio
    async def test_steam_games_saved_after_successful_fetch(self):
        client = make_mock_client()
        client.get_health.return_value = {"machineName": "PC", "version": "1.0"}
        state = _full_system_state()
        state["steamGames"] = [{"appId": 570, "name": "Dota 2"}]
        client.get_system_state.return_value = state

        coord = _make_coordinator(client)
        coord._steam_games_store.async_save = AsyncMock()
        await coord._async_update_data()

        coord._steam_games_store.async_save.assert_called_once()


# ---------------------------------------------------------------------------
# _populate_from_system_state
# ---------------------------------------------------------------------------

class TestPopulateFromSystemState:
    def test_populates_all_fields(self):
        coord = _make_coordinator()
        data = PcRemoteData()
        state = _full_system_state()
        coord._populate_from_system_state(data, state)

        assert data.volume == 60
        assert data.current_audio_device == "Speakers"
        assert data.monitor_profiles == ["Desktop", "Gaming"]
        assert data.steam_games[0]["name"] == "Dota 2"
        assert data.modes == ["Gaming", "Work"]
        assert data.steam_running is None

    def test_handles_empty_state(self):
        coord = _make_coordinator()
        data = PcRemoteData()
        coord._populate_from_system_state(data, {})

        assert data.audio_devices == []
        assert data.monitor_profiles == []
        assert data.steam_games == []
        assert data.modes == []

    def test_running_game_populated(self):
        coord = _make_coordinator()
        data = PcRemoteData()
        state = _full_system_state()
        state["runningGame"] = {"appId": 570, "name": "Dota 2"}
        coord._populate_from_system_state(data, state)

        assert data.steam_running["appId"] == 570
