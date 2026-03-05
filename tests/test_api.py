"""Tests for custom_components/pc_remote/api.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# conftest stubs homeassistant before this import
from custom_components.pc_remote.api import (
    CannotConnectError,
    InvalidAuthError,
    PcRemoteClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status: int = 200, json_data: dict | None = None) -> MagicMock:
    """Return a mock aiohttp response usable as an async context manager."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=status
        )
    return resp


def _make_session(response: MagicMock) -> MagicMock:
    """Wrap a response in a mock session whose .get/.post/.put return it as async ctx manager."""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=ctx)
    session.post = MagicMock(return_value=ctx)
    session.put = MagicMock(return_value=ctx)
    return session


def _make_client(session: MagicMock) -> PcRemoteClient:
    return PcRemoteClient(
        host="192.168.1.1",
        port=5000,
        api_key="test-key",
        session=session,
    )


# ---------------------------------------------------------------------------
# get_health
# ---------------------------------------------------------------------------

class TestGetHealth:
    @pytest.mark.asyncio
    async def test_success_returns_data(self):
        resp = _make_response(200, {"success": True, "data": {"machineName": "TestPC", "version": "1.0"}})
        client = _make_client(_make_session(resp))
        result = await client.get_health()
        assert result["machineName"] == "TestPC"
        assert result["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_success_without_data_key_returns_whole_payload(self):
        """When the response has no 'data' key, the whole dict is returned."""
        resp = _make_response(200, {"machineName": "TestPC", "version": "1.0"})
        client = _make_client(_make_session(resp))
        result = await client.get_health()
        assert result["machineName"] == "TestPC"

    @pytest.mark.asyncio
    async def test_401_raises_invalid_auth(self):
        resp = _make_response(401)
        client = _make_client(_make_session(resp))
        with pytest.raises(InvalidAuthError):
            await client.get_health()

    @pytest.mark.asyncio
    async def test_500_raises_cannot_connect(self):
        resp = _make_response(500)
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=500
        )
        client = _make_client(_make_session(resp))
        with pytest.raises(CannotConnectError):
            await client.get_health()

    @pytest.mark.asyncio
    async def test_connection_error_raises_cannot_connect(self):
        session = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectorError(
            connection_key=MagicMock(), os_error=OSError("refused")
        ))
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=ctx)
        client = _make_client(session)
        with pytest.raises(CannotConnectError):
            await client.get_health()

    @pytest.mark.asyncio
    async def test_timeout_raises_cannot_connect(self):
        session = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=ctx)
        client = _make_client(session)
        with pytest.raises(CannotConnectError):
            await client.get_health()

    @pytest.mark.asyncio
    async def test_api_error_in_body_raises_cannot_connect(self):
        resp = _make_response(200, {"success": False, "message": "Service unavailable"})
        client = _make_client(_make_session(resp))
        with pytest.raises(CannotConnectError, match="Service unavailable"):
            await client.get_health()


# ---------------------------------------------------------------------------
# get_system_state
# ---------------------------------------------------------------------------

class TestGetSystemState:
    @pytest.mark.asyncio
    async def test_success(self):
        payload = {"audio": {"volume": 75}, "steamGames": []}
        resp = _make_response(200, {"success": True, "data": payload})
        client = _make_client(_make_session(resp))
        result = await client.get_system_state()
        assert result["audio"]["volume"] == 75

    @pytest.mark.asyncio
    async def test_401_raises_invalid_auth(self):
        resp = _make_response(401)
        client = _make_client(_make_session(resp))
        with pytest.raises(InvalidAuthError):
            await client.get_system_state()

    @pytest.mark.asyncio
    async def test_timeout_raises_cannot_connect(self):
        session = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=ctx)
        client = _make_client(session)
        with pytest.raises(CannotConnectError):
            await client.get_system_state()


# ---------------------------------------------------------------------------
# get_modes / set_mode
# ---------------------------------------------------------------------------

