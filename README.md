# Forelka

Telethon-based Telegram userbot with an inline control bot, hot-reloadable
modules, a Flask web login and per-account configuration.

## Quick start

```bash
# create & activate a venv (Python 3.10+)
python -m venv .venv
source .venv/bin/activate

# install (editable, so hot-reload / modules still work from repo)
pip install -e .

# first launch — web login will prompt for API ID/HASH/phone
python -m forelka
# (or, after `pip install`, just `forelka`)
```

Sessions are stored as `forelka-<user_id>.session` (legacy, kept for backward
compatibility) or under `accounts/<user_id>/` (new layout used by
`forelka.config.AccountConfig`). Both the session files and `loaded_modules/`
live in the current working directory, so pick a persistent data dir and
run `forelka` from it.

## Configuration — `forelka.config.AccountConfig`

Before this refactor every module read its own JSON config inline with
`open() + json.load() + except: pass`. All of that now goes through a single
typed manager:

```python
from forelka.config import AccountConfig

cfg = AccountConfig.load(client._self_id)   # cached
cfg.prefix                                   # "."
cfg.owners                                   # [123, 456]
cfg.aliases                                  # {"p": "ping"}
cfg.lang                                     # "ru"
cfg.management_group_id
cfg.management_topics

cfg.add_owner(42)
cfg.set_alias("h", "help")
cfg.lang = "en"
cfg.save()                                   # atomic write via os.replace
```

Highlights:

- **Typed dataclass** with sensible defaults — missing keys never raise.
- **Atomic writes** via `tempfile` + `os.replace` — a crashed save never
  leaves a half-written JSON.
- **In-memory cache** keyed by `user_id`; call `AccountConfig.invalidate()`
  on hot-reload.
- **Preserves unknown fields** in `cfg.extra` so an older checkout reading
  a newer config doesn't lose data.
- **Layout migration**: reads legacy `config-<user_id>.json` if present,
  writes to `accounts/<user_id>/config.json` going forward.

## Internationalisation — `forelka.i18n`

The UI was hardcoded in Russian. Strings now live in `locales/<lang>.json`:

```python
from forelka.i18n import t, Translator, for_client

t("cmd.update.checking", lang="en")        # "⌛️ Updating..."
tr = Translator("ru")
tr("cmd.update.error", error="boom")       # "❌ Ошибка: <code>boom</code>"
tr = for_client(client)                    # uses client's configured lang
```

Language is per account (`cfg.lang`) and can be switched from Telegram:

```
.lang          show current + available languages
.lang en       switch to English
.lang ru       switch back to Russian
```

Resolution order: requested lang → default lang (`ru`) → raw key. Missing
format placeholders never crash the caller — the unformatted string is
returned instead.

Adding a new language:

1. Drop a `locales/<code>.json` with the same shape as `ru.json`.
2. Run the tests: `pytest`.
3. Users can switch via `.lang <code>`.

## Development

```bash
pip install -e '.[dev]'
ruff check forelka tests
pytest
```

CI runs `ruff` + `pytest` on every push and PR.

## Project layout

```
forelka/                     # the package — everything lives in here now
  __init__.py                # re-exports AccountConfig, t, Translator, for_client
  __main__.py                # `python -m forelka` entrypoint
  app.py                     # main loop: session discovery, client start, dispatch
  cli.py                     # interactive TUI (`forelka-cli`)
  core/                      # shared infrastructure
    config.py                # AccountConfig — single source of truth for per-account state
    i18n.py                  # t(), Translator, for_client() — locale bundles
    kernel.py                # Kernel — per-client lifecycle, command registry
    loader.py                # .dlm / .addrepo — external module loader
    meta.py                  # module __meta__ parser (was meta_lib.py)
    database.py              # SQLite KV used by module configs
    utils.py                 # tiny helpers (prefix parsing, …)
  inline/
    bot.py                   # BotFather-automated inline helper bot
  web/
    app.py                   # Flask web login (API ID/HASH/phone + 2FA)
    tunnel.py                # SSH reverse tunnel via localhost.run
  modules/                   # hot-reloadable userbot commands
    help.py, owner.py, info.py, ping.py, lang.py, updater.py, …
  assets/                    # bundled static resources (avatar, …)
  locales/                   # i18n bundles
    ru.json
    en.json
tests/                       # pytest suite (config, i18n, package-layout smoke)
loaded_modules/              # user-installed third-party modules (cwd, gitignored)
accounts/<user_id>/          # per-account config + session (new layout, cwd)
```

Backwards-compatible shims keep `from forelka.config import AccountConfig` and
`from forelka.i18n import t` working — they now re-export from
`forelka.core.*`. Legacy cwd paths (`config-<id>.json`, `forelka-<id>.session`,
etc.) are still read on startup.

## Known limitations / roadmap

The big list of 20 planned improvements lives in the PR description that
introduced this refactor. Top priorities still outstanding:

- Move `.tsec` temp-access into SQLite so it survives restarts.
- Sandbox `.term` and verify downloaded modules before `exec`.
- Replace `sys.stdout = TerminalLogger()` with `logging` + rotation.
- Drop Pyrogram from the web login (keeps only Telethon).
- Docker / systemd packaging.
