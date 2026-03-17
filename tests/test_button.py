"""Tests for custom_components/pc_remote/button.py."""

from __future__ import annotations

import pytest

from custom_components.pc_remote.button import PcRemoteUpdateButton
from tests.conftest import (
    make_coordinator_data,
    make_mock_client,
    make_mock_coordinator,
    make_mock_entry,
    wire_entity,
)


class TestUpdateButton:
    """Tests for PcRemoteUpdateButton."""

    def _make_button(self, data=None, client=None, entry=None):
        coordinator = make_mock_coordinator(data)
        coordinator.available = True
        client = client or make_mock_client()
        entry = entry or make_mock_entry()
        button = PcRemoteUpdateButton(coordinator, client, entry)
        wire_entity(button, coordinator)
        return button, coordinator, client

    @pytest.mark.asyncio
    async def test_update_button_calls_api(self):
        button, _, client = self._make_button()
        await button.async_press()
        client.trigger_update.assert_awaited_once()

    def test_update_button_unavailable_when_offline(self):
        data = make_coordinator_data(online=False)
        button, _, _ = self._make_button(data=data)
        assert button.available is False

    def test_update_button_available_when_online(self):
        data = make_coordinator_data(online=True)
        button, _, _ = self._make_button(data=data)
        assert button.available is True

    def test_unique_id(self):
        entry = make_mock_entry(entry_id="abc")
        button, _, _ = self._make_button(entry=entry)
        assert button._attr_unique_id == "abc_check_update"

    def test_entity_category_is_config(self):
        from homeassistant.const import EntityCategory
        button, _, _ = self._make_button()
        assert button.entity_category == EntityCategory.CONFIG
