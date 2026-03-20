"""Tests for custom_components/pc_remote/switch.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.pc_remote.api import CannotConnectError
from custom_components.pc_remote.coordinator import PcRemoteData
from custom_components.pc_remote.switch import PcRemoteAppSwitch, PcRemotePowerSwitch
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

def _make_power_switch(data=None, client=None, entry=None):
    data = data or make_coordinator_data()
    coordinator = make_mock_coordinator(data)
    coordinator.available = True
    coordinator.set_power_state = MagicMock()
    client = client or make_mock_client()
    entry = entry or make_mock_entry()
    switch = PcRemotePowerSwitch(coordinator, client, entry)
    wire_entity(switch, coordinator)
    return switch, coordinator, client


def _make_app_switch(app_key="chrome", display_name="Chrome", data=None, client=None, entry=None):
    data = data or make_coordinator_data()
    coordinator = make_mock_coordinator(data)
    coordinator.available = True
    client = client or make_mock_client()
    entry = entry or make_mock_entry()
    switch = PcRemoteAppSwitch(coordinator, client, entry, app_key, display_name)
    wire_entity(switch, coordinator)
    return switch, coordinator, client


# ---------------------------------------------------------------------------
# PcRemotePowerSwitch — state
# ---------------------------------------------------------------------------

class TestPowerSwitchState:
    def test_is_on_when_online(self):
        data = make_coordinator_data(online=True)
        switch, *_ = _make_power_switch(data)
        assert switch.is_on is True

    def test_is_off_when_offline(self):
        data = make_coordinator_data(online=False)
        switch, *_ = _make_power_switch(data)
        assert switch.is_on is False

    def test_always_available(self):
        data = make_coordinator_data(online=False)
        switch, *_ = _make_power_switch(data)
        assert switch.available is True

    def test_unique_id_includes_entry_id(self):
        entry = make_mock_entry(entry_id="abc")
        switch, *_ = _make_power_switch(entry=entry)
        assert switch._attr_unique_id == "abc_power"


# ---------------------------------------------------------------------------
# PcRemotePowerSwitch — turn on (Wake-on-LAN)
# ---------------------------------------------------------------------------

class TestPowerSwitchTurnOn:
    @pytest.mark.asyncio
    async def test_turn_on_sends_wol_and_sets_power_state(self):
        entry = make_mock_entry(mac_address="AA:BB:CC:DD:EE:FF")
        data = make_coordinator_data(online=False)
        switch, coordinator, client = _make_power_switch(data=data, entry=entry)

        await switch.async_turn_on()

        coordinator.hass.async_add_executor_job.assert_awaited_once()
        coordinator.set_power_state.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_on_no_mac_does_nothing(self):
        entry = make_mock_entry(mac_address="")
        # Override data dict to clear mac
        entry.data = {"host": "host", "port": 5000, "api_key": "k", "mac_address": ""}
        data = make_coordinator_data(online=False)
        switch, coordinator, client = _make_power_switch(data=data, entry=entry)

        await switch.async_turn_on()

        coordinator.hass.async_add_executor_job.assert_not_awaited()
        coordinator.set_power_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_wol_os_error_does_not_propagate(self):
        entry = make_mock_entry(mac_address="AA:BB:CC:DD:EE:FF")
        data = make_coordinator_data(online=False)
        switch, coordinator, client = _make_power_switch(data=data, entry=entry)
        coordinator.hass.async_add_executor_job.side_effect = OSError("network error")

        # Should not raise
        await switch.async_turn_on()

        coordinator.set_power_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_wol_value_error_does_not_propagate(self):
        entry = make_mock_entry(mac_address="INVALID")
        data = make_coordinator_data(online=False)
        switch, coordinator, client = _make_power_switch(data=data, entry=entry)
        coordinator.hass.async_add_executor_job.side_effect = ValueError("bad mac")

        await switch.async_turn_on()

        coordinator.set_power_state.assert_not_called()


# ---------------------------------------------------------------------------
# PcRemotePowerSwitch — turn off (sleep)
# ---------------------------------------------------------------------------

class TestPowerSwitchTurnOff:
    @pytest.mark.asyncio
    async def test_turn_off_calls_sleep_and_sets_power_state(self):
        data = make_coordinator_data(online=True)
        switch, coordinator, client = _make_power_switch(data)

        await switch.async_turn_off()

        client.sleep.assert_awaited_once()
        coordinator.set_power_state.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_turn_off_swallows_cannot_connect(self):
        data = make_coordinator_data(online=True)
        switch, coordinator, client = _make_power_switch(data)
        client.sleep.side_effect = CannotConnectError("refused")

        await switch.async_turn_off()  # must not raise

        coordinator.set_power_state.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# PcRemoteAppSwitch — state
# ---------------------------------------------------------------------------

class TestAppSwitchState:
    def test_is_on_when_app_running(self):
        data = make_coordinator_data(
            online=True,
            apps=[{"key": "chrome", "displayName": "Chrome", "isRunning": True}],
        )
        switch, *_ = _make_app_switch("chrome", "Chrome", data)
        assert switch.is_on is True

    def test_is_off_when_app_not_running(self):
        data = make_coordinator_data(
            online=True,
            apps=[{"key": "chrome", "displayName": "Chrome", "isRunning": False}],
        )
        switch, *_ = _make_app_switch("chrome", "Chrome", data)
        assert switch.is_on is False

    def test_is_none_when_app_key_not_found(self):
        data = make_coordinator_data(apps=[])
        switch, *_ = _make_app_switch("unknown_app", "Unknown", data)
        assert switch.is_on is None

    def test_unique_id_includes_entry_id_and_key(self):
        entry = make_mock_entry(entry_id="myentry")
        switch, *_ = _make_app_switch("steam", "Steam", entry=entry)
        assert switch._attr_unique_id == "myentry_app_steam"

    def test_name_is_display_name(self):
        switch, *_ = _make_app_switch("chrome", "Google Chrome")
        assert switch._attr_name == "Google Chrome"


# ---------------------------------------------------------------------------
# PcRemoteAppSwitch — commands
# ---------------------------------------------------------------------------

class TestAppSwitchCommands:
    @pytest.mark.asyncio
    async def test_turn_on_launches_app(self):
        data = make_coordinator_data(online=True, apps=[])
        switch, coordinator, client = _make_app_switch("chrome", "Chrome", data)

        await switch.async_turn_on()

        client.launch_app.assert_awaited_once_with("chrome")
        coordinator.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_turn_on_auto_wakes_when_offline(self):
        data = make_coordinator_data(online=False, apps=[])
        switch, coordinator, client = _make_app_switch("chrome", "Chrome", data)

        await switch.async_turn_on()

        coordinator.async_ensure_online.assert_awaited_once()
        client.launch_app.assert_awaited_once_with("chrome")

    @pytest.mark.asyncio
    async def test_turn_on_aborts_when_wake_fails(self):
        data = make_coordinator_data(online=False, apps=[])
        switch, coordinator, client = _make_app_switch("chrome", "Chrome", data)
        coordinator.async_ensure_online.return_value = False

        await switch.async_turn_on()

        client.launch_app.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_turn_off_kills_app(self):
        data = make_coordinator_data(online=True, apps=[])
        switch, coordinator, client = _make_app_switch("chrome", "Chrome", data)

        await switch.async_turn_off()

        client.kill_app.assert_awaited_once_with("chrome")
        coordinator.async_request_refresh.assert_awaited_once()
