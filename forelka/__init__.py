"""Forelka core package: shared infrastructure (config, i18n)."""

from forelka.config import AccountConfig
from forelka.i18n import Translator, t

__all__ = ["AccountConfig", "Translator", "t"]
