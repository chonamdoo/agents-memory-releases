"""Run the actual Bash half of the PowerShell bridge without downloading/installing the core."""
import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "distribution/mcp-local/install-wsl.ps1"


@pytest.fixture
def bridge(tmp_path):
    source = SOURCE.read_text()
    script = re.search(r"\$amScript = @'\n(.*?)\n'@", source, re.DOTALL).group(1)
    installer = tmp_path / "synthetic-installer.sh"
    installer.write_text(
        "#!/bin/bash\npython3 -c 'import json,os,sys; "
        "open(os.environ[\"AM_TEST_CAPTURE\"],\"w\").write(json.dumps(sys.argv[1:]))' \"$@\"\n"
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    curl = binary / "curl"
    curl.write_text(
        '#!/bin/bash\nfor ((i=1;i<=$#;i++)); do if [[ ${!i} == -o ]]; then '
        'j=$((i+1)); cp "$AM_TEST_INSTALLER" "${!j}"; exit; fi; done\nexit 88\n'
    )
    curl.chmod(0o700)
    identity = binary / "id"
    identity.write_text('#!/bin/bash\nprintf "%s\\n" "${AM_TEST_UID:-1000}"\n')
    identity.chmod(0o700)
    captured = tmp_path / "arguments.json"
    environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                       AM_TEST_CAPTURE=str(captured), AM_TEST_INSTALLER=str(installer))

    def invoke(project, clients=("claude", "codex", "omp"), *, checksum=None, **overrides):
        expected = checksum or hashlib.sha256(installer.read_bytes()).hexdigest()
        encoded = base64.b64encode(os.fsencode(project)).decode()
        return subprocess.run(["bash", "-c", script, "bridge-test", "1.0.8", expected, encoded, *clients],
                              env=environment | overrides, cwd=tmp_path, capture_output=True, text=True,
                              timeout=10, check=False)

    return invoke, captured


def test_encoded_project_round_trips_quotes_unicode_and_shell_syntax(bridge, tmp_path):
    project = tmp_path / 'project "double" \'single\' $(touch SHOULD_NOT_RUN) 한글'
    project.mkdir()
    invoke, captured = bridge
    result = invoke(project)
    assert result.returncode == 0, result.stderr
    assert json.loads(captured.read_text()) == ["--project", str(project), "--client", "claude",
                                               "--client", "codex", "--client", "omp"]
    assert not (tmp_path / "SHOULD_NOT_RUN").exists()


def test_installer_checksum_failure_never_executes_payload(bridge, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    invoke, captured = bridge
    result = invoke(project, checksum="0" * 64)
    assert result.returncode == 65 and "integrity" in result.stderr
    assert not captured.exists()


@pytest.mark.parametrize("invalid", ["root", "home"])
def test_unsuitable_wsl_identity_or_home_never_executes_installer(bridge, tmp_path, invalid):
    project = tmp_path / "project"
    project.mkdir()
    invoke, captured = bridge
    options = {"AM_TEST_UID": "0"} if invalid == "root" else {"HOME": str(project)}
    result = invoke(project, **options)
    assert result.returncode == 2 and not captured.exists()


@pytest.mark.parametrize("state", ["fresh", "unmarked", "booted"])
def test_vm_start_guard_preserves_existing_unmarked_test_disk(tmp_path, state):
    storage = tmp_path / "storage"
    storage.mkdir()
    disk = storage / "data.qcow2"
    if state != "fresh":
        disk.write_bytes(b"synthetic test disk must not be overwritten")
    if state == "booted":
        (storage / "windows.boot").touch()
    script = SOURCE.parents[1] / ".." / "tools/windows-vm/start-guard.sh"
    result = subprocess.run(["bash", str(script), "bash", "-c", "printf wrapper-started"],
                            env=dict(os.environ, STORAGE=str(storage)), capture_output=True,
                            text=True, timeout=10, check=False)
    if state == "unmarked":
        assert result.returncode == 73 and result.stdout == ""
        assert disk.read_bytes() == b"synthetic test disk must not be overwritten"
    else:
        assert result.returncode == 0 and result.stdout == "wrapper-started"
