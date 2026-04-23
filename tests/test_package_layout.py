"""Smoke tests for the ``forelka/{core,inline,web,modules,assets,locales}`` layout."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_top_level_reexports():
    mod = importlib.import_module("forelka")
    assert hasattr(mod, "AccountConfig")
    assert hasattr(mod, "t")
    assert hasattr(mod, "Translator")
    assert hasattr(mod, "for_client")
    assert mod.__version__


def test_core_subpackage_imports():
    # Only import modules that don't pull in heavy runtime deps (telethon etc.).
    for name in [
        "forelka.core",
        "forelka.core.config",
        "forelka.core.i18n",
        "forelka.core.meta",
    ]:
        importlib.import_module(name)


def test_backward_compat_shims_alias_core():
    from forelka import config as shim_config
    from forelka import i18n as shim_i18n
    from forelka.core import config as real_config
    from forelka.core import i18n as real_i18n

    assert shim_config.AccountConfig is real_config.AccountConfig
    assert shim_i18n.t is real_i18n.t


def test_locales_live_inside_package():
    from forelka.core import i18n

    locales_dir = i18n.LOCALES_DIR
    assert locales_dir.exists(), locales_dir
    assert "forelka" in locales_dir.parts
    assert (locales_dir / "ru.json").is_file()
    assert (locales_dir / "en.json").is_file()


def test_assets_live_inside_package():
    assets_dir = Path(importlib.import_module("forelka").__file__).resolve().parent / "assets"
    assert assets_dir.exists()
    # At least one avatar file should be present.
    assert any(assets_dir.iterdir())


def test_modules_dir_exposes_builtin_commands():
    from forelka.modules import MODULES_DIR

    names = {p.stem for p in MODULES_DIR.glob("*.py") if p.stem != "__init__"}
    for expected in {"help", "owner", "lang", "updater", "ping"}:
        assert expected in names, f"missing built-in module: {expected}"


def test_main_module_has_main_entrypoint():
    # forelka.__main__ imports forelka.app which pulls in telethon — so we
    # just verify the file exists and declares a ``main`` import.
    import forelka

    main_file = Path(forelka.__file__).resolve().parent / "__main__.py"
    assert main_file.is_file()
    source = main_file.read_text(encoding="utf-8")
    assert "from forelka.app import main" in source
    assert "main()" in source
