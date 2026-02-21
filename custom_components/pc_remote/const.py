"""Constants for the PC Remote integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

DOMAIN = "pc_remote"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_API_KEY = "api_key"

DEFAULT_PORT = 5000
DEFAULT_SCAN_INTERVAL = 30


def build_device_info(entry: ConfigEntry) -> dict:
    """Build shared device info dict for all entities."""
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": f"PC Remote ({entry.data[CONF_HOST]})",
        "manufacturer": "PC Remote",
        "model": "PC",
        "configuration_url": f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
    }
