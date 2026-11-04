#!/usr/bin/env python3
"""Local-only repeatable verification. Never uses a user database or GitHub Actions."""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and not any(x in p.parts for x in ('.git', '__pycache__', '.pytest_cache', '.hypothesis', '.venv', 'dist'))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--e5', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True, help='New empty directory for synthetic DB, snapshot and evidence')
    parser.add_argument('--python', type=Path, help='Use an existing locked QA environment, read-only')
    parser.add_argument('--go', default='go')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    root = args.work.absolute()
    if root.exists() and any(root.iterdir()):
        raise SystemExit('Verification work directory must be empty; no existing files were changed')
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    (root/'evidence').mkdir()
    snapshot = root/'snapshot'
    shutil.copytree(source, snapshot, ignore=shutil.ignore_patterns('.venv', '__pycache__', '.pytest_cache', '.hypothesis', 'dist', '.env', '*.connection.json'))
    before = hashes(snapshot)
    (root/'snapshot.json').write_text(json.dumps(before, indent=2))
    python = args.python or root/'venv/bin/python'
    if not args.python:
        subprocess.run(['uv', 'venv', '--python', '3.12', str(root/'venv')], check=True)
        subprocess.run(['uv', 'pip', 'sync', '--python', str(python), '--require-hashes', str(snapshot/'requirements.lock'), str(snapshot/'qa-requirements.lock')], check=True)
    # Check every locked package, including when reusing an external QA venv.
    check = '''import importlib.metadata,json,sys
from pathlib import Path
from packaging.requirements import Requirement
expected={}
for name in sys.argv[1:]:
    for line in Path(name).read_text().splitlines():
        if not line or line[0].isspace() or line.startswith('#') or '==' not in line:
            continue
        req=Requirement(line.rstrip().removesuffix(chr(92)).strip())
        if not req.marker or req.marker.evaluate():
            expected[req.name]=next(iter(req.specifier)).version
actual={k:importlib.metadata.version(k) for k in expected}
assert actual==expected,(actual,expected)
print(json.dumps(actual,sort_keys=True))
'''
    installed = subprocess.check_output([str(python), '-c', check, str(snapshot/'requirements.lock'), str(snapshot/'qa-requirements.lock')], text=True)
    (root/'evidence/dependencies.json').write_text(installed)
    subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(root/'dist')], cwd=snapshot, check=True)
    wheel = next((root/'dist').glob('*.whl'))
    proxy = root/'legacy-proxy'
    subprocess.run([args.go, 'build', '-trimpath', '-o', str(proxy), './client/main.go'], cwd=snapshot, check=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    pgdata = root/'pgdata'
    with (root/'evidence/initdb.log').open('w') as out:
        subprocess.run([str(args.pg_bin/'initdb'), '-D', str(pgdata), '-U', 'audit', '--auth-local=trust', '--auth-host=trust', '--no-instructions'], stdout=out, stderr=subprocess.STDOUT, check=True)
    start = [str(args.pg_bin/'pg_ctl'), '-D', str(pgdata)]
    subprocess.run(start+['-l', str(root/'pg.log'), '-o', f'-h 127.0.0.1 -p {port} -k {root}', 'start'], check=True)
    env = dict(os.environ, PYTHONPATH=str(snapshot/'src'), PYTHONDONTWRITEBYTECODE='1',
        AM_COLLAB_TEST_DSN=f'postgresql://audit@127.0.0.1:{port}/postgres', AM_COLLAB_TEST_DATA_DIR=str(pgdata),
        AM_COLLAB_TEST_E5=str(args.e5), AM_COLLAB_TEST_E5_MANIFEST=str(snapshot/'e5-assets.sha256.json'),
        AM_COLLAB_EVIDENCE=str(root/'evidence'), AM_COLLAB_TEST_PROXY=str(proxy), AM_COLLAB_TEST_WHEEL=str(wheel),
        AUDIT_PG_BIN=str(args.pg_bin))
    command = [str(python), '-m', 'pytest', 'tests', '-q', '--tb=short', '--hypothesis-seed=20261104', '--junitxml='+str(root/'evidence/results.xml')]
    try:
        with (root/'evidence/results.log').open('w') as out:
            result = subprocess.run(command, check=False, cwd=snapshot, env=env, stdout=out, stderr=subprocess.STDOUT)
    finally:
        subprocess.run(start+['-m', 'fast', 'stop'], check=True)
    assert hashes(snapshot) == before, 'Executed snapshot changed during verification'
    (root/'evidence/run.json').write_text(json.dumps({'exit_code': result.returncode,
        'source_unchanged': hashes(source) == before, 'snapshot_unchanged': True,
        'python': str(python), 'command': command, 'platform': sys.platform,
        'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(), 'seed': 20261104}, indent=2))
    print((root/'evidence/results.log').read_text())
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
