"""`.lang` command — switch userbot UI language per account.

Usage:
    .lang          — show current language and available options
    .lang ru       — switch to Russian
    .lang en       — switch to English
"""

from forelka.config import AccountConfig
from forelka.i18n import Translator, available_languages, for_client


async def lang_cmd(client, message, args):
    cfg = AccountConfig.load(client._self_id)
    langs = available_languages()

    if not args:
        available = ", ".join(f"<code>{code}</code>" for code in langs) or "—"
        return await message.edit(
            "<blockquote>🌐 <b>Language / Язык</b>\n\n"
            f"<b>Current:</b> <code>{cfg.lang}</code>\n"
            f"<b>Available:</b> {available}\n\n"
            "Usage: <code>.lang &lt;code&gt;</code></blockquote>",
            parse_mode="html",
        )

    new_lang = args[0].lower()
    if new_lang not in langs:
        return await message.edit(
            f"<blockquote>❌ Unknown language: <code>{new_lang}</code></blockquote>",
            parse_mode="html",
        )

    cfg.lang = new_lang
    cfg.save()

    # Build a translator for the new language so the confirmation is in it.
    tr = Translator(new_lang)
    _ = for_client  # keep import for downstream use
    await message.edit(
        f"<blockquote>{tr('common.ok')} — <code>{new_lang}</code></blockquote>",
        parse_mode="html",
    )


def register(app, commands, module_name):
    commands["lang"] = {"func": lang_cmd, "module": module_name}
