"""Config flow for the PC Remote integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnectError, InvalidAuthError, PcRemoteClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MAC_ADDRESS,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_API_KEY): str,
    }
)

STEP_ZEROCONF_CONFIRM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class PcRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PC Remote."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_port: int | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._api_key: str | None = None
        self._unique_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }
            )

            session = async_get_clientsession(self.hass)
            client = PcRemoteClient(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                api_key=user_input[CONF_API_KEY],
                session=session,
            )

            try:
                await client.test_connection()
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                self._host = user_input[CONF_HOST]
                self._port = user_input[CONF_PORT]
                self._api_key = user_input[CONF_API_KEY]
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
        self._discovered_port = discovery_info.port or DEFAULT_PORT

        # Use machine_name from TXT record as stable unique ID (survives IP changes)
        machine_name = (discovery_info.properties or {}).get("machine_name")
        if machine_name:
            if isinstance(machine_name, bytes):
                machine_name = machine_name.decode("utf-8")
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
            assert self._discovered_host is not None
            assert self._discovered_port is not None

            session = async_get_clientsession(self.hass)
            client = PcRemoteClient(
                host=self._discovered_host,
                port=self._discovered_port,
                api_key=user_input[CONF_API_KEY],
                session=session,
            )

            try:
                await client.test_connection()
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                self._host = self._discovered_host
                self._port = self._discovered_port
                self._api_key = user_input[CONF_API_KEY]
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

    async def async_step_select_mac(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a network interface for Wake-on-LAN."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self._create_entry(user_input[CONF_MAC_ADDRESS])

        # Fetch MAC addresses from the health endpoint
        session = async_get_clientsession(self.hass)
        client = PcRemoteClient(
            host=self._host,
            port=self._port,
            api_key=self._api_key,
            session=session,
        )

        try:
            health = await client.get_health()
        except (CannotConnectError, InvalidAuthError, Exception):  # noqa: BLE001
            _LOGGER.exception("Failed to fetch MAC addresses from health endpoint")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="select_mac",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        mac_addresses: list[dict] = health.get("macAddresses", [])

        if not mac_addresses:
            errors["base"] = "no_mac_addresses"
            return self.async_show_form(
                step_id="select_mac",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        if len(mac_addresses) == 1:
            return self._create_entry(mac_addresses[0]["macAddress"])

        # Multiple MACs — show dropdown
        options = [
            selector.SelectOptionDict(
                value=mac["macAddress"],
                label=f"{mac['interfaceName']} ({mac['macAddress']} - {mac['ipAddress']})",
            )
            for mac in mac_addresses
        ]

        return self.async_show_form(
            step_id="select_mac",
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
            errors=errors,
        )

    def _create_entry(self, mac_address: str) -> ConfigFlowResult:
        """Create a config entry with the collected data."""
        return self.async_create_entry(
            title=f"PC Remote ({self._host})",
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_API_KEY: self._api_key,
                CONF_MAC_ADDRESS: mac_address,
            },
        )
