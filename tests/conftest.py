"""Shared fixtures and helpers for pc_remote tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.pc_remote.api import (
    CannotConnectError,
    InvalidAuthError,
    PcRemoteClient,
)
from custom_components.pc_remote.coordinator import (
    PcRemoteCoordinator,
    PcRemoteData,
)


# ---------------------------------------------------------------------------
# Mock Store — replaces homeassistant.helpers.storage.Store in tests
# ---------------------------------------------------------------------------

class MockStore:
    """Simple in-memory Store replacement for tests."""

    def __init__(self, hass, version, key):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


@pytest.fixture(autouse=True)
def _mock_store():
    """Replace Store with an in-memory implementation for all tests."""
    with patch("custom_components.pc_remote.coordinator.Store", MockStore):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_coordinator_data(**kwargs) -> PcRemoteData:
    """Return a PcRemoteData with sensible defaults, overridable via kwargs."""
    defaults = dict(
        online=True,
        machine_name="TestPC",
        service_version="0.9.5",
        audio_devices=[
            {"name": "Speakers", "isDefault": True, "volume": 50},
            {"name": "Headphones", "isDefault": False, "volume": 70},
        ],
        current_audio_device="Speakers",
        volume=50,
        monitor_profiles=["Desktop", "Gaming", "TV"],
        monitors=[
            {"monitorId": "mon1", "monitorName": "Dell U2723D", "isPrimary": True},
            {"monitorId": "mon2", "monitorName": "LG 27UK850", "isPrimary": False},
        ],
        apps=[
            {"key": "chrome", "displayName": "Chrome", "isRunning": False},
        ],
        steam_games=[
            {"appId": 1091500, "name": "Cyberpunk 2077"},
            {"appId": 570, "name": "Dota 2"},
        ],
        steam_running=None,
        modes=["Gaming", "Work", "TV"],
        current_mode=None,
        current_monitor_profile=None,
        idle_seconds=30,
    )
    defaults.update(kwargs)
    return PcRemoteData(**defaults)


def make_mock_coordinator(data: PcRemoteData | None = None) -> MagicMock:
    """Return a mock coordinator with the given data."""
    coordinator = MagicMock()
    coordinator.data = data or make_coordinator_data()
    coordinator.hass = MagicMock()
    coordinator.hass.async_add_executor_job = AsyncMock()
    coordinator.hass.async_create_task = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.persist_selection = AsyncMock()
    coordinator.available = True
    return coordinator


def make_mock_entry(entry_id: str = "test_entry_id", **data_kwargs) -> MagicMock:
    """Return a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "host": "192.168.1.100",
        "port": 5000,
        "api_key": "test-api-key",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        **data_kwargs,
    }
    return entry


def make_mock_client() -> MagicMock:
    """Return a mock PcRemoteClient."""
    client = MagicMock(spec=PcRemoteClient)
    client.get_health = AsyncMock(return_value={"machineName": "TestPC", "version": "0.9.5"})
    client.get_system_state = AsyncMock(return_value={})
    client.get_audio_devices = AsyncMock(return_value=[])
    client.set_audio_device = AsyncMock()
    client.set_volume = AsyncMock()
    client.get_monitor_profiles = AsyncMock(return_value=[])
    client.set_monitor_profile = AsyncMock()
    client.get_monitors = AsyncMock(return_value=[])
    client.solo_monitor = AsyncMock()
    client.get_apps = AsyncMock(return_value=[])
    client.launch_app = AsyncMock()
    client.kill_app = AsyncMock()
    client.get_steam_games = AsyncMock(return_value=[])
    client.get_steam_running = AsyncMock(return_value=None)
    client.steam_run = AsyncMock(return_value=None)
    client.steam_stop = AsyncMock()
    client.get_modes = AsyncMock(return_value=[])
    client.set_mode = AsyncMock()
    client.sleep = AsyncMock()
    client.test_connection = AsyncMock(return_value=True)
    return client


def wire_entity(entity, coordinator) -> None:
    """Wire an entity to a mock coordinator for testing outside HA."""
    entity.hass = coordinator.hass
    entity.async_write_ha_state = MagicMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def coordinator_data() -> PcRemoteData:
    return make_coordinator_data()


@pytest.fixture
def mock_coordinator(coordinator_data) -> MagicMock:
    return make_mock_coordinator(coordinator_data)


@pytest.fixture
def mock_entry() -> MagicMock:
    return make_mock_entry()


@pytest.fixture
def mock_client() -> MagicMock:
    return make_mock_client()
