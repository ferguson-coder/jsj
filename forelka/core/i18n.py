"""Tiny i18n helper.

Loads JSON dictionaries from ``locales/<lang>.json`` and resolves dotted
keys.  Falls back to the default language (ru) and finally to the key
itself.

Usage::

    from forelka.i18n import t, Translator

    t("common.error", error="oops")          # default language
    tr = Translator(lang="en")
    tr("common.error", error="oops")

For per-client convenience use :func:`for_client`::

    tr = for_client(client)    # reads lang from AccountConfig
    await message.edit(tr("cmd.restart.starting"))
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

DEFAULT_LANG = "ru"
LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


_loaded: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _load_locale(lang: str) -> dict[str, Any]:
    with _lock:
        cached = _loaded.get(lang)
        if cached is not None:
            return cached
        path = LOCALES_DIR / f"{lang}.json"
        if not path.exists():
            _loaded[lang] = {}
            return _loaded[lang]
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except (OSError, json.JSONDecodeError):
            data = {}
        _loaded[lang] = data
        return data


def _resolve(key: str, bundle: dict[str, Any]) -> str | None:
    node: Any = bundle
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        if part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def t(key: str, *, lang: str | None = None, **fmt: Any) -> str:
    """Resolve a translation key.

    Lookup order: ``lang`` → default language → raw ``key`` string.
    Any ``{placeholder}`` tokens in the resolved string are formatted
    with ``**fmt``; unknown placeholders leave a visible marker rather
    than raising, so a misconfigured translation never takes the bot
    offline.
    """
    chosen = lang or DEFAULT_LANG
    value = _resolve(key, _load_locale(chosen))
    if value is None and chosen != DEFAULT_LANG:
        value = _resolve(key, _load_locale(DEFAULT_LANG))
    if value is None:
        value = key
    if not fmt:
        return value
    try:
        return value.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return value


class Translator:
    """Bound translator for a specific language."""

    __slots__ = ("lang",)

    def __init__(self, lang: str | None = None) -> None:
        self.lang = lang or DEFAULT_LANG

    def __call__(self, key: str, **fmt: Any) -> str:
        return t(key, lang=self.lang, **fmt)


def for_client(client: Any) -> Translator:
    """Return a :class:`Translator` bound to the client's configured language.

    Falls back to the default language if the account config is missing
    or the lang field is empty.
    """
    from forelka.config import AccountConfig

    user_id = getattr(client, "_self_id", None)
    if user_id is None:
        return Translator()
    try:
        cfg = AccountConfig.load(int(user_id))
    except Exception:
        return Translator()
    return Translator(cfg.lang or DEFAULT_LANG)


def available_languages() -> list[str]:
    if not LOCALES_DIR.exists():
        return []
    return sorted(p.stem for p in LOCALES_DIR.glob("*.json"))


def reload() -> None:
    """Drop cached locale bundles (useful for tests / hot-reload)."""
    with _lock:
        _loaded.clear()
