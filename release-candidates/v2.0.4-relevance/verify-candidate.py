"""Verify candidate bytes, not experimental results or permission to publish."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile


def sha(body):
    return hashlib.sha256(body).hexdigest()


def verify(directory):
    proof = json.loads((directory / 'CANDIDATE.json').read_text())
    archive = directory / proof['archive']['name']
    assert sha(archive.read_bytes()) == proof['archive']['sha256']
    assert (directory / 'SHA256SUMS').read_text() == proof['archive']['sha256'] + '  ' + archive.name + '\n'
    checkout = directory.parents[1]
    with tarfile.open(archive) as package:
        members = package.getmembers()
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        assert len({m.name for m in members}) == len(members) == proof['archive_members']
        manifest = json.load(package.extractfile('ASSETS.json'))
        assert manifest['version'] == proof['runtime_version'] == '2.0.0'
        assert set(manifest['files']) | {'ASSETS.json'} == {m.name for m in members}
        for name, digest in manifest['files'].items():
            assert sha(package.extractfile(name).read()) == digest, name
        for field in ['core_312', 'core_313']:
            name = manifest[field]
            body = package.extractfile(name).read()
            assert sha(body) == proof['core_wheels'][Path(name).name]
            with zipfile.ZipFile(io.BytesIO(body)) as wheel:
                names = wheel.namelist()
                public = {'agents_memory/__init__.py', 'agents_memory/runtime_launcher.py'}
                assert all(not n.endswith(('.c', '.h')) and (not n.endswith('.py') or n in public) for n in names)
                assert len([n for n in names if n.startswith('agents_memory/') and n.endswith('.pyc')]) == 13
        body = package.extractfile(manifest['sdk']).read()
        assert sha(body) == proof['sdk_wheel_sha256']
        with zipfile.ZipFile(io.BytesIO(body)) as wheel:
            names = [n for n in wheel.namelist() if n.startswith('agents_memory_collab/')]
            assert len([n for n in names if n.endswith('.py')]) == proof['sdk_python_modules'] == 16
            assert set(names) == set(proof['sdk_package_files'])
            for name in names:
                content = wheel.read(name)
                assert sha(content) == proof['sdk_package_files'][name], name
                assert content == (checkout / 'distribution/server/src' / name).read_bytes(), name
        for name in ['install-unified.sh', 'install-client.sh', 'unified_setup.py']:
            assert package.extractfile(name).read() == (checkout / 'distribution/server' / name).read_bytes(), name
    return {'candidate_identity_verified': True, 'sdk_python_modules': 16,
            'source_free_core_modules_per_interpreter': 13,
            'independent_quality': 'not asserted by this identity check',
            'stable_approval': False}


if __name__ == '__main__':
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent)))
