"""API client for the PC Remote service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
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
    # Centralised request helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: aiohttp.ClientTimeout | None = None,
        json: dict[str, Any] | None = None,
        unwrap: bool = True,
    ) -> Any:
        """Send an authenticated request and return the response payload.

        Args:
            method: HTTP method (get, post, put, etc.).
            path: URL path appended to the base URL.
            timeout: Override the default timeout.
            json: Optional JSON body for POST/PUT requests.
            unwrap: If True, check ``success`` and return ``data``. If False,
                    return the raw JSON dict.

        Returns:
            The ``data`` value from the JSON envelope when *unwrap* is True,
            or the full JSON dict otherwise.

        Raises:
            InvalidAuthError: On HTTP 401.
            CannotConnectError: On network/timeout errors or API-level failures.
        """
        url = f"{self._base_url}{path}"
        kwargs: dict[str, Any] = {
            "headers": self._headers,
            "timeout": timeout or _TIMEOUT,
        }
        if json is not None:
            kwargs["json"] = json

        try:
            async with getattr(self._session, method)(url, **kwargs) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
                result = await resp.json()
                if unwrap:
                    if not result.get("success", True):
                        msg = result.get("message", "Unknown error")
                        _LOGGER.warning("API call failed: %s", msg)
                        raise CannotConnectError(f"API error: {msg}")
                    return result.get("data", result)
                return result
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    async def _request_no_body(
        self,
        method: str,
        path: str,
        *,
        timeout: aiohttp.ClientTimeout | None = None,
        json: dict[str, Any] | None = None,
    ) -> None:
        """Send an authenticated request, ignoring the response body."""
        url = f"{self._base_url}{path}"
        kwargs: dict[str, Any] = {
            "headers": self._headers,
            "timeout": timeout or _TIMEOUT,
        }
        if json is not None:
            kwargs["json"] = json

        try:
            async with getattr(self._session, method)(url, **kwargs) as resp:
                if resp.status == 401:
                    raise InvalidAuthError("Invalid API key")
                resp.raise_for_status()
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnectError(
                f"Cannot connect to {self._base_url}"
            ) from err

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def get_health(self) -> dict:
        """Poll the health endpoint. Returns the unwrapped data payload."""
        return await self._request("get", "/api/health")

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    async def get_system_state(self) -> dict:
        """Get aggregated system state from the service."""
        return await self._request("get", "/api/system/state")

    async def set_power_config(self, auto_sleep_minutes: int) -> None:
        """Set power configuration (auto-sleep timeout) on the service."""
        await self._request_no_body(
            "put", "/api/system/power/",
            json={"autoSleepAfterMinutes": auto_sleep_minutes},
        )

    async def get_modes(self) -> list[str]:
        """Get available PC modes."""
        return await self._request("get", "/api/system/modes")

    async def set_mode(self, mode_name: str) -> None:
        """Apply a PC mode."""
        await self._request_no_body(
            "post", f"/api/system/mode/{quote(mode_name, safe='')}",
        )

    async def sleep(self) -> None:
        """Send the sleep command to the PC."""
        await self._request_no_body("post", "/api/system/sleep")

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    async def get_audio_devices(self) -> list[dict]:
        """Get available audio output devices."""
        return await self._request("get", "/api/audio/devices")

    async def set_audio_device(self, device_name: str) -> None:
        """Set the active audio output device."""
        await self._request_no_body(
            "post", f"/api/audio/set/{quote(device_name, safe='')}",
        )

    async def set_volume(self, level: int) -> None:
        """Set the system volume level."""
        await self._request_no_body("post", f"/api/audio/volume/{level}")

    # ------------------------------------------------------------------
    # Monitor
    # ------------------------------------------------------------------

    async def get_monitor_profiles(self) -> list[dict]:
        """Get available monitor profiles."""
        return await self._request("get", "/api/monitor/profiles")

    async def set_monitor_profile(self, profile: str) -> None:
        """Activate a monitor profile."""
        await self._request_no_body(
            "post", f"/api/monitor/set/{quote(profile, safe='')}",
        )

    async def get_monitors(self) -> list[dict]:
        """Get connected monitors."""
        return await self._request("get", "/api/monitor/list")

    async def solo_monitor(self, monitor_id: str) -> None:
        """Enable only this monitor, disable all others."""
        await self._request_no_body(
            "post", f"/api/monitor/solo/{quote(monitor_id, safe='')}",
        )

    async def enable_monitor(self, monitor_id: str) -> None:
        """Enable a monitor."""
        await self._request_no_body(
            "post", f"/api/monitor/enable/{quote(monitor_id, safe='')}",
        )

    async def disable_monitor(self, monitor_id: str) -> None:
        """Disable a monitor."""
        await self._request_no_body(
            "post", f"/api/monitor/disable/{quote(monitor_id, safe='')}",
        )

    async def set_primary_monitor(self, monitor_id: str) -> None:
        """Set a monitor as the primary display."""
        await self._request_no_body(
            "post", f"/api/monitor/primary/{quote(monitor_id, safe='')}",
        )

    # ------------------------------------------------------------------
    # Apps
    # ------------------------------------------------------------------

    async def get_apps(self) -> list[dict]:
        """Get configured apps and their running status."""
        return await self._request("get", "/api/app/status")

    async def launch_app(self, app_key: str) -> None:
        """Launch an app by key."""
        await self._request_no_body(
            "post", f"/api/app/launch/{quote(app_key, safe='')}",
        )

    async def kill_app(self, app_key: str) -> None:
        """Kill a running app by key."""
        await self._request_no_body(
            "post", f"/api/app/kill/{quote(app_key, safe='')}",
        )

    # ------------------------------------------------------------------
    # Steam
    # ------------------------------------------------------------------

    async def get_steam_games(self) -> list[dict]:
        """Get recently played Steam games."""
        return await self._request("get", "/api/steam/games")

    async def get_steam_running(self) -> dict | None:
        """Get the currently running Steam game, or None."""
        return await self._request("get", "/api/steam/running")

    async def steam_run(self, app_id: int) -> dict | None:
        """Launch a Steam game, return running game dict or None."""
        return await self._request(
            "post", f"/api/steam/run/{app_id}",
            timeout=aiohttp.ClientTimeout(total=30),
        )

    async def get_steam_bindings(self) -> dict:
        """Get Steam game-to-PC-mode bindings."""
        result = await self._request("get", "/api/steam/bindings")
        return result if result is not None else {}

    async def steam_stop(self) -> None:
        """Stop the currently running Steam game."""
        await self._request_no_body("post", "/api/steam/stop")

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
