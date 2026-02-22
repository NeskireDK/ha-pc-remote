"""The PC Remote integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnectError, PcRemoteClient
from .const import CONF_API_KEY, CONF_HOST, CONF_PORT, DOMAIN
from .coordinator import PcRemoteCoordinator

_LOGGER = __import__("logging").getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to current version."""
    if entry.version < 2:
        # v1 used "host:port" as unique ID; v2 uses machine_name from health endpoint
        session = async_get_clientsession(hass)
        client = PcRemoteClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            api_key=entry.data[CONF_API_KEY],
            session=session,
        )
        new_unique_id = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        try:
            health = await client.get_health()
            new_unique_id = health.get("machineName", new_unique_id)
        except CannotConnectError:
            _LOGGER.warning(
                "PC offline during migration, will retry on next restart"
            )
            return True
        hass.config_entries.async_update_entry(entry, unique_id=new_unique_id, version=2)
        _LOGGER.info("Migrated config entry %s to version 2", entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PC Remote from a config entry."""
    session = async_get_clientsession(hass)
    client = PcRemoteClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        api_key=entry.data[CONF_API_KEY],
        session=session,
    )

    coordinator = PcRemoteCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
