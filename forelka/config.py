"""Account config manager.

Replaces the dozens of scattered ``open("config-<id>.json") + json.load``
calls across the codebase with a single typed, cached, atomically-written
store.

Layout (new):
    accounts/<user_id>/config.json         # user-facing config (this module)
    accounts/<user_id>/kernel_config.json  # kernel/API creds (Kernel handles)
    accounts/<user_id>/session            # Telethon session file

Legacy layout (still read for backward compatibility):
    config-<user_id>.json
    kernel_config-<user_id>.json
    forelka-<user_id>.session

On first ``save()`` the new layout is used; legacy files are left in place
so an old checkout keeps working.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar


DEFAULT_LANG = "ru"


@dataclass
class AccountConfig:
    """Per-account configuration.

    All fields are optional on disk; missing keys fall back to the defaults
    here.  Unknown keys from legacy configs are preserved in :attr:`extra`
    so we never lose user data on migration.
    """

    user_id: int
    prefix: str = "."
    owners: list[int] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    management_group_id: int | None = None
    management_topics: dict[str, int] = field(default_factory=dict)
    lang: str = DEFAULT_LANG
    # info module presentation flags (kept for backward compat)
    info_quote_media: bool = False
    info_banner_url: str = ""
    info_invert_media: bool = True
    # Forward-compatible bucket for fields we haven't modelled yet.
    extra: dict[str, Any] = field(default_factory=dict)

    _cache: ClassVar[dict[int, "AccountConfig"]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # ------------------------------------------------------------------ paths

    @staticmethod
    def account_dir(user_id: int) -> Path:
        return Path("accounts") / str(user_id)

    @classmethod
    def config_path(cls, user_id: int) -> Path:
        """Preferred location for this account's config.json."""
        return cls.account_dir(user_id) / "config.json"

    @classmethod
    def legacy_path(cls, user_id: int) -> Path:
        return Path(f"config-{user_id}.json")

    # ------------------------------------------------------------------ load

    @classmethod
    def load(cls, user_id: int, *, use_cache: bool = True) -> "AccountConfig":
        """Load config for ``user_id`` from disk (or cache)."""
        with cls._lock:
            if use_cache and user_id in cls._cache:
                return cls._cache[user_id]

            path = cls.config_path(user_id)
            if not path.exists():
                legacy = cls.legacy_path(user_id)
                if legacy.exists():
                    path = legacy

            data: dict[str, Any] = {}
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except (OSError, json.JSONDecodeError):
                    data = {}

            cfg = cls._from_dict(user_id, data)
            cls._cache[user_id] = cfg
            return cfg

    @classmethod
    def _from_dict(cls, user_id: int, data: dict[str, Any]) -> "AccountConfig":
        known = {f.name for f in fields(cls) if f.name not in ("user_id", "extra")}
        kwargs: dict[str, Any] = {"user_id": user_id}
        extra: dict[str, Any] = {}
        for key, value in data.items():
            if key in known:
                kwargs[key] = value
            else:
                extra[key] = value
        kwargs["extra"] = extra
        return cls(**kwargs)

    # ------------------------------------------------------------------ save

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("user_id", None)
        extra = d.pop("extra", {}) or {}
        out: dict[str, Any] = {**extra, **{k: v for k, v in d.items() if v is not None}}
        return out

    def save(self) -> None:
        """Atomically write config to disk (preferring the new layout)."""
        path = self.config_path(self.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        # Write to a tempfile in the same directory, then os.replace for atomicity.
        fd, tmp_name = tempfile.mkstemp(prefix=".config-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        with type(self)._lock:
            type(self)._cache[self.user_id] = self

    # ------------------------------------------------------------------ helpers

    def is_owner(self, peer_id: int) -> bool:
        return peer_id == self.user_id or peer_id in self.owners

    def add_owner(self, peer_id: int) -> bool:
        if peer_id in self.owners:
            return False
        self.owners.append(peer_id)
        return True

    def remove_owner(self, peer_id: int) -> bool:
        if peer_id not in self.owners:
            return False
        self.owners.remove(peer_id)
        return True

    def set_alias(self, alias: str, target: str) -> None:
        self.aliases[alias] = target

    def resolve_alias(self, cmd: str) -> str:
        return self.aliases.get(cmd, cmd)

    # ------------------------------------------------------------------ cache

    @classmethod
    def invalidate(cls, user_id: int | None = None) -> None:
        with cls._lock:
            if user_id is None:
                cls._cache.clear()
            else:
                cls._cache.pop(user_id, None)
