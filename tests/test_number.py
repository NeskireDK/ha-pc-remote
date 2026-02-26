"""Tests for custom_components/pc_remote/number.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.pc_remote.coordinator import PcRemoteData
from custom_components.pc_remote.number import (
    PcRemoteAutoSleepNumber,
    PcRemoteVolumeNumber,
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
# PcRemoteVolumeNumber
# ---------------------------------------------------------------------------

class TestVolumeNumber:
    def test_unique_id(self):
        entry = make_mock_entry(entry_id="entry_abc")
        entity, *_ = _make_entity(PcRemoteVolumeNumber, entry=entry)
        assert entity.unique_id == "entry_abc_volume"

    def test_translation_key(self):
        entity, *_ = _make_entity(PcRemoteVolumeNumber)
        assert entity.translation_key == "volume"

    def test_native_value_returns_volume(self):
        data = make_coordinator_data(volume=75)
        entity, *_ = _make_entity(PcRemoteVolumeNumber, data)
        assert entity.native_value == 75

    def test_native_value_none_when_unset(self):
        data = make_coordinator_data(volume=None)
        entity, *_ = _make_entity(PcRemoteVolumeNumber, data)
        assert entity.native_value is None

    def test_available_when_online(self):
        data = make_coordinator_data(online=True)
        entity, *_ = _make_entity(PcRemoteVolumeNumber, data)
        assert entity.available is True

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        entity, *_ = _make_entity(PcRemoteVolumeNumber, data)
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_set_native_value_calls_client_and_updates_data(self):
        data = make_coordinator_data(volume=50)
        entity, coordinator, client = _make_entity(PcRemoteVolumeNumber, data)
        await entity.async_set_native_value(80.0)
        client.set_volume.assert_awaited_once_with(80)
        assert coordinator.data.volume == 80
        entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# PcRemoteAutoSleepNumber
# ---------------------------------------------------------------------------

class TestAutoSleepNumber:
    def test_unique_id(self):
        entry = make_mock_entry(entry_id="entry_abc")
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber, entry=entry)
        assert entity.unique_id == "entry_abc_auto_sleep"

    def test_translation_key(self):
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber)
        assert entity.translation_key == "auto_sleep"

    def test_icon(self):
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber)
        assert entity.icon == "mdi:sleep"

    def test_min_max_step(self):
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber)
        assert entity.native_min_value == 0
        assert entity.native_max_value == 480
        assert entity.native_step == 1

    def test_unit_of_measurement(self):
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber)
        assert entity.native_unit_of_measurement == "min"

    def test_native_value_returns_auto_sleep_minutes(self):
        data = make_coordinator_data(auto_sleep_minutes=45)
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber, data)
        assert entity.native_value == 45

    def test_native_value_none_when_unset(self):
        data = make_coordinator_data(auto_sleep_minutes=None)
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber, data)
        assert entity.native_value is None

    def test_available_when_online(self):
        data = make_coordinator_data(online=True)
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber, data)
        assert entity.available is True

    def test_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        entity, *_ = _make_entity(PcRemoteAutoSleepNumber, data)
        assert entity.available is False

    @pytest.mark.asyncio
    async def test_set_native_value_calls_client_and_updates_data(self):
        data = make_coordinator_data(auto_sleep_minutes=30)
        entity, coordinator, client = _make_entity(PcRemoteAutoSleepNumber, data)
        await entity.async_set_native_value(60.0)
        client.set_power_config.assert_awaited_once_with(60)
        assert coordinator.data.auto_sleep_minutes == 60
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_native_value_zero_disables_auto_sleep(self):
        data = make_coordinator_data(auto_sleep_minutes=30)
        entity, coordinator, client = _make_entity(PcRemoteAutoSleepNumber, data)
        await entity.async_set_native_value(0.0)
        client.set_power_config.assert_awaited_once_with(0)
        assert coordinator.data.auto_sleep_minutes == 0
