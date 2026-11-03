"""Public wrapper contracts; synthetic keys only, no vendor service calls."""
import argparse
import importlib.util
import json
import os
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "distribution/hindsight-local"
KEY = "synthetic-jev-key-settings-test"


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location("provider_installer", SOURCE / "installer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def args(**updates):
    return argparse.Namespace(**dict(provider=None, model=None, codex=None, host=None,
                                    executable=None) | updates)


@pytest.mark.parametrize("host,model", [("claude", "claude-sonnet-5-5"), ("codex", "gpt-6.1-terra")])
def test_new_subscription_models(installer, tmp_path, host, model):
    profile = installer.select_profile(args(provider="local-llm", host=host), tmp_path)
    assert profile["model"] == model and profile["subscription_host"] == host


def test_legacy_codex_profile_and_model_remain_unchanged(installer, tmp_path):
    profile = installer.select_profile(args(provider="local-llm", host="codex", model="gpt-6.1-sol"), tmp_path)
    profile.pop("subscription_host")
    installer.private_json(tmp_path / "settings/profile.json", profile)
    before = (tmp_path / "settings/profile.json").read_bytes()
    assert installer.select_profile(args(), tmp_path) == profile
    assert (tmp_path / "settings/profile.json").read_bytes() == before


def test_jev_key_hidden_input_and_preservation(installer, tmp_path, monkeypatch, capsys):
    profile = installer.select_profile(args(provider="jev"), tmp_path)
    monkeypatch.setattr(installer.sys.stdin, "isatty", lambda: True)
    prompts = []
    monkeypatch.setattr(installer.getpass, "getpass", lambda prompt: prompts.append(prompt) or KEY)
    key = installer.pending_jev_credential(tmp_path, profile)
    assert key == KEY and len(prompts) == 1
    path = tmp_path / "settings/jev-credential.json"
    installer.private_json(path, {"schema_version": 1, "api_key": key})
    installer.private_json(tmp_path / "settings/profile.json", profile)
    before = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert installer.select_profile(args(), tmp_path) == profile
    assert installer.pending_jev_credential(tmp_path, profile) is None
    assert path.read_bytes() == before and len(prompts) == 1
    assert KEY not in capsys.readouterr().out


def test_subscription_does_not_read_jev_key(installer, tmp_path, monkeypatch):
    profile = installer.select_profile(args(provider="local-llm", host="codex"), tmp_path)
    monkeypatch.setattr(installer, "read_jev_credential", lambda *_: pytest.fail("Wrong route read a key"))
    assert installer.pending_jev_credential(tmp_path, profile) is None


def test_getpass_echo_fallback_is_refused(installer, monkeypatch):
    monkeypatch.setattr(installer.sys.stdin, "isatty", lambda: True)

    def unsafe(prompt):
        import warnings
        warnings.warn("No secure terminal", installer.getpass.GetPassWarning)

    monkeypatch.setattr(installer.getpass, "getpass", unsafe)
    with pytest.raises(ValueError, match="Secure terminal"):
        installer.prompt_jev_key()


def test_changed_install_options_require_explicit_configure(installer, tmp_path):
    profile = installer.select_profile(args(provider="jev"), tmp_path)
    installer.private_json(tmp_path / "settings/profile.json", profile)
    with pytest.raises(ValueError, match="preserved"):
        installer.select_profile(args(model="another-model"), tmp_path)


def test_public_bundle_does_not_accept_insecure_key_file(installer, tmp_path):
    (tmp_path / "settings").mkdir()
    path = tmp_path / "settings/jev-credential.json"
    path.write_text(json.dumps({"schema_version": 1, "api_key": KEY}))
    os.chmod(path, 0o644)
    with pytest.raises(ValueError, match="Private configuration"):
        installer.read_jev_credential(tmp_path)
