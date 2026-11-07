"""Verify the downloaded source-search candidate against this reviewed tree.

Only reads files. Does not install, extract, call a provider or publish anything.
"""
import argparse
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(archive):
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    proof = json.loads((here / 'VERIFICATION.json').read_text())
    data = archive.read_bytes()
    assert archive.name == proof['archive']['name']
    assert len(data) == proof['archive']['bytes'] and sha(data) == proof['archive']['sha256']
    assert (here / 'SOURCE-SEARCH-SHA256SUMS').read_text() == sha(data) + '  ' + archive.name + '\n'
    for name, expected in proof['evidence_sha256'].items():
        assert sha((here / name).read_bytes()) == expected, name
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        members = tar.getmembers()
        assert len({m.name for m in members}) == len(members)
        assert all(m.isfile() and not Path(m.name).is_absolute()
                   and '..' not in Path(m.name).parts for m in members)
        manifest = json.load(tar.extractfile('ASSETS.json'))
        assert manifest['version'] == '2.0.0'
        assert {m.name for m in members} == set(manifest['files']) | {'ASSETS.json'}
        for name, expected in manifest['files'].items():
            assert sha(tar.extractfile(name).read()) == expected, name
        sdk = tar.extractfile(manifest['sdk']).read()
        assert sha(sdk) == proof['sdk_wheel']['sha256']
        with zipfile.ZipFile(io.BytesIO(sdk)) as wheel:
            files = proof['sdk_wheel']['files']
            actual = {n for n in wheel.namelist() if n.startswith('agents_memory_collab/')
                      and n.endswith(('.py', '.sql'))}
            assert actual == set(files)
            for name, expected in files.items():
                source = root / 'distribution/server/src' / name
                assert sha(wheel.read(name)) == expected == sha(source.read_bytes()), name
        for label in ('core_312', 'core_313'):
            name = manifest[label]
            payload = tar.extractfile(name).read()
            assert sha(payload) == proof['unchanged_core_wheels'][Path(name).name]
            with zipfile.ZipFile(io.BytesIO(payload)) as wheel:
                assert all(not n.endswith(('.c', '.h')) and (not n.endswith('.py') or n in {
                    'agents_memory/__init__.py', 'agents_memory/runtime_launcher.py'}) for n in wheel.namelist())
        for name in ('install-client.sh', 'README.ko.md', 'unified_setup.py'):
            assert tar.extractfile(name).read() == (root / 'distribution/server' / name).read_bytes(), name
    print(json.dumps({'verified': True, 'archive_sha256': sha(data),
                      'sdk_python_files': proof['sdk_wheel']['python_files'],
                      'schema_matches': True, 'private_core_sources_published': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    main(parser.parse_args().archive)
