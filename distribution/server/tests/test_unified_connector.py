"""Actual release connector protocol; explicit synthetic install only."""

import json
import os
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_unconfigured_release_plugin_stays_connected_without_fake_storage(
    tmp_path,
):
    plugin = os.environ.get("AM_TEST_UNIFIED_PLUGIN")
    if not plugin:
        pytest.skip("Set the built release plugin directory")
    parameters = StdioServerParameters(
        command="/bin/bash",
        args=[
            str(Path(plugin) / "scripts/connect.sh"),
            "--prefix",
            str(tmp_path / "unconfigured"),
        ],
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        assert [t.name for t in (await session.list_tools()).tools] == ["setup_status"]
        status = json.loads(
            (await session.call_tool("setup_status", {})).content[0].text
        )
        assert status["ready"] is False and status["state"] == "setup_required"
        assert status["version"] == "1.0.8"
        assert (await session.call_tool("sync_retain", {})).is_error


@pytest.mark.asyncio
async def test_configured_release_plugin_executes_installed_owned_runtime():
    plugin, prefix = (
        os.environ.get("AM_TEST_UNIFIED_PLUGIN"),
        os.environ.get("AM_TEST_UNIFIED_INSTALL"),
    )
    if not plugin or not prefix:
        pytest.skip("Requires an explicit owned synthetic installation")
    parameters = StdioServerParameters(
        command="/bin/bash",
        args=[
            str(Path(plugin) / "scripts/connect.sh"),
            "--prefix",
            prefix,
            "--project",
            "synthetic-plugin-project",
        ],
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {
            "recall",
            "sync_retain",
            "team_search",
            "team_brief",
            "setup_status",
        } <= tools
        status = json.loads(
            (await session.call_tool("setup_status", {})).content[0].text
        )
        assert status["ready"] and status["version"] == "1.0.8"
