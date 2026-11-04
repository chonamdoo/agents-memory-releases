"""Mode selection must never run the other installer or rewrite its arguments."""
import json
import os
import subprocess
from pathlib import Path

import pytest

SELECTOR = Path(__file__).resolve().parents[2] / 'distribution/install.sh'


@pytest.fixture
def package(tmp_path):
    root = tmp_path / 'package with spaces'
    root.mkdir()
    (root/'install.sh').write_bytes(SELECTOR.read_bytes())
    for folder, entry in [('mcp-local', 'install.sh'), ('server', 'install-client.sh')]:
        (root/folder).mkdir()
        (root/folder/entry).write_text('#!/bin/bash\nexec python3 -c \'import json,os,sys; open(os.environ["RESULT"],"w").write(json.dumps(sys.argv[1:]))\' '+folder+' "$@"\n')
    return root


def run(root, *args):
    output = root/'result.json'
    result = subprocess.run(['bash', str(root/'install.sh'), *args], input='',
        env=dict(os.environ, RESULT=str(output)), text=True, capture_output=True, check=False)
    return result, json.loads(output.read_text()) if output.exists() else None


@pytest.mark.parametrize('mode,entry', [('local', 'mcp-local'), ('personal-server', 'server')])
def test_selects_only_requested_path_with_exact_arguments(package, mode, entry):
    args = ['--client', 'omp', '--project', '/tmp/한글 project', '--url', 'https://memory.example']
    result, saved = run(package, '--mode', mode, *args)
    assert result.returncode == 0 and saved == [entry, *args]


@pytest.mark.parametrize('args', [[], ['--mode'], ['--mode', 'invalid'], ['--mode='],
    ['--mode', 'local', '--mode', 'personal-server']])
def test_invalid_or_noninteractive_missing_mode_never_installs(package, args):
    result, saved = run(package, *args)
    assert result.returncode == 2 and saved is None


def test_help_does_not_install(package):
    result, saved = run(package, '--help')
    assert result.returncode == 0 and saved is None
    assert 'local LLM or Jev' in result.stdout


def test_missing_package_does_not_download_or_fall_back(package):
    (package/'server/install-client.sh').unlink()
    result, saved = run(package, '--mode=personal-server')
    assert result.returncode == 2 and saved is None
