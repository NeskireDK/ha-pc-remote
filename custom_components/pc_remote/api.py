"""API client for the PC Remote service."""

from __future__ import annotations

import logging
from urllib.parse import quote

import aiohttp

_LOGGER = logging.getLogger(__name__)


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
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    _LOGGER.warning("Health endpoint returned failure: %s", result.get("message"))
                return result.get("data", result)
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    async def sleep(self) -> None:
        """Send the sleep command to the Windows PC."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/system/sleep",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
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
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    _LOGGER.warning("get_audio_devices returned failure: %s", result.get("message"))
                return result.get("data", result)
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def get_current_audio(self) -> dict:
        """Get the current audio device and volume."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/audio/current",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    _LOGGER.warning("get_current_audio returned failure: %s", result.get("message"))
                return result.get("data", result)
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_audio_device(self, device_name: str) -> None:
        """Set the active audio output device."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/audio/set/{quote(device_name, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_volume(self, level: int) -> None:
        """Set the system volume level."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/audio/volume/{level}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
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
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    _LOGGER.warning("get_monitor_profiles returned failure: %s", result.get("message"))
                return result.get("data", result)
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_monitor_profile(self, profile: str) -> None:
        """Activate a monitor profile."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/set/{quote(profile, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def get_monitors(self) -> list[dict]:
        """Get connected monitors."""
        try:
            async with self._session.get(
                f"{self._base_url}/api/monitor/list",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    _LOGGER.warning("get_monitors returned failure: %s", result.get("message"))
                return result.get("data", result)
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def solo_monitor(self, monitor_id: str) -> None:
        """Enable only this monitor, disable all others."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/solo/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def enable_monitor(self, monitor_id: str) -> None:
        """Enable a monitor."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/enable/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def disable_monitor(self, monitor_id: str) -> None:
        """Disable a monitor."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/disable/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def set_primary_monitor(self, monitor_id: str) -> None:
        """Set a monitor as the primary display."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/monitor/primary/{quote(monitor_id, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
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
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if not result.get("success", True):
                    _LOGGER.warning("get_apps returned failure: %s", result.get("message"))
                return result.get("data", result)
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def launch_app(self, app_key: str) -> None:
        """Launch an app by key."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/app/launch/{quote(app_key, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def kill_app(self, app_key: str) -> None:
        """Kill a running app by key."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/app/kill/{quote(app_key, safe='')}",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except aiohttp.ClientConnectorError as err:
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
