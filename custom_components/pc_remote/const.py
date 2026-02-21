"""Constants for the PC Remote integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

DOMAIN = "pc_remote"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_API_KEY = "api_key"
CONF_MAC_ADDRESS = "mac_address"

DEFAULT_PORT = 5000
DEFAULT_SCAN_INTERVAL = 30


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build shared device info for all entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"PC Remote ({entry.data[CONF_HOST]})",
        manufacturer="PC Remote",
        model="PC",
        configuration_url=f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
    )
