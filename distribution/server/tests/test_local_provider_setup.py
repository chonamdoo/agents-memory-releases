"""Provider routing checks with no model calls or credential discovery."""
import os
from types import SimpleNamespace
from pathlib import Path

import pytest
from test_unified_setup import assets, setup


def args(prefix, bundle, **overrides):
    values = dict(prefix=prefix, bundle=bundle, provider='local', mode='local', model='test-model',
                  public_url=None, local_host=None, local_url=None, local_executable=None,
                  jev_key_file=None, reranker_dir=None, bootstrap_bundle=None)
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize('mode', ['personal-server', 'team-server', 'company-server'])
@pytest.mark.parametrize('provider', ['local', 'local-llm'])
def test_server_refuses_local_before_credentials_or_bootstrap(assets, mode, provider):
    prefix, bundle, _ = assets
    with pytest.raises(setup.SetupInputError, match='Server deployments'):
        setup.install(args(prefix, bundle, mode=mode, provider=provider))
    assert not prefix.exists()


@pytest.mark.parametrize('url', ['https://localhost/v1', 'http://example.com/v1',
                                 'http://127.0.0.1/v1?key=x', 'http://a@localhost/v1',
                                 'http://localhost/other', 'http://localhost:bad/v1'])
def test_remote_or_invalid_local_endpoint_rejected(url):
    with pytest.raises(setup.SetupInputError):
        setup.local_endpoint(url)


def test_local_service_does_not_read_jev_key_and_clears_inherited_routes(assets, monkeypatch):
    prefix, bundle, _ = assets
    h = setup.helper(bundle)
    h.write_json(prefix / 'settings/mcp-database.json', {'url': 'postgresql://fixture'})
    h.write_private(prefix / 'settings/jev-credential.json', b'invalid and deliberately unread')
    monkeypatch.setenv('AM_MEMORY_JEV_KEY_FILE', '/never/read')
    monkeypatch.setenv('HINDSIGHT_API_MEMORY_ADMISSION_API_KEY', 'synthetic')
    config = dict(provider='local', model='test', mode='local', path=os.defpath,
                  local_host='openai', local_url='http://localhost:11434/v1')
    env = setup.service_environment(prefix, h, config)
    assert env['AM_MEMORY_LOCAL_URL'] == 'http://127.0.0.1:11434/v1'
    assert env['AM_MEMORY_DEPLOYMENT_MODE'] == 'local'
    assert 'AM_MEMORY_JEV_KEY_FILE' not in env
    assert 'HINDSIGHT_API_MEMORY_ADMISSION_API_KEY' not in env


@pytest.mark.parametrize('host', ['claude', 'codex'])
def test_cli_choice_and_saved_update_preserve_backend_without_key(assets, host):
    prefix, bundle, _ = assets
    h = setup.helper(bundle)
    executable = prefix.parent / host
    executable.write_text('#!/bin/sh\nexit 0\n'); executable.chmod(0o700)
    selected = args(prefix, bundle, local_host=host, local_executable=executable)
    _, migrating, model = setup._selected_configuration(selected, h, prefix)
    assert not migrating and model == 'test-model'
    assert selected._local_executable == str(executable)
    h.write_json(prefix / 'settings/unified.json', dict(provider='local', model='saved-model',
                  local_host=host, local_executable=str(executable), mode='local', public_url='http://localhost'))
    update = args(prefix, bundle, provider=None, model=None)
    _, migrating, model = setup._selected_configuration(update, h, prefix)
    assert update._selected_provider == 'local' and update._local_host == host
    assert not migrating and model == 'saved-model'


def test_legacy_local_llm_alias_selects_codex(assets):
    prefix, bundle, _ = assets
    h = setup.helper(bundle)
    executable = prefix.parent / 'codex'
    executable.write_text('#!/bin/sh\nexit 0\n'); executable.chmod(0o700)
    selected = args(prefix, bundle, provider='local-llm', local_executable=executable)
    setup._selected_configuration(selected, h, prefix)
    assert selected._selected_provider == 'local' and selected._local_host == 'codex'


def test_saved_server_mode_cannot_be_spoofed_as_local(assets):
    prefix, bundle, _ = assets
    h = setup.helper(bundle)
    h.write_json(prefix / 'settings/unified.json', dict(provider='jev', mode='team-server', model='jev'))
    with pytest.raises(setup.SetupInputError):
        setup._selected_configuration(args(prefix, bundle), h, prefix)


def test_local_never_accepts_jev_key_argument(assets):
    prefix, bundle, _ = assets
    with pytest.raises(setup.SetupInputError, match='does not use'):
        setup.install(args(prefix, bundle, jev_key_file=Path('/never/read')))


def test_first_local_bootstrap_requires_no_jev_credential(assets, monkeypatch):
    prefix, bundle, source = assets
    h = setup.helper(bundle)
    monkeypatch.setattr(setup, 'helper', lambda _: h)
    def bootstrap(_prefix, command, environment, _h):
        assert command[command.index('--provider') + 1] == 'local-llm'
        assert 'HINDSIGHT_API_MEMORY_ADMISSION_API_KEY' not in environment
        raise RuntimeError('reached bootstrap without key')
    monkeypatch.setattr(setup, '_bootstrap', bootstrap)
    with pytest.raises(RuntimeError, match='without key'):
        setup.install(args(prefix, bundle, reranker_dir=source, bootstrap_bundle=prefix.parent))


def test_switching_backend_marks_migration(assets):
    prefix, bundle, _ = assets
    h = setup.helper(bundle)
    h.write_json(prefix / 'settings/unified.json', dict(provider='local', local_host='codex',
                  mode='local', model='old', public_url='http://localhost'))
    _, migrating, _ = setup._selected_configuration(args(prefix, bundle, local_host='openai'), h, prefix)
    assert migrating
