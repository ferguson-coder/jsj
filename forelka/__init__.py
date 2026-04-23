"""Forelka — Telethon-based Telegram userbot framework.

Package layout::

    forelka/
        app.py           # main loop (wired by __main__.py)
        cli.py           # interactive TUI
        core/            # shared infrastructure
            config.py    # AccountConfig — per-account typed config
            i18n.py      # t() / Translator — locale lookup
            kernel.py    # Kernel — per-client lifecycle
            loader.py    # external module loader (.dlm / .addrepo)
            meta.py      # module __meta__ parser
            database.py  # SQLite KV for module state
            utils.py     # tiny helpers (prefix parser, ...)
        inline/
            bot.py       # inline helper bot (BotFather automation)
        web/
            app.py       # Flask web login
            tunnel.py    # SSH reverse tunnel
        modules/         # hot-reloadable user-facing commands
        assets/          # static resources (avatar, ...)
        locales/         # i18n bundles
"""

from forelka.core.config import AccountConfig
from forelka.core.i18n import Translator, for_client, t

__all__ = ["AccountConfig", "Translator", "for_client", "t"]
__version__ = "2.0.0"
