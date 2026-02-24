"""Tests for custom_components/pc_remote/select.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest stubs homeassistant before this import
from custom_components.pc_remote.api import CannotConnectError
from custom_components.pc_remote.coordinator import PcRemoteData
from custom_components.pc_remote.select import (
    PcRemoteAudioOutputSelect,
    PcRemoteModeSelect,
    PcRemoteMonitorProfileSelect,
    PcRemoteMonitorSoloSelect,
)
from tests.conftest import make_coordinator_data, make_mock_client, make_mock_coordinator, make_mock_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(cls, data=None, client=None, entry=None):
    coordinator = make_mock_coordinator(data)
    coordinator.available = True
    client = client or make_mock_client()
    entry = entry or make_mock_entry()
    entity = cls(coordinator, client, entry)
    return entity, coordinator, client


# ---------------------------------------------------------------------------
# PcRemoteAudioOutputSelect
# ---------------------------------------------------------------------------

class TestAudioOutputSelect:
    def test_options_from_audio_devices(self):
        data = make_coordinator_data(
            audio_devices=[
                {"name": "Speakers", "isDefault": True},
                {"name": "Headphones", "isDefault": False},
            ]
        )
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, data)
        assert entity.options == ["Speakers", "Headphones"]

    def test_options_empty_when_no_devices(self):
        data = make_coordinator_data(audio_devices=[])
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, data)
        assert entity.options == []

    def test_current_option_is_active_device(self):
        data = make_coordinator_data(current_audio_device="Speakers")
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, data)
        assert entity.current_option == "Speakers"

    def test_current_option_none_when_unset(self):
        data = make_coordinator_data(current_audio_device=None)
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, data)
        assert entity.current_option is None

    def test_available_when_online(self):
        data = make_coordinator_data(online=True)
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, data)
        assert entity.available is True

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, data)
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_select_option_calls_api_and_updates_data(self):
        data = make_coordinator_data(
            audio_devices=[{"name": "Headphones", "isDefault": False}]
        )
        entity, coordinator, client = _make_entity(PcRemoteAudioOutputSelect, data)

        await entity.async_select_option("Headphones")

        client.set_audio_device.assert_awaited_once_with("Headphones")
        assert coordinator.data.current_audio_device == "Headphones"

    @pytest.mark.asyncio
    async def test_select_option_propagates_api_error(self):
        data = make_coordinator_data()
        entity, coordinator, client = _make_entity(PcRemoteAudioOutputSelect, data)
        client.set_audio_device.side_effect = CannotConnectError("refused")

        with pytest.raises(CannotConnectError):
            await entity.async_select_option("Headphones")

    def test_unique_id_includes_entry_id(self):
        entry = make_mock_entry(entry_id="abc")
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, entry=entry)
        assert entity._attr_unique_id == "abc_audio_output"


# ---------------------------------------------------------------------------
# PcRemoteMonitorProfileSelect
# ---------------------------------------------------------------------------

class TestMonitorProfileSelect:
    def test_options_from_monitor_profiles(self):
        data = make_coordinator_data(monitor_profiles=["Desktop", "Gaming", "TV"])
        entity, *_ = _make_entity(PcRemoteMonitorProfileSelect, data)
        assert entity.options == ["Desktop", "Gaming", "TV"]

    def test_options_empty_when_no_profiles(self):
        data = make_coordinator_data(monitor_profiles=[])
        entity, *_ = _make_entity(PcRemoteMonitorProfileSelect, data)
        assert entity.options == []

    def test_current_option_none_when_not_persisted(self):
        data = make_coordinator_data(monitor_profiles=["Desktop"], current_monitor_profile=None)
        entity, *_ = _make_entity(PcRemoteMonitorProfileSelect, data)
        assert entity.current_option is None

    def test_current_option_returns_persisted_profile(self):
        data = make_coordinator_data(
            monitor_profiles=["Desktop", "Gaming"],
            current_monitor_profile="Gaming",
        )
        entity, *_ = _make_entity(PcRemoteMonitorProfileSelect, data)
        assert entity.current_option == "Gaming"

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        entity, *_ = _make_entity(PcRemoteMonitorProfileSelect, data)
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_select_option_calls_api_and_persists(self):
        data = make_coordinator_data(monitor_profiles=["Desktop", "Gaming"])
        entity, coordinator, client = _make_entity(PcRemoteMonitorProfileSelect, data)

        await entity.async_select_option("Gaming")

        client.set_monitor_profile.assert_awaited_once_with("Gaming")
        assert coordinator.data.current_monitor_profile == "Gaming"
        coordinator.persist_selection.assert_awaited_once_with("monitor_profile", "Gaming")

    @pytest.mark.asyncio
    async def test_select_option_api_failure_propagates(self):
        data = make_coordinator_data(monitor_profiles=["Desktop"])
        entity, coordinator, client = _make_entity(PcRemoteMonitorProfileSelect, data)
        client.set_monitor_profile.side_effect = CannotConnectError("no conn")

        with pytest.raises(CannotConnectError):
            await entity.async_select_option("Desktop")


# ---------------------------------------------------------------------------
# PcRemoteMonitorSoloSelect
# ---------------------------------------------------------------------------

class TestMonitorSoloSelect:
    def test_options_uses_monitor_name_field(self):
        data = make_coordinator_data(
            monitors=[
                {"monitorId": "m1", "monitorName": "Dell U2723D", "isPrimary": True},
                {"monitorId": "m2", "monitorName": "LG 27UK850", "isPrimary": False},
            ]
        )
        entity, *_ = _make_entity(PcRemoteMonitorSoloSelect, data)
        assert entity.options == ["Dell U2723D", "LG 27UK850"]

    def test_options_falls_back_to_name_field(self):
        data = make_coordinator_data(
            monitors=[{"monitorId": "m1", "name": "Fallback", "isPrimary": True}]
        )
        entity, *_ = _make_entity(PcRemoteMonitorSoloSelect, data)
        assert entity.options == ["Fallback"]

    def test_current_option_is_primary_monitor(self):
        data = make_coordinator_data(
            monitors=[
                {"monitorId": "m1", "monitorName": "Dell", "isPrimary": True},
                {"monitorId": "m2", "monitorName": "LG", "isPrimary": False},
            ]
        )
        entity, *_ = _make_entity(PcRemoteMonitorSoloSelect, data)
        assert entity.current_option == "Dell"

    def test_current_option_none_when_no_primary(self):
        data = make_coordinator_data(
            monitors=[{"monitorId": "m1", "monitorName": "Dell", "isPrimary": False}]
        )
        entity, *_ = _make_entity(PcRemoteMonitorSoloSelect, data)
        assert entity.current_option is None

    def test_current_option_none_when_no_monitors(self):
        data = make_coordinator_data(monitors=[])
        entity, *_ = _make_entity(PcRemoteMonitorSoloSelect, data)
        assert entity.current_option is None

    @pytest.mark.asyncio
    async def test_solo_calls_api_with_monitor_id(self):
        data = make_coordinator_data(
            monitors=[{"monitorId": "m1", "monitorName": "Dell", "isPrimary": True}]
        )
        entity, coordinator, client = _make_entity(PcRemoteMonitorSoloSelect, data)

        await entity.async_select_option("Dell")

        client.solo_monitor.assert_awaited_once_with("m1")
        coordinator.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_solo_does_nothing_for_unknown_monitor(self):
        data = make_coordinator_data(
            monitors=[{"monitorId": "m1", "monitorName": "Dell", "isPrimary": True}]
        )
        entity, coordinator, client = _make_entity(PcRemoteMonitorSoloSelect, data)

        await entity.async_select_option("Unknown Monitor")

        client.solo_monitor.assert_not_awaited()
        coordinator.async_request_refresh.assert_not_awaited()

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        entity, *_ = _make_entity(PcRemoteMonitorSoloSelect, data)
        assert entity.available is False


# ---------------------------------------------------------------------------
# PcRemoteModeSelect
# ---------------------------------------------------------------------------

class TestModeSelect:
    def test_options_from_modes(self):
        data = make_coordinator_data(modes=["Gaming", "Work", "TV"])
        entity, *_ = _make_entity(PcRemoteModeSelect, data)
        assert entity.options == ["Gaming", "Work", "TV"]

    def test_options_empty_when_no_modes(self):
        data = make_coordinator_data(modes=[])
        entity, *_ = _make_entity(PcRemoteModeSelect, data)
        assert entity.options == []

    def test_current_option_none_initially(self):
        data = make_coordinator_data(modes=["Gaming"])
        entity, *_ = _make_entity(PcRemoteModeSelect, data)
        assert entity.current_option is None

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        entity, *_ = _make_entity(PcRemoteModeSelect, data)
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_select_option_calls_api_and_persists_mode(self):
        data = make_coordinator_data(modes=["Gaming", "Work"])
        entity, coordinator, client = _make_entity(PcRemoteModeSelect, data)

        await entity.async_select_option("Gaming")

        client.set_mode.assert_awaited_once_with("Gaming")
        assert coordinator.data.current_mode == "Gaming"
        coordinator.persist_selection.assert_awaited_once_with("mode", "Gaming")

    @pytest.mark.asyncio
    async def test_select_option_updates_current_mode(self):
        data = make_coordinator_data(modes=["Gaming", "Work"])
        entity, coordinator, client = _make_entity(PcRemoteModeSelect, data)

        await entity.async_select_option("Work")
        assert coordinator.data.current_mode == "Work"

        await entity.async_select_option("Gaming")
        assert coordinator.data.current_mode == "Gaming"

    @pytest.mark.asyncio
    async def test_select_option_api_failure_propagates(self):
        data = make_coordinator_data(modes=["Gaming"])
        entity, coordinator, client = _make_entity(PcRemoteModeSelect, data)
        client.set_mode.side_effect = CannotConnectError("refused")

        with pytest.raises(CannotConnectError):
            await entity.async_select_option("Gaming")

    def test_unique_id_includes_entry_id(self):
        entry = make_mock_entry(entry_id="xyz")
        entity, *_ = _make_entity(PcRemoteModeSelect, entry=entry)
        assert entity._attr_unique_id == "xyz_pc_mode"
