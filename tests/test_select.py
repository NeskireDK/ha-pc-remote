"""Tests for custom_components/pc_remote/select.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pc_remote.api import CannotConnectError
from custom_components.pc_remote.coordinator import PcRemoteData
from custom_components.pc_remote.select import (
    PcRemoteAudioOutputSelect,
    PcRemoteModeSelect,
    PcRemoteMonitorSoloSelect,
)
from tests.conftest import (
    make_coordinator_data,
    make_mock_client,
    make_mock_coordinator,
    make_mock_entry,
    wire_entity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(cls, data=None, client=None, entry=None):
    coordinator = make_mock_coordinator(data)
    coordinator.available = True
    client = client or make_mock_client()
    entry = entry or make_mock_entry()
    entity = cls(coordinator, client, entry)
    wire_entity(entity, coordinator)
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
    async def test_select_option_auto_wakes(self):
        data = make_coordinator_data(online=False)
        entity, coordinator, client = _make_entity(PcRemoteAudioOutputSelect, data)

        await entity.async_select_option("Headphones")

        coordinator.async_ensure_online.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_select_option_aborts_when_wake_fails(self):
        data = make_coordinator_data(online=False)
        entity, coordinator, client = _make_entity(PcRemoteAudioOutputSelect, data)
        coordinator.async_ensure_online.return_value = False

        await entity.async_select_option("Headphones")

        client.set_audio_device.assert_not_awaited()

    def test_unique_id_includes_entry_id(self):
        entry = make_mock_entry(entry_id="abc")
        entity, *_ = _make_entity(PcRemoteAudioOutputSelect, entry=entry)
        assert entity._attr_unique_id == "abc_audio_output"


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

    @pytest.mark.asyncio
    async def test_solo_auto_wakes(self):
        data = make_coordinator_data(online=False)
        entity, coordinator, client = _make_entity(PcRemoteMonitorSoloSelect, data)

        await entity.async_select_option("Dell")

        coordinator.async_ensure_online.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_solo_aborts_when_wake_fails(self):
        data = make_coordinator_data(
            online=False,
            monitors=[{"monitorId": "m1", "monitorName": "Dell", "isPrimary": True}],
        )
        entity, coordinator, client = _make_entity(PcRemoteMonitorSoloSelect, data)
        coordinator.async_ensure_online.return_value = False

        await entity.async_select_option("Dell")

        client.solo_monitor.assert_not_awaited()


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
    async def test_select_option_auto_wakes(self):
        data = make_coordinator_data(online=False, modes=["Gaming"])
        entity, coordinator, client = _make_entity(PcRemoteModeSelect, data)

        await entity.async_select_option("Gaming")

        coordinator.async_ensure_online.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_select_option_aborts_when_wake_fails(self):
        data = make_coordinator_data(online=False, modes=["Gaming"])
        entity, coordinator, client = _make_entity(PcRemoteModeSelect, data)
        coordinator.async_ensure_online.return_value = False

        await entity.async_select_option("Gaming")

        client.set_mode.assert_not_awaited()

    def test_unique_id_includes_entry_id(self):
        entry = make_mock_entry(entry_id="xyz")
        entity, *_ = _make_entity(PcRemoteModeSelect, entry=entry)
        assert entity._attr_unique_id == "xyz_pc_mode"
