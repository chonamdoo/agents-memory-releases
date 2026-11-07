"""Check installed shipping modules under the selected isolated interpreter.

Use python -I from a fresh environment with the reviewed SDK and matching Core
wheel installed. This verifies imports/bytes, not engine bootstrap or quality.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(bundle, output):
    def deny_network(event, args):
        if event == 'socket.connect':
            raise RuntimeError('Network is forbidden in the installed-module probe')
    sys.addaudithook(deny_network)
    version = sys.version_info[:2]
    if version not in {(3, 12), (3, 13)}:
        raise ValueError('Select a supported CPython 3.12 or 3.13 interpreter')
    bundle = bundle.resolve(strict=True)
    manifest = json.loads((bundle / 'ASSETS.json').read_text())
    result = {'python': platform.python_version(), 'platform': sys.platform,
              'machine': platform.machine(), 'source_tree_imports': False,
              'network_connections_forbidden': True, 'probe_external_jev_calls': 0,
              'core_modules': {}, 'sdk_modules': {}}
    prefix = Path(sys.prefix).resolve(strict=True)
    for label in ('core_312' if version == (3, 12) else 'core_313', 'sdk'):
        member = manifest[label]
        path = (bundle / member).resolve(strict=True)
        assert path.is_relative_to(bundle) and not (bundle / member).is_symlink()
        assert sha(path.read_bytes()) == manifest['files'][member]
        result[label + '_wheel_sha256'] = sha(path.read_bytes())
        with zipfile.ZipFile(path) as archive:
            suffix = '.pyc' if label.startswith('core') else '.py'
            package = 'agents_memory/' if label.startswith('core') else 'agents_memory_collab/'
            names = [n for n in archive.namelist() if n.startswith(package) and n.endswith(suffix)]
            assert len(names) == (13 if label.startswith('core') else 15)
            for name in names:
                dotted = name[:-len(suffix)].replace('/', '.')
                dotted = dotted.removesuffix('.__init__')
                module = importlib.import_module(dotted)
                installed = Path(module.__file__).resolve(strict=True)
                assert installed.is_relative_to(prefix)
                assert installed.suffix == suffix and installed.read_bytes() == archive.read(name)
                result['core_modules' if label.startswith('core') else 'sdk_modules'][dotted] = sha(installed.read_bytes())
            if label == 'sdk':
                import agents_memory_collab
                schema = Path(agents_memory_collab.__file__).with_name('schema.sql')
                assert schema.read_bytes() == archive.read('agents_memory_collab/schema.sql')
                result['sdk_version'] = agents_memory_collab.__version__
                result['schema_sha256'] = sha(schema.read_bytes())
    assert result['sdk_version'] == manifest['version'] == '2.0.0'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'verified': True, 'python': result['python'],
                      'core_modules': len(result['core_modules']),
                      'sdk_modules': len(result['sdk_modules']), 'schema_verified': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.bundle, args.output)
