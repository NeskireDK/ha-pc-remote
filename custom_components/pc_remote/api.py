"""API client for the PC Remote service."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class PcRemoteClient:
    """Async HTTP client for the PC Remote REST API."""

    def __init__(
        self,
        host: str,
        port: int,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._base_url = f"http://{host}:{port}"
        self._headers = {"X-Api-Key": api_key}
        self._session = session

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def get_health(self) -> dict:
        """Poll the health endpoint. Returns the unwrapped data payload."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/health",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    async def get_system_state(self) -> dict:
        """Get aggregated system state from the service."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/system/state",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def get_modes(self) -> list[str]:
        """Get available PC modes."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/system/modes",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_mode(self, mode_name: str) -> None:
        """Apply a PC mode."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/system/mode/{quote(mode_name, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def sleep(self) -> None:
        """Send the sleep command to the PC."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/system/sleep",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    async def get_audio_devices(self) -> list[dict]:
        """Get available audio output devices."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/audio/devices",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_audio_device(self, device_name: str) -> None:
        """Set the active audio output device."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/audio/set/{quote(device_name, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_volume(self, level: int) -> None:
        """Set the system volume level."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/audio/volume/{level}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # Monitor
    # ------------------------------------------------------------------

    async def get_monitor_profiles(self) -> list[dict]:
        """Get available monitor profiles."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/monitor/profiles",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_monitor_profile(self, profile: str) -> None:
        """Activate a monitor profile."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/set/{quote(profile, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def get_monitors(self) -> list[dict]:
        """Get connected monitors."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/monitor/list",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def solo_monitor(self, monitor_id: str) -> None:
        """Enable only this monitor, disable all others."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/solo/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def enable_monitor(self, monitor_id: str) -> None:
        """Enable a monitor."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/enable/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def disable_monitor(self, monitor_id: str) -> None:
        """Disable a monitor."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/disable/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_primary_monitor(self, monitor_id: str) -> None:
        """Set a monitor as the primary display."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/primary/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # Apps
    # ------------------------------------------------------------------

    async def get_apps(self) -> list[dict]:
        """Get configured apps and their running status."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/app/status",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def launch_app(self, app_key: str) -> None:
        """Launch an app by key."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/app/launch/{quote(app_key, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def kill_app(self, app_key: str) -> None:
        """Kill a running app by key."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/app/kill/{quote(app_key, safe='')}",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # Steam
    # ------------------------------------------------------------------

    async def get_steam_games(self) -> list[dict]:
        """Get recently played Steam games."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/steam/games",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data", result)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def get_steam_running(self) -> dict | None:
        """Get the currently running Steam game, or None."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/steam/running",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    msg = result.get("message", "Unknown error")
                    _LOGGER.warning("API call failed: %s", msg)
                    raise CannotConnectError(f"API error: {msg}")
                return result.get("data")  # Can be None if no game running
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def steam_run(self, app_id: int) -> None:
        """Launch a Steam game (idempotent -- closes current if different)."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/steam/run/{app_id}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def steam_stop(self) -> None:
        """Stop the currently running Steam game."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/steam/stop",
                headers=self._headers,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    async def test_connection(self) -> bool:
        """Test the connection to the PC Remote service."""
        await self.get_health()
        return True


class CannotConnectError(Exception):
    """Error raised when the client cannot connect."""


class InvalidAuthError(Exception):
    """Error raised when the API key is invalid."""
