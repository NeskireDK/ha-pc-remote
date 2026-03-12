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

FAST_POLL_INTERVAL = 1
FAST_POLL_DURATION = 180


def build_device_info(
    entry: ConfigEntry,
    machine_name: str = "",
    sw_version: str = "",
) -> DeviceInfo:
    """Build shared device info for all entities."""
    display_name = machine_name or entry.data.get(CONF_HOST, "PC Remote")
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"PC Remote ({display_name})",
        manufacturer="PC Remote",
        model="Windows Service",
        sw_version=sw_version or None,
        configuration_url=f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
    )
