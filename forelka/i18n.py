"""Backward-compat shim — the real implementation now lives in ``forelka.core.i18n``."""

from forelka.core.i18n import (
    DEFAULT_LANG,
    LOCALES_DIR,
    Translator,
    available_languages,
    for_client,
    reload,
    t,
)

__all__ = [
    "DEFAULT_LANG",
    "LOCALES_DIR",
    "Translator",
    "available_languages",
    "for_client",
    "reload",
    "t",
]
