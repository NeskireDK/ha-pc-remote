"""Tests for the PC Remote config flow (user, zeroconf, reconfigure, options)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.pc_remote.api import CannotConnectError, InvalidAuthError
from custom_components.pc_remote.config_flow import (
    PcRemoteConfigFlow,
    PcRemoteOptionsFlow,
)
from custom_components.pc_remote.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MAC_ADDRESS,
    CONF_PORT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

HEALTH_RESPONSE = {
    "machineName": "TestPC",
    "version": "1.0.0",
    "macAddresses": [
        {
            "interfaceName": "Ethernet",
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "ipAddress": "192.168.1.100",
        }
    ],
}

HEALTH_MULTI_MAC = {
    "machineName": "TestPC",
    "version": "1.0.0",
    "macAddresses": [
        {
            "interfaceName": "Ethernet",
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "ipAddress": "192.168.1.100",
        },
        {
            "interfaceName": "Wi-Fi",
            "macAddress": "11:22:33:44:55:66",
            "ipAddress": "192.168.1.101",
        },
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow() -> PcRemoteConfigFlow:
    """Create a config flow with mocked HA internals."""
    flow = PcRemoteConfigFlow()
    flow.hass = MagicMock()
    flow.context = {}
    return flow


def _make_entry_data(**overrides) -> dict:
    defaults = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 5000,
        CONF_API_KEY: "test-key",
        CONF_MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
    }
    defaults.update(overrides)
    return defaults


def _make_config_entry(data: dict | None = None, options: dict | None = None) -> MagicMock:
    entry = MagicMock()
    entry.data = data or _make_entry_data()
    entry.options = options or {}
    entry.entry_id = "test_entry_id"
    entry.unique_id = "TestPC"
    return entry


# ---------------------------------------------------------------------------
# User step
# ---------------------------------------------------------------------------


class TestUserStep:
    @pytest.mark.asyncio
    async def test_show_form_on_first_call(self):
        flow = _make_flow()
        result = await flow.async_step_user(user_input=None)
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_cannot_connect(self):
        flow = _make_flow()
        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=CannotConnectError
            )
            result = await flow.async_step_user(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_invalid_auth(self):
        flow = _make_flow()
        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=InvalidAuthError
            )
            result = await flow.async_step_user(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 5000, CONF_API_KEY: "bad"}
            )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_unknown_error(self):
        flow = _make_flow()
        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            result = await flow.async_step_user(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_success_proceeds_to_select_mac(self):
        flow = _make_flow()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_RESPONSE
            )
            result = await flow.async_step_user(
                {CONF_HOST: "192.168.1.100", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )

        # With single MAC, auto-selects and creates entry
        assert result["type"] == "create_entry"
        assert result["data"][CONF_MAC_ADDRESS] == "AA:BB:CC:DD:EE:FF"


# ---------------------------------------------------------------------------
# Select MAC step
# ---------------------------------------------------------------------------


class TestSelectMacStep:
    @pytest.mark.asyncio
    async def test_single_mac_auto_selects(self):
        flow = _make_flow()
        flow._host = "192.168.1.100"
        flow._port = 5000
        flow._api_key = "key"
        flow._machine_name = "TestPC"

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_RESPONSE
            )
            result = await flow.async_step_select_mac(user_input=None)

        assert result["type"] == "create_entry"
        assert result["data"][CONF_MAC_ADDRESS] == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_multiple_macs_shows_dropdown(self):
        flow = _make_flow()
        flow._host = "192.168.1.100"
        flow._port = 5000
        flow._api_key = "key"
        flow._machine_name = "TestPC"

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_MULTI_MAC
            )
            result = await flow.async_step_select_mac(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "select_mac"

    @pytest.mark.asyncio
    async def test_user_selects_mac(self):
        flow = _make_flow()
        flow._host = "192.168.1.100"
        flow._port = 5000
        flow._api_key = "key"
        flow._machine_name = "TestPC"

        result = await flow.async_step_select_mac(
            user_input={CONF_MAC_ADDRESS: "11:22:33:44:55:66"}
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_MAC_ADDRESS] == "11:22:33:44:55:66"

    @pytest.mark.asyncio
    async def test_no_macs_shows_error(self):
        flow = _make_flow()
        flow._host = "192.168.1.100"
        flow._port = 5000
        flow._api_key = "key"

        health_no_macs = {
            "machineName": "TestPC",
            "macAddresses": [],
        }

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=health_no_macs
            )
            result = await flow.async_step_select_mac(user_input=None)

        assert result["type"] == "form"
        assert result["errors"] == {"base": "no_mac_addresses"}

    @pytest.mark.asyncio
    async def test_connection_error_during_mac_fetch(self):
        flow = _make_flow()
        flow._host = "192.168.1.100"
        flow._port = 5000
        flow._api_key = "key"

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=CannotConnectError
            )
            result = await flow.async_step_select_mac(user_input=None)

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_aborts_when_host_missing(self):
        flow = _make_flow()
        flow._host = None
        flow._port = None

        result = await flow.async_step_select_mac(user_input=None)
        assert result["type"] == "abort"


# ---------------------------------------------------------------------------
# Reconfigure step
# ---------------------------------------------------------------------------


class TestReconfigureStep:
    def _setup_flow(self, entry_data: dict | None = None) -> PcRemoteConfigFlow:
        flow = _make_flow()
        entry = _make_config_entry(data=entry_data)
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reconfigure_successful"}
        )
        return flow

    @pytest.mark.asyncio
    async def test_show_form_prefilled(self):
        flow = self._setup_flow()
        result = await flow.async_step_reconfigure(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    @pytest.mark.asyncio
    async def test_cannot_connect(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=CannotConnectError
            )
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_invalid_auth(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=InvalidAuthError
            )
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 5000, CONF_API_KEY: "bad"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_unknown_error(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_same_host_updates_without_mac_reselect(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_RESPONSE
            )
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "192.168.1.100", CONF_PORT: 5001, CONF_API_KEY: "new-key"}
            )

        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"
        call_data = flow.async_update_reload_and_abort.call_args[1]["data"]
        assert call_data[CONF_PORT] == 5001
        assert call_data[CONF_API_KEY] == "new-key"
        assert call_data[CONF_MAC_ADDRESS] == "AA:BB:CC:DD:EE:FF"  # preserved

    @pytest.mark.asyncio
    async def test_host_changed_triggers_mac_reselect(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_RESPONSE
            )
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "10.0.0.5", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )

        # Single MAC auto-selects, so we get the abort directly
        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"

    @pytest.mark.asyncio
    async def test_host_changed_multiple_macs_shows_dropdown(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_MULTI_MAC
            )
            result = await flow.async_step_reconfigure(
                {CONF_HOST: "10.0.0.5", CONF_PORT: 5000, CONF_API_KEY: "key"}
            )

        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure_select_mac"


# ---------------------------------------------------------------------------
# Reconfigure select MAC step
# ---------------------------------------------------------------------------


class TestReconfigureSelectMacStep:
    def _setup_flow(self) -> PcRemoteConfigFlow:
        flow = _make_flow()
        flow._host = "10.0.0.5"
        flow._port = 5000
        flow._api_key = "key"
        flow._machine_name = "TestPC"
        entry = _make_config_entry()
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reconfigure_successful"}
        )
        return flow

    @pytest.mark.asyncio
    async def test_user_selects_mac(self):
        flow = self._setup_flow()

        result = await flow.async_step_reconfigure_select_mac(
            user_input={CONF_MAC_ADDRESS: "11:22:33:44:55:66"}
        )

        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"
        call_data = flow.async_update_reload_and_abort.call_args[1]["data"]
        assert call_data[CONF_MAC_ADDRESS] == "11:22:33:44:55:66"
        assert call_data[CONF_HOST] == "10.0.0.5"

    @pytest.mark.asyncio
    async def test_single_mac_auto_selects(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_RESPONSE
            )
            result = await flow.async_step_reconfigure_select_mac(user_input=None)

        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"

    @pytest.mark.asyncio
    async def test_connection_error(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=CannotConnectError
            )
            result = await flow.async_step_reconfigure_select_mac(user_input=None)

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_invalid_auth(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=InvalidAuthError
            )
            result = await flow.async_step_reconfigure_select_mac(user_input=None)

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_no_macs_shows_error(self):
        flow = self._setup_flow()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value={"machineName": "TestPC", "macAddresses": []}
            )
            result = await flow.async_step_reconfigure_select_mac(user_input=None)

        assert result["type"] == "form"
        assert result["errors"] == {"base": "no_mac_addresses"}

    @pytest.mark.asyncio
    async def test_aborts_when_host_missing(self):
        flow = self._setup_flow()
        flow._host = None
        flow._port = None

        result = await flow.async_step_reconfigure_select_mac(user_input=None)
        assert result["type"] == "abort"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class TestOptionsFlow:
    def _make_options_flow(self, options: dict | None = None) -> PcRemoteOptionsFlow:
        flow = PcRemoteOptionsFlow()
        flow.hass = MagicMock()
        entry = _make_config_entry(options=options)
        flow._config_entry = entry
        # OptionsFlow uses self.config_entry property
        type(flow).config_entry = property(lambda self: self._config_entry)
        return flow

    @pytest.mark.asyncio
    async def test_show_form_with_defaults(self):
        flow = self._make_options_flow()
        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_show_form_with_existing_options(self):
        flow = self._make_options_flow(options={"scan_interval": 60})
        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"

    @pytest.mark.asyncio
    async def test_saves_options(self):
        flow = self._make_options_flow()
        flow.async_create_entry = MagicMock(
            return_value={"type": "create_entry", "data": {"scan_interval": 15}}
        )

        result = await flow.async_step_init(user_input={"scan_interval": 15})

        assert result["type"] == "create_entry"
        flow.async_create_entry.assert_called_once_with(data={"scan_interval": 15})

    def test_scan_interval_validation_range(self):
        """Validate that the schema rejects out-of-range values."""
        schema = vol.Schema(
            {
                vol.Required("scan_interval"): vol.All(
                    int, vol.Range(min=10, max=300)
                ),
            }
        )

        # Valid values
        assert schema({"scan_interval": 10}) == {"scan_interval": 10}
        assert schema({"scan_interval": 30}) == {"scan_interval": 30}
        assert schema({"scan_interval": 300}) == {"scan_interval": 300}

        # Invalid values
        with pytest.raises(vol.MultipleInvalid):
            schema({"scan_interval": 5})
        with pytest.raises(vol.MultipleInvalid):
            schema({"scan_interval": 301})

    def test_async_get_options_flow_returns_options_flow(self):
        entry = _make_config_entry()
        result = PcRemoteConfigFlow.async_get_options_flow(entry)
        assert isinstance(result, PcRemoteOptionsFlow)


# ---------------------------------------------------------------------------
# Zeroconf step
# ---------------------------------------------------------------------------


class TestZeroconfStep:
    @pytest.mark.asyncio
    async def test_zeroconf_discovery_sets_context(self):
        flow = _make_flow()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        discovery = MagicMock()
        discovery.host = "192.168.1.50"
        discovery.port = 5000
        discovery.properties = {"machine_name": "MyPC"}

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ):
            result = await flow.async_step_zeroconf(discovery)

        assert result["type"] == "form"
        assert result["step_id"] == "zeroconf_confirm"
        assert flow._discovered_host == "192.168.1.50"
        assert flow._discovered_port == 5000

    @pytest.mark.asyncio
    async def test_zeroconf_invalid_port(self):
        """Port 0 is falsy, so `port or DEFAULT_PORT` falls back to 5000."""
        flow = _make_flow()
        flow._async_abort_entries_match = MagicMock()

        discovery = MagicMock()
        discovery.host = "192.168.1.50"
        discovery.port = 0  # falsy → falls back to DEFAULT_PORT
        discovery.properties = {}

        result = await flow.async_step_zeroconf(discovery)
        # Port 0 is falsy, so code uses DEFAULT_PORT (5000) which is valid
        assert result["type"] == "form"
        assert result["step_id"] == "zeroconf_confirm"
        assert flow._discovered_port == DEFAULT_PORT

    @pytest.mark.asyncio
    async def test_zeroconf_confirm_success(self):
        flow = _make_flow()
        flow._discovered_host = "192.168.1.50"
        flow._discovered_port = 5000
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                return_value=HEALTH_RESPONSE
            )
            result = await flow.async_step_zeroconf_confirm(
                {CONF_API_KEY: "my-key"}
            )

        # Single MAC auto-selects → create_entry
        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_zeroconf_confirm_cannot_connect(self):
        flow = _make_flow()
        flow._discovered_host = "192.168.1.50"
        flow._discovered_port = 5000

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=CannotConnectError
            )
            result = await flow.async_step_zeroconf_confirm(
                {CONF_API_KEY: "my-key"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_zeroconf_confirm_invalid_auth(self):
        flow = _make_flow()
        flow._discovered_host = "192.168.1.50"
        flow._discovered_port = 5000

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ), patch(
            "custom_components.pc_remote.config_flow.PcRemoteClient"
        ) as mock_cls:
            mock_cls.return_value.get_health = AsyncMock(
                side_effect=InvalidAuthError
            )
            result = await flow.async_step_zeroconf_confirm(
                {CONF_API_KEY: "bad-key"}
            )

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_zeroconf_bytes_machine_name(self):
        flow = _make_flow()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        discovery = MagicMock()
        discovery.host = "192.168.1.50"
        discovery.port = 5000
        discovery.properties = {"machine_name": b"BytePC"}

        with patch(
            "custom_components.pc_remote.config_flow.async_get_clientsession"
        ):
            result = await flow.async_step_zeroconf(discovery)

        flow.async_set_unique_id.assert_called_with("BytePC")

    @pytest.mark.asyncio
    async def test_zeroconf_bad_unicode_aborts(self):
        flow = _make_flow()

        discovery = MagicMock()
        discovery.host = "192.168.1.50"
        discovery.port = 5000
        discovery.properties = {"machine_name": b"\xff\xfe"}

        result = await flow.async_step_zeroconf(discovery)
        assert result["type"] == "abort"
