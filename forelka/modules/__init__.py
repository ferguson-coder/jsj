"""Built-in Forelka command modules.

Each module exposes::

    def register(app, commands, module_name, kernel=None):
        commands["<name>"] = {"func": <handler>, "module": module_name}

Modules are discovered and loaded by :mod:`forelka.core.loader` and
:mod:`forelka.app`.
"""

from __future__ import annotations

from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parent
