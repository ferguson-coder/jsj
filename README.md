# Forelka

Telethon-based Telegram userbot with an inline control bot, hot-reloadable
modules, a Flask web login and per-account configuration.

## Quick start

```bash
# create & activate a venv (Python 3.10+)
python -m venv .venv
source .venv/bin/activate

# install runtime deps
pip install -e .
# or: pip install -r <(python -c "import tomllib,sys; d=tomllib.load(open('pyproject.toml','rb')); print('\\n'.join(d['project']['dependencies']))")

# first launch — web login will prompt for API ID/HASH/phone
python main.py
```

Sessions are stored as `forelka-<user_id>.session` (legacy, kept for backward
compatibility) or under `accounts/<user_id>/` (new layout used by
`forelka.config.AccountConfig`).

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
forelka/         # shared infrastructure package
  config.py      # AccountConfig — single source of truth for per-account state
  i18n.py        # t(), Translator, for_client() — locale bundles
locales/
  ru.json        # default UI language
  en.json
modules/         # hot-reloadable userbot commands (owner, help, info, …)
  lang.py        # .lang command (new)
tests/           # pytest suite for forelka.*
main.py          # entry point — Telethon client, command dispatch
kernel.py        # Kernel — bot lifecycle, inline bot, command registry
loader.py        # .dlm / .addrepo — external module loader
webapp.py        # Flask web login (API ID/HASH/phone + 2FA)
tunnel.py        # SSH reverse tunnel via localhost.run
Updater.py       # .update / .restart
```

## Known limitations / roadmap

The big list of 20 planned improvements lives in the PR description that
introduced this refactor. Top priorities still outstanding:

- Move `.tsec` temp-access into SQLite so it survives restarts.
- Sandbox `.term` and verify downloaded modules before `exec`.
- Replace `sys.stdout = TerminalLogger()` with `logging` + rotation.
- Drop Pyrogram from the web login (keeps only Telethon).
- Docker / systemd packaging.
