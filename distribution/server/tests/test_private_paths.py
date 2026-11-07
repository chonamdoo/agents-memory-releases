"""OS-root alias regression plus real filesystem rejection controls."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents_memory_collab import client
from agents_memory_collab.setup import write_private


@pytest.mark.parametrize('alias', ['/var', '/tmp', '/etc'])
def test_darwin_normalizes_only_verified_system_root(monkeypatch, alias):
    original_link = Path.is_symlink
    original_real = os.path.realpath
    original_stat = os.lstat
    monkeypatch.setattr(client.sys, 'platform', 'darwin')
    monkeypatch.setattr(Path, 'is_symlink', lambda p: True if str(p) == alias else original_link(p))
    monkeypatch.setattr(os, 'lstat', lambda p, **kw: SimpleNamespace(st_uid=0) if str(p) == alias else original_stat(p, **kw))
    monkeypatch.setattr(os.path, 'realpath', lambda p, **kw: '/private'+alias if str(p) == alias else original_real(p, **kw))
    assert client.private_file(Path(alias)/'am-test-uncreated/connection.json') == Path('/private'+alias)/'am-test-uncreated/connection.json'


@pytest.mark.parametrize('owner,target', [(1000, '/private/var'), (0, '/untrusted')])
def test_darwin_does_not_allow_changed_or_unowned_root(monkeypatch, owner, target):
    original_link, original_stat, original_real = Path.is_symlink, os.lstat, os.path.realpath
    monkeypatch.setattr(client.sys, 'platform', 'darwin')
    monkeypatch.setattr(Path, 'is_symlink', lambda p: True if str(p) == '/var' else original_link(p))
    monkeypatch.setattr(os, 'lstat', lambda p, **kw: SimpleNamespace(st_uid=owner) if str(p) == '/var' else original_stat(p, **kw))
    monkeypatch.setattr(os.path, 'realpath', lambda p, **kw: target if str(p) == '/var' else original_real(p, **kw))
    with pytest.raises(ValueError, match='symbolic links'):
        client.private_file(Path('/var/am-test-uncreated/connection.json'))


def test_user_controlled_leaf_and_parent_links_still_rejected(tmp_path):
    source = tmp_path/'source.json'
    write_private(source, '{}')
    leaf = tmp_path/'leaf.json'
    leaf.symlink_to(source)
    with pytest.raises(ValueError, match='symbolic links'):
        client.private_file(leaf)
    parent = tmp_path/'parent'
    parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='symbolic links'):
        client.private_file(parent/'source.json')


def test_private_mode_and_hardlink_rules_still_enforced(tmp_path):
    source = tmp_path/'source.json'
    source.write_text('{}')
    source.chmod(0o644)
    with pytest.raises(ValueError, match='0600'):
        client.private_file(source)
    source.chmod(0o600)
    os.link(source, tmp_path/'another.json')
    with pytest.raises(ValueError, match='regular file'):
        client.private_file(source)
