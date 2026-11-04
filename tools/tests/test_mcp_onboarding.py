"""Cold-start protocol and explicit onboarding; no credentials, models or real histories."""
import asyncio
import json
import os
import subprocess

import pytest
from test_mcp_local_setup import SOURCE

pytest_plugins = ["test_mcp_local_setup"]

ROOT = SOURCE.parents[2]
BINARY = ROOT / "plugins/agents-memory-local/bin/setup-status-linux-x86_64"


def frames(messages):
    data = b"".join((json.dumps(m, ensure_ascii=False).encode() if isinstance(m, dict) else m) + b"\n"
                    for m in messages)
    result = subprocess.run([str(BINARY)], input=data, capture_output=True, timeout=5, check=True)
    assert not result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


@pytest.mark.parametrize("protocol", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"])
def test_no_runtime_initialize_and_actionable_setup_status(protocol):
    result = frames([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": protocol}},
                     {"jsonrpc": "2.0", "method": "notifications/initialized"},
                     {"jsonrpc": "2.0", "id": "tools", "method": "tools/list"},
                     {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "setup_status"}}])
    assert len(result) == 3 and result[0]["result"]["protocolVersion"] == protocol
    assert [t["name"] for t in result[1]["result"]["tools"]] == ["setup_status"]
    status = result[2]["result"]
    assert status["structuredContent"]["ready"] is False and status["structuredContent"]["setupRequired"]
    guide = status["content"][0]["text"]
    assert '\n' in guide and '--project "$PWD"' in guide and 'Enter' in guide
    assert not status["isError"]


@pytest.mark.parametrize("identifier", [0, -17, "quoted\"identifier", "한글🧠", "line\nbreak"])
def test_request_id_is_echoed_safely(identifier):
    result = frames([{"jsonrpc": "2.0", "id": identifier, "method": "ping"}])
    assert result == [{"jsonrpc": "2.0", "id": identifier, "result": {}}]


@pytest.mark.parametrize("broken", [b'{broken', b'{"jsonrpc":"2.0","id":"\xff","method":"ping"}',
                                     b'{}trailing', b'{' * 70, b'a' * 70000, b'{}\x00more'])
def test_bad_input_is_bounded_and_next_request_still_works(broken):
    result = frames([broken, {"jsonrpc": "2.0", "id": 2, "method": "ping"}])
    assert result[0]["error"]["code"] == -32700 and result[1]["result"] == {}


def test_setup_tool_does_not_echo_caller_secrets_or_execute_other_tools():
    canary = "SYNTHETIC_KEY_MUST_NOT_APPEAR"
    result = frames([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "setup_status", "arguments": {"key": canary}}},
                     {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "sync_retain"}}])
    assert canary not in json.dumps(result) and result[1]["error"]["code"] == -32602


def test_home_project_is_rejected_before_install_or_key_prompt(helper, tmp_path, monkeypatch):
    monkeypatch.setattr(helper.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(helper, "install_core", lambda *args: pytest.fail("Home setup requested a key"))
    args = helper.parser().parse_args(["setup", "--project", str(tmp_path), "--client", "omp"])
    with pytest.raises(helper.Refused, match="not HOME"):
        helper.setup(args)


def test_home_route_is_not_used_as_catch_all_for_other_projects(helper, installation, tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = home / "work/project"
    project.mkdir(parents=True)
    monkeypatch.setattr(helper.Path, "home", lambda: home)
    helper.write_json(installation / "settings/mcp-projects.json", {str(home): {"project": str(home), "bank": "home"}})
    with pytest.raises(helper.Refused, match="not configured"):
        helper.project_record(installation, project)


def test_shell_rejects_home_before_any_download(tmp_path):
    environment = dict(os.environ) | {"HOME": str(tmp_path)}
    result = subprocess.run(["bash", str(SOURCE.parent / "install.sh"), "--project", str(tmp_path),
                             "--client", "omp"], env=environment, capture_output=True, timeout=5, check=False)
    assert result.returncode == 2 and b'Downloading' not in result.stderr


def test_sdk_proxy_stays_connected_when_explicitly_stopped(helper, installation, tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    helper.write_json(installation / "settings/mcp-service.json", {"enabled": False, "product_id": "a" * 32})

    async def check():
        params = StdioServerParameters(command=helper.sys.executable,
                                       args=[str(SOURCE), "--prefix", str(installation), "proxy", "--project", str(tmp_path)])
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            assert [tool.name for tool in (await session.list_tools()).tools] == ["setup_status"]
            result = await session.call_tool("setup_status", {})
            assert result.structured_content["state"] == "explicitly_stopped"
            assert result.structured_content["ready"] is False

    asyncio.run(check())
