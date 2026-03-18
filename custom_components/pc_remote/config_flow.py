"""Config flow for the PC Remote integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import CannotConnectError, InvalidAuthError, PcRemoteClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MAC_ADDRESS,
    CONF_PORT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)

STEP_ZEROCONF_CONFIRM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


class PcRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PC Remote."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_port: int | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._api_key: str | None = None
        self._machine_name: str | None = None

    async def _test_connection(
        self, host: str, port: int, api_key: str
    ) -> tuple[dict | None, str | None]:
        """Test connection and return (health_data, error_key). error_key is None on success."""
        session = async_get_clientsession(self.hass)
        client = PcRemoteClient(
            host=host,
            port=port,
            api_key=api_key,
            session=session,
        )
        try:
            health = await client.get_health()
            return health, None
        except CannotConnectError:
            return None, "cannot_connect"
        except InvalidAuthError:
            return None, "invalid_auth"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception during connection test")
            return None, "unknown"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            health, error_key = await self._test_connection(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_API_KEY]
            )
            if error_key:
                errors["base"] = error_key
            else:
                machine_name = health.get(
                    "machineName", f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                await self.async_set_unique_id(machine_name)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )
                self._host = user_input[CONF_HOST]
                self._port = user_input[CONF_PORT]
                self._api_key = user_input[CONF_API_KEY]
                self._machine_name = machine_name
                return await self.async_step_select_mac()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._discovered_host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        if not 1 <= port <= 65535:
            return self.async_abort(reason="unknown")
        self._discovered_port = port

        # Use machine_name from TXT record as stable unique ID (survives IP changes)
        machine_name = (discovery_info.properties or {}).get("machine_name")
        if machine_name:
            if isinstance(machine_name, bytes):
                try:
                    machine_name = machine_name.decode("utf-8")
                except UnicodeDecodeError:
                    return self.async_abort(reason="unknown")
            if len(machine_name) > 253:
                machine_name = machine_name[:253]
            await self.async_set_unique_id(machine_name)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._discovered_host, CONF_PORT: self._discovered_port}
            )
        else:
            # Fallback if no machine_name in TXT record
            self._async_abort_entries_match(
                {CONF_HOST: self._discovered_host, CONF_PORT: self._discovered_port}
            )

        self.context["title_placeholders"] = {
            "host": self._discovered_host,
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm zeroconf discovery and ask for API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self._discovered_host is None:
                return self.async_abort(reason="unknown")
            if self._discovered_port is None:
                return self.async_abort(reason="unknown")

            health, error_key = await self._test_connection(
                self._discovered_host, self._discovered_port, user_input[CONF_API_KEY]
            )
            if error_key:
                errors["base"] = error_key
            else:
                self._host = self._discovered_host
                self._port = self._discovered_port
                self._api_key = user_input[CONF_API_KEY]
                self._machine_name = health.get("machineName", "")
                return await self.async_step_select_mac()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=STEP_ZEROCONF_CONFIRM_SCHEMA,
            description_placeholders={
                "host": self._discovered_host or "",
                "port": str(self._discovered_port or DEFAULT_PORT),
            },
            errors=errors,
        )

    async def _fetch_mac_addresses(self) -> tuple[list[dict], str | None]:
        """Fetch and filter MAC addresses from the health endpoint.

        Returns (mac_list, None) on success or ([], error_key) on failure.
        """
        session = async_get_clientsession(self.hass)
        client = PcRemoteClient(
            host=self._host,
            port=self._port,
            api_key=self._api_key,
            session=session,
        )
        try:
            health = await client.get_health()
        except CannotConnectError:
            _LOGGER.debug("Failed to fetch MAC addresses: service unreachable")
            return [], "cannot_connect"
        except InvalidAuthError:
            return [], "invalid_auth"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to fetch MAC addresses from health endpoint")
            return [], "unknown"

        raw_macs: list[dict] = health.get("macAddresses", [])
        mac_addresses = [
            m for m in raw_macs if MAC_PATTERN.match(m.get("macAddress", ""))
        ]
        return mac_addresses, None

    def _build_mac_dropdown_form(
        self, step_id: str, mac_addresses: list[dict]
    ) -> ConfigFlowResult:
        """Build and return the MAC address dropdown form."""
        options = [
            selector.SelectOptionDict(
                value=mac.get("macAddress", ""),
                label=(
                    f"{mac.get('interfaceName', '')} "
                    f"({mac.get('macAddress', '')} - {mac.get('ipAddress', '')})"
                ),
            )
            for mac in mac_addresses
        ]

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC_ADDRESS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors={},
        )

    async def async_step_select_mac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a network interface for Wake-on-LAN."""
        if user_input is not None:
            return self._create_entry(user_input[CONF_MAC_ADDRESS])

        if self._host is None or self._port is None:
            return self.async_abort(reason="unknown")

        mac_addresses, error_key = await self._fetch_mac_addresses()

        if error_key:
            return self.async_show_form(
                step_id="select_mac",
                data_schema=vol.Schema({}),
                errors={"base": error_key},
            )

        if not mac_addresses:
            return self.async_show_form(
                step_id="select_mac",
                data_schema=vol.Schema({}),
                errors={"base": "no_mac_addresses"},
            )

        if len(mac_addresses) == 1:
            return self._create_entry(mac_addresses[0]["macAddress"])

        return self._build_mac_dropdown_form("select_mac", mac_addresses)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of host, port, and API key."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            health, error_key = await self._test_connection(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_API_KEY]
            )
            if error_key:
                errors["base"] = error_key
            else:
                self._host = user_input[CONF_HOST]
                self._port = user_input[CONF_PORT]
                self._api_key = user_input[CONF_API_KEY]
                self._machine_name = health.get("machineName", "")

                # If host changed, re-select MAC (new machine may have different NICs)
                if user_input[CONF_HOST] != entry.data[CONF_HOST]:
                    return await self.async_step_reconfigure_select_mac()

                return self.async_update_reload_and_abort(
                    entry,
                    title=f"PC Remote ({self._machine_name or self._host})",
                    data={
                        **entry.data,
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_API_KEY: self._api_key,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): int,
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_select_mac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-select MAC address during reconfigure when host changed."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                title=f"PC Remote ({self._machine_name or self._host})",
                data={
                    **entry.data,
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_API_KEY: self._api_key,
                    CONF_MAC_ADDRESS: user_input[CONF_MAC_ADDRESS],
                },
            )

        if self._host is None or self._port is None:
            return self.async_abort(reason="unknown")

        mac_addresses, error_key = await self._fetch_mac_addresses()

        if error_key:
            return self.async_show_form(
                step_id="reconfigure_select_mac",
                data_schema=vol.Schema({}),
                errors={"base": error_key},
            )

        if not mac_addresses:
            return self.async_show_form(
                step_id="reconfigure_select_mac",
                data_schema=vol.Schema({}),
                errors={"base": "no_mac_addresses"},
            )

        if len(mac_addresses) == 1:
            return self.async_update_reload_and_abort(
                entry,
                title=f"PC Remote ({self._machine_name or self._host})",
                data={
                    **entry.data,
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_API_KEY: self._api_key,
                    CONF_MAC_ADDRESS: mac_addresses[0]["macAddress"],
                },
            )

        return self._build_mac_dropdown_form("reconfigure_select_mac", mac_addresses)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> PcRemoteOptionsFlow:
        """Get the options flow for this handler."""
        return PcRemoteOptionsFlow()

    def _create_entry(self, mac_address: str) -> ConfigFlowResult:
        """Create a config entry with the collected data."""
        return self.async_create_entry(
            title=f"PC Remote ({self._machine_name or self._host})",
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_API_KEY: self._api_key,
                CONF_MAC_ADDRESS: mac_address,
            },
        )


class PcRemoteOptionsFlow(OptionsFlow):
    """Handle options for PC Remote."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "scan_interval",
                        default=current.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=10, max=300)),
                }
            ),
        )