class TestModes:
    @pytest.mark.asyncio
    async def test_get_modes_returns_list(self):
        resp = _make_response(200, {"success": True, "data": ["Gaming", "Work"]})
        client = _make_client(_make_session(resp))
        modes = await client.get_modes()
        assert modes == ["Gaming", "Work"]

    @pytest.mark.asyncio
    async def test_set_mode_posts_to_correct_url(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_mode("Gaming Mode")
        call_args = session.post.call_args
        assert "Gaming%20Mode" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_set_mode_401_raises_invalid_auth(self):
        resp = _make_response(401)
        client = _make_client(_make_session(resp))
        with pytest.raises(InvalidAuthError):
            await client.set_mode("Gaming")


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

class TestAudio:
    @pytest.mark.asyncio
    async def test_get_audio_devices(self):
        devices = [{"name": "Speakers", "isDefault": True, "volume": 50}]
        resp = _make_response(200, {"success": True, "data": devices})
        client = _make_client(_make_session(resp))
        result = await client.get_audio_devices()
        assert result == devices

    @pytest.mark.asyncio
    async def test_set_audio_device_encodes_name(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_audio_device("Realtek HD Audio")
        call_url = session.post.call_args[0][0]
        assert "Realtek%20HD%20Audio" in call_url

    @pytest.mark.asyncio
    async def test_set_volume_posts_level(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_volume(75)
        call_url = session.post.call_args[0][0]
        assert "/75" in call_url

    @pytest.mark.asyncio
    async def test_set_volume_401(self):
        resp = _make_response(401)
        client = _make_client(_make_session(resp))
        with pytest.raises(InvalidAuthError):
            await client.set_volume(50)


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class TestMonitor:
    @pytest.mark.asyncio
    async def test_get_monitor_profiles(self):
        profiles = [{"name": "Desktop"}, {"name": "Gaming"}]
        resp = _make_response(200, {"success": True, "data": profiles})
        client = _make_client(_make_session(resp))
        result = await client.get_monitor_profiles()
        assert result == profiles

    @pytest.mark.asyncio
    async def test_set_monitor_profile_encodes_name(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_monitor_profile("TV Mode")
        assert "TV%20Mode" in session.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_solo_monitor_posts_correct_id(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.solo_monitor("\\\\?\\display#1")
        call_url = session.post.call_args[0][0]
        assert "/api/monitor/solo/" in call_url


# ---------------------------------------------------------------------------
# Steam
# ---------------------------------------------------------------------------

class TestSteam:
    @pytest.mark.asyncio
    async def test_get_steam_games(self):
        games = [{"appId": 570, "name": "Dota 2"}]
        resp = _make_response(200, {"success": True, "data": games})
        client = _make_client(_make_session(resp))
        result = await client.get_steam_games()
        assert result[0]["name"] == "Dota 2"

    @pytest.mark.asyncio
    async def test_get_steam_running_returns_none_when_no_game(self):
        resp = _make_response(200, {"success": True, "data": None})
        client = _make_client(_make_session(resp))
        result = await client.get_steam_running()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_steam_running_returns_game(self):
        game = {"appId": 570, "name": "Dota 2"}
        resp = _make_response(200, {"success": True, "data": game})
        client = _make_client(_make_session(resp))
        result = await client.get_steam_running()
        assert result["appId"] == 570

    @pytest.mark.asyncio
    async def test_steam_run_posts_app_id(self):
        game = {"appId": 1091500, "name": "Cyberpunk 2077"}
        resp = _make_response(200, {"success": True, "data": game})
        session = _make_session(resp)
        client = _make_client(session)
        result = await client.steam_run(1091500)
        assert "/api/steam/run/1091500" in session.post.call_args[0][0]
        assert result["appId"] == 1091500

    @pytest.mark.asyncio
    async def test_steam_run_returns_none_when_not_confirmed(self):
        resp = _make_response(200, {"success": True, "data": None})
        session = _make_session(resp)
        client = _make_client(session)
        result = await client.steam_run(1091500)
        assert result is None

    @pytest.mark.asyncio
    async def test_steam_stop_posts_to_stop(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.steam_stop()
        assert "/api/steam/stop" in session.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_steam_run_401(self):
        resp = _make_response(401)
        client = _make_client(_make_session(resp))
        with pytest.raises(InvalidAuthError):
            await client.steam_run(570)


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------

class TestSleep:
    @pytest.mark.asyncio
    async def test_sleep_posts_to_sleep_endpoint(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.sleep()
        assert "/api/system/sleep" in session.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_sleep_401_raises_invalid_auth(self):
        resp = _make_response(401)
        client = _make_client(_make_session(resp))
        with pytest.raises(InvalidAuthError):
            await client.sleep()

    @pytest.mark.asyncio
    async def test_sleep_timeout_raises_cannot_connect(self):
        session = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.post = MagicMock(return_value=ctx)
        client = _make_client(session)
        with pytest.raises(CannotConnectError):
            await client.sleep()


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

class TestConnection:
    @pytest.mark.asyncio
    async def test_test_connection_returns_true_on_success(self):
        resp = _make_response(200, {"success": True, "data": {"machineName": "PC"}})
        client = _make_client(_make_session(resp))
        result = await client.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_raises_on_failure(self):
        session = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        ctx.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=ctx)
        client = _make_client(session)
        with pytest.raises(CannotConnectError):
            await client.test_connection()


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

class TestUrlConstruction:
    def test_base_url_uses_host_and_port(self):
        session = MagicMock()
        client = PcRemoteClient("myhost.local", 8080, "key", session)
        assert client._base_url == "http://myhost.local:8080"

    def test_api_key_in_headers(self):
        session = MagicMock()
        client = PcRemoteClient("host", 5000, "secret-key", session)
        assert client._headers["X-Api-Key"] == "secret-key"


# ---------------------------------------------------------------------------
# API key header sent on every request
# ---------------------------------------------------------------------------

class TestApiKeyHeader:
    """Verify every public method sends X-Api-Key via the centralised _request helpers."""

    @pytest.mark.asyncio
    async def test_get_health_sends_api_key(self):
        resp = _make_response(200, {"success": True, "data": {"machineName": "PC"}})
        session = _make_session(resp)
        client = _make_client(session)
        await client.get_health()
        headers = session.get.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_get_system_state_sends_api_key(self):
        resp = _make_response(200, {"success": True, "data": {}})
        session = _make_session(resp)
        client = _make_client(session)
        await client.get_system_state()
        headers = session.get.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_set_power_config_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_power_config(30)
        headers = session.put.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_set_mode_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_mode("Gaming")
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_sleep_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.sleep()
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_set_audio_device_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.set_audio_device("Speakers")
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_steam_run_sends_api_key(self):
        resp = _make_response(200, {"success": True, "data": None})
        session = _make_session(resp)
        client = _make_client(session)
        await client.steam_run(570)
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_steam_stop_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.steam_stop()
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_launch_app_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.launch_app("chrome")
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"

    @pytest.mark.asyncio
    async def test_solo_monitor_sends_api_key(self):
        resp = _make_response(200, {})
        session = _make_session(resp)
        client = _make_client(session)
        await client.solo_monitor("mon1")
        headers = session.post.call_args[1]["headers"]
        assert headers["X-Api-Key"] == "test-key"
