"""Tests for forelka.config.AccountConfig."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forelka.config import AccountConfig


@pytest.fixture(autouse=True)
def _chdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    AccountConfig.invalidate()
    yield
    AccountConfig.invalidate()


def test_load_missing_returns_defaults():
    cfg = AccountConfig.load(111)
    assert cfg.user_id == 111
    assert cfg.prefix == "."
    assert cfg.owners == []
    assert cfg.aliases == {}
    assert cfg.lang == "ru"
    assert cfg.management_group_id is None


def test_load_reads_legacy_path(tmp_path: Path):
    data = {
        "prefix": "!",
        "owners": [42, 7],
        "aliases": {"p": "ping"},
        "management_group_id": -100,
        "lang": "en",
    }
    (tmp_path / "config-222.json").write_text(json.dumps(data), encoding="utf-8")
    cfg = AccountConfig.load(222)
    assert cfg.prefix == "!"
    assert cfg.owners == [42, 7]
    assert cfg.aliases == {"p": "ping"}
    assert cfg.management_group_id == -100
    assert cfg.lang == "en"


def test_save_uses_new_layout(tmp_path: Path):
    cfg = AccountConfig.load(333)
    cfg.prefix = "?"
    cfg.owners = [1, 2]
    cfg.lang = "en"
    cfg.save()

    new_path = tmp_path / "accounts" / "333" / "config.json"
    assert new_path.exists()
    stored = json.loads(new_path.read_text(encoding="utf-8"))
    assert stored["prefix"] == "?"
    assert stored["owners"] == [1, 2]
    assert stored["lang"] == "en"


def test_save_preserves_unknown_fields(tmp_path: Path):
    legacy = tmp_path / "config-444.json"
    legacy.write_text(json.dumps({"prefix": ".", "future_field": "keep me"}), encoding="utf-8")

    cfg = AccountConfig.load(444)
    assert cfg.extra.get("future_field") == "keep me"
    cfg.save()

    new_path = tmp_path / "accounts" / "444" / "config.json"
    stored = json.loads(new_path.read_text(encoding="utf-8"))
    assert stored["future_field"] == "keep me"


def test_is_owner():
    cfg = AccountConfig.load(555)
    cfg.owners = [1, 2]
    assert cfg.is_owner(555)  # self is always an owner
    assert cfg.is_owner(1)
    assert not cfg.is_owner(999)


def test_add_and_remove_owner():
    cfg = AccountConfig.load(666)
    assert cfg.add_owner(10) is True
    assert cfg.add_owner(10) is False  # already there
    assert cfg.owners == [10]
    assert cfg.remove_owner(10) is True
    assert cfg.remove_owner(10) is False
    assert cfg.owners == []


def test_resolve_alias():
    cfg = AccountConfig.load(777)
    cfg.aliases = {"p": "ping"}
    assert cfg.resolve_alias("p") == "ping"
    assert cfg.resolve_alias("help") == "help"


def test_save_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """os.replace is used so a crashed save never leaves a half-written file."""
    cfg = AccountConfig.load(888)
    cfg.prefix = "/"

    replaces: list[tuple[str, str]] = []
    import os as os_mod

    original_replace = os_mod.replace

    def tracking_replace(src: str, dst: str) -> None:
        replaces.append((str(src), str(dst)))
        original_replace(src, dst)

    monkeypatch.setattr(os_mod, "replace", tracking_replace)
    cfg.save()

    assert len(replaces) == 1
    src, dst = replaces[0]
    assert src != dst
    assert dst.endswith("accounts/888/config.json")


def test_cache_returns_same_instance():
    a = AccountConfig.load(999)
    b = AccountConfig.load(999)
    assert a is b
    AccountConfig.invalidate(999)
    c = AccountConfig.load(999)
    assert c is not a
