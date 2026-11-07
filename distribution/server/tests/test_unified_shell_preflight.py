import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def shell_case(tmp_path):
    tools = tmp_path / 'bin'
    tools.mkdir()
    marker = tmp_path / 'forbidden'
    for name in ('curl', 'tar', 'mktemp'):
        tool = tools / name
        tool.write_text('#!/bin/bash\nprintf "%s\\n" "$0" >> "$FORBIDDEN"\nexit 97\n')
        tool.chmod(0o700)
    (tools / 'python3').symlink_to(sys.executable)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], HOME=str(tmp_path), FORBIDDEN=str(marker))
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    files = {}
    required = ['unified_setup.py', 'install-unified.sh', 'install-client.sh', 'runtime-helper.py', 'client-requirements.lock', 'reranker-assets.sha256.json']
    manifest = {'version': '2.0.0'}
    for label in ('sdk', 'core_312', 'core_313'):
        name = 'packages/' + label + '.whl'
        manifest[label] = name
        required.append(name)
    for name in required:
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'forbidden installer asset\n')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['files'] = files
    (bundle / 'ASSETS.json').write_text(json.dumps(manifest))
    return tmp_path, bundle, marker, env


def invoke(case, *args):
    _, bundle, marker, env = case
    result = subprocess.run(['/bin/bash', str(ROOT / 'install-unified.sh'), '--bundle', str(bundle), *args], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert result.returncode != 0
    assert not marker.exists(), result.stderr
    return result


@pytest.mark.parametrize('args', [
    ['--url', 'https://example.invalid'], ['--profile', 'private'],
    ['--credential-file', '/private/secret'], ['--replace-credential'], ['--recover'],
    ['--root', '/private/client'], ['--no-automatic-memory'],
    ['--connect-server', '--provider', 'jev'], ['--connect-server', '--model', 'model'],
    ['--connect-server', '--mode', 'local'], ['--connect-server', '--reranker-dir', '/model'],
    ['--connect-server', '--bootstrap-bundle', '/bootstrap'],
])
def test_mixed_modes_do_not_start_setup(shell_case, args):
    invoke(shell_case, *args)


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'symlink-file', 'symlink-directory'])
@pytest.mark.parametrize('remote', [False, True])
def test_invalid_assets_never_download_or_extract(shell_case, mutation, remote):
    tmp_path, bundle, _, _ = shell_case
    if mutation == 'missing':
        (bundle / 'runtime-helper.py').unlink()
    elif mutation == 'extra':
        (bundle / 'unreviewed.py').write_text('raise SystemExit(99)')
    elif mutation == 'symlink-file':
        asset = bundle / 'runtime-helper.py'
        target = tmp_path / 'outside.py'
        shutil.move(asset, target)
        asset.symlink_to(target)
    else:
        (bundle / 'unlisted-directory').symlink_to(tmp_path, target_is_directory=True)
    invoke(shell_case, *(['--connect-server'] if remote else []))


def test_extracted_bootstrap_cannot_authorize_itself(shell_case):
    tmp_path, _, _, _ = shell_case
    bootstrap = tmp_path / 'bootstrap'
    (bootstrap / 'runtimes').mkdir(parents=True)
    (bootstrap / 'installer.py').write_text('raise SystemExit(99)')
    for target in ('darwin-arm64', 'linux-x86_64'):
        (bootstrap / 'runtimes' / (target + '.tar.gz')).write_bytes(b'untrusted runtime')
    (bootstrap / 'MANIFEST.json').write_text(json.dumps({'files': {}}))
    (tmp_path / 'bin' / 'mktemp').unlink()
    invoke(shell_case, '--bootstrap-bundle', str(bootstrap))
