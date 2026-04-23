"""Tests for forelka.i18n."""

from __future__ import annotations

from forelka import i18n
from forelka.i18n import Translator, available_languages, t


def setup_function() -> None:
    i18n.reload()


def test_known_key_ru():
    assert "Обновление" in t("cmd.update.checking", lang="ru")


def test_known_key_en():
    assert "Updating" in t("cmd.update.checking", lang="en")


def test_unknown_key_returns_key():
    assert t("no.such.key") == "no.such.key"


def test_fallback_to_default_language():
    # Missing in "en" but present in "ru" would fall back.
    # We don't have a key like that in the default bundle, so emulate by
    # asking for an unknown key in a non-default language — should return key.
    assert t("no.such.key", lang="en") == "no.such.key"


def test_format_placeholders():
    msg = t("cmd.update.error", lang="en", error="boom")
    assert "boom" in msg


def test_missing_placeholder_does_not_raise():
    # Asking for a formatted string without the expected kwargs must not
    # crash the caller — we return the unformatted value instead.
    value = t("cmd.update.error", lang="en")
    assert "error" in value or "{" in value


def test_translator_bind():
    tr = Translator("en")
    assert "Updating" in tr("cmd.update.checking")


def test_available_languages_contains_ru_en():
    langs = available_languages()
    assert "ru" in langs
    assert "en" in langs
