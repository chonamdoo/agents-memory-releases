"""Actual release connector protocol; explicit synthetic install only."""

import json
import os
import hashlib
import shlex
import sqlite3
from pathlib import Path
from uuid import UUID

import asyncio

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
        manifest = json.loads((Path(plugin) / ".claude-plugin/plugin.json").read_text())
        assert status["marketplace_version"] == manifest["version"]
        assert status["release_channel"] == "prerelease"
        assert status["candidate_archive"] == "agents-memory-unified-2.0.0-source-search.tar.gz"
        assert status["candidate_checksums"] == "SOURCE-SEARCH-SHA256SUMS"
        assert status["candidate_url"].startswith("https://github.com/chonamdoo/agents-memory-releases/")
        assert status["model_checksums"] == "SHA256SUMS"
        for host, client in [("claude", "claude-plugin"), ("omp", "omp-plugin"), ("codex", "codex")]:
            command = shlex.split(status["install_commands"][host])
            assert command[command.index("--client") + 1] == client
            assert "--provider" in command and "--project" in command
        assert (await session.call_tool("sync_retain", {})).is_error


@pytest.mark.asyncio
async def test_configured_connector_executes_installed_sdk_and_searches_original(system, tmp_path):
    """Real connector, shipped wheels and Native; fixture launcher omits autostart.

The fixture supplies an already-running isolated service and a launcher that
executes the installed interpreter. This does not verify unified engine
bootstrap, production ensure/autostart, real Jev judgment or macOS execution.
"""
    plugin = os.environ.get("AM_TEST_UNIFIED_PLUGIN")
    bundle = os.environ.get("AM_COLLAB_TEST_CLIENT_BUNDLE")
    if not plugin or not bundle or not os.environ.get("AM_UNIFIED_TEST_RECEIPT"):
        pytest.skip("Requires the release plugin, reviewed bundle and isolated Native runtime")
    from test_collaboration import operation
    from test_unified_contract import engine
    from agents_memory_collab.setup import write_private

    system.store.memory_engine = engine()
    remote, actor = await system.account()
    project = tmp_path / "configured project"
    project.mkdir()
    prefix = tmp_path / "owned prefix"
    python = prefix / "client/venv/bin/python"
    launcher = prefix / "bin/unified-python"
    write_private(launcher, "#!/bin/sh\nexec " + shlex.quote(str(python)) + ' -I "$@"\n')
    launcher.chmod(0o700)
    supplied = tmp_path / "operator.connection.json"
    write_private(supplied, json.dumps({"url": remote.url, "token": remote.token}))
    op = operation("The cache TTL is 37 seconds.\nThanks, the namespace is cache-v7.",
                   project=project.name, source_id="configured-fixture", session_id="configured-session")
    await system.store.push(actor, [op])
    text = await system.store.pool.fetchval("SELECT text FROM am_collab.memories WHERE user_id=$1 AND id=$2",
                                          actor.user_id, op.memory_id)
    assert "cache-v7" not in text
    # Importing the source tree instead of the installed wheel must fail.
    poison = tmp_path / "poison/agents_memory_collab"
    poison.mkdir(parents=True)
    (poison / "__init__.py").write_text('raise RuntimeError("source_tree_import_forbidden")\n')
    env = dict(os.environ, AM_COLLAB_CLIENT_ROOT=str(prefix / "client"),
               PYTHONPATH=str(poison.parent), PYTHONDONTWRITEBYTECODE="1")
    process = await asyncio.create_subprocess_exec(
        "bash", str(Path(bundle) / "install-client.sh"), "--client", "claude-plugin",
        "--profile", "local", "--project", str(project), "--python-launcher", str(launcher),
        "--credential-file", str(supplied), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(process.communicate(), 180)
    assert process.returncode == 0, stderr.decode()[-2000:]
    assert json.loads(stdout)["service_ready"]
    connection = prefix / "client/local/connection.json"
    saved = json.loads(connection.read_text())
    device = await system.store.authenticate(saved["token"])
    parameters = StdioServerParameters(command="/bin/bash",
        args=[str(Path(plugin) / "scripts/connect.sh"), "--prefix", str(prefix), "--project", str(project)],
        env=env)
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert "cache-v7" not in initialized.instructions
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"recall", "source_search", "sync_retain", "setup_status"} <= tools
        status = json.loads((await session.call_tool("setup_status", {})).content[0].text)
        assert status["service_ready"] and status["server_ready"]
        result = await session.call_tool("source_search", {"project": project.name, "query": "namespace"})
        assert not result.is_error
        source = json.loads(result.content[0].text)["sources"][0]
        assert source["body"] == op.text and source["id"] == str(op.op_id)
        assert source["body_sha256"] == hashlib.sha256(op.text.encode()).hexdigest()
        assert source["source_id"] == "configured-fixture"
        with sqlite3.connect(prefix / "client/local/replica.sqlite") as local:
            assert all("cache-v7" not in (row[0] or "") for row in local.execute("SELECT text FROM memories"))
        await system.store.revoke_device(actor, UUID(str(device.credential_id)))
        denied = await session.call_tool("source_search", {"project": project.name, "query": "namespace"})
        assert denied.is_error and "unauthorized" in denied.content[0].text


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
        assert status["service_ready"] and status["server_ready"]
