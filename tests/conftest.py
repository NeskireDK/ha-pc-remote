"""Shared fixtures and homeassistant module stubs for pc_remote tests."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub out the entire homeassistant package before any integration import
# ---------------------------------------------------------------------------

def _make_module(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


def _stub_homeassistant() -> None:
    """Register minimal homeassistant stubs so integration modules can be imported."""
    if "homeassistant" in sys.modules:
        return

    # Top-level package
    ha = _make_module("homeassistant")

    # homeassistant.core
    core = _make_module("homeassistant.core")
    core.HomeAssistant = MagicMock  # type: ignore[attr-defined]
    core.callback = lambda f: f  # passthrough decorator

    # homeassistant.exceptions
    exc = _make_module("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        pass

    class HomeAssistantError(Exception):
        pass

    exc.ConfigEntryAuthFailed = ConfigEntryAuthFailed  # type: ignore[attr-defined]
    exc.HomeAssistantError = HomeAssistantError  # type: ignore[attr-defined]

    # homeassistant.const
    const = _make_module("homeassistant.const")

    class Platform:
        MEDIA_PLAYER = "media_player"
        NUMBER = "number"
        SELECT = "select"
        SWITCH = "switch"

    const.Platform = Platform  # type: ignore[attr-defined]

    # homeassistant.config_entries
    ce = _make_module("homeassistant.config_entries")
    ce.ConfigEntry = MagicMock  # type: ignore[attr-defined]

    # homeassistant.helpers
    helpers = _make_module("homeassistant.helpers")

    helpers_update = _make_module("homeassistant.helpers.update_coordinator")

    from typing import Generic, TypeVar
    _T = TypeVar("_T")

    class DataUpdateCoordinator(Generic[_T]):
        def __init__(self, hass, logger, *, name, update_interval):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None
            self._listeners: list = []

        async def async_request_refresh(self):
            pass

        async def async_refresh(self):
            pass

        def __class_getitem__(cls, item):
            return cls

    class UpdateFailed(Exception):
        pass

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self) -> bool:
            return True

        def async_write_ha_state(self):
            pass

        @property
        def hass(self):
            return self.coordinator.hass

        def __class_getitem__(cls, item):
            return cls

    helpers_update.DataUpdateCoordinator = DataUpdateCoordinator  # type: ignore[attr-defined]
    helpers_update.UpdateFailed = UpdateFailed  # type: ignore[attr-defined]
    helpers_update.CoordinatorEntity = CoordinatorEntity  # type: ignore[attr-defined]

    helpers_device = _make_module("homeassistant.helpers.device_registry")

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    helpers_device.DeviceInfo = DeviceInfo  # type: ignore[attr-defined]

    helpers_entity = _make_module("homeassistant.helpers.entity_platform")
    helpers_entity.AddEntitiesCallback = MagicMock  # type: ignore[attr-defined]

    helpers_aiohttp = _make_module("homeassistant.helpers.aiohttp_client")
    helpers_aiohttp.async_get_clientsession = MagicMock()  # type: ignore[attr-defined]

    helpers_storage = _make_module("homeassistant.helpers.storage")

    class Store:
        def __init__(self, hass, version, key):
            self._data = None

        async def async_load(self):
            return self._data

        async def async_save(self, data):
            self._data = data

    helpers_storage.Store = Store  # type: ignore[attr-defined]

    # homeassistant.components
    components = _make_module("homeassistant.components")

    # media_player
    mp = _make_module("homeassistant.components.media_player")

    class MediaPlayerEntity:
        pass

    class MediaPlayerEntityFeature:
        SELECT_SOURCE = 1
        STOP = 2
        PLAY = 4
        PAUSE = 8

    class MediaPlayerState:
        PLAYING = "playing"
        IDLE = "idle"
        OFF = "off"
        BUFFERING = "buffering"

    mp.MediaPlayerEntity = MediaPlayerEntity  # type: ignore[attr-defined]
    mp.MediaPlayerEntityFeature = MediaPlayerEntityFeature  # type: ignore[attr-defined]
    mp.MediaPlayerState = MediaPlayerState  # type: ignore[attr-defined]

    # select
    sel = _make_module("homeassistant.components.select")

    class SelectEntity:
        pass

    sel.SelectEntity = SelectEntity  # type: ignore[attr-defined]

    # switch
    sw = _make_module("homeassistant.components.switch")

    class SwitchEntity:
        pass

    class SwitchDeviceClass:
        SWITCH = "switch"

    sw.SwitchEntity = SwitchEntity  # type: ignore[attr-defined]
    sw.SwitchDeviceClass = SwitchDeviceClass  # type: ignore[attr-defined]

    # number
    num = _make_module("homeassistant.components.number")

    class NumberEntity:
        pass

    num.NumberEntity = NumberEntity  # type: ignore[attr-defined]

    # wakeonlan stub
    wol = _make_module("wakeonlan")
    wol.send_magic_packet = MagicMock()  # type: ignore[attr-defined]


_stub_homeassistant()

# ---------------------------------------------------------------------------
# Now we can safely import integration modules
# ---------------------------------------------------------------------------
from custom_components.pc_remote.api import (  # noqa: E402
    CannotConnectError,
    InvalidAuthError,
    PcRemoteClient,
)
from custom_components.pc_remote.coordinator import (  # noqa: E402
    PcRemoteCoordinator,
    PcRemoteData,
)


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
