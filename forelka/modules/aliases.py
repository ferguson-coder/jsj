import html

from forelka.config import AccountConfig


def _escape(value):
    return html.escape(str(value)) if value is not None else ""


def _cfg(client) -> AccountConfig:
    return AccountConfig.load(client._self_id)


def _get_prefix(client) -> str:
    return _cfg(client).prefix


async def alias_cmd(client, message, args):
    pref = _get_prefix(client)

    if len(args) < 2:
        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</emoji> "
            f"<b>Usage:</b> <code>{_escape(pref)}alias &lt;name&gt; &lt;target&gt;</code></blockquote>",
            parse_mode='html'
        )
        return

    name = args[0].lower()
    target = args[1].lower()

    if target not in client.commands:
        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</emoji> "
            f"<b>Команда</b> <code>{_escape(target)}</code> <b>не найдена.</b></blockquote>",
            parse_mode='html'
        )
        return

    if name in client.commands:
        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</emoji> "
            f"<b>Имя</b> <code>{_escape(name)}</code> <b>уже занято командой.</b></blockquote>",
            parse_mode='html'
        )
        return

    cfg = _cfg(client)
    aliases = dict(cfg.aliases)
    aliases[name] = target
    cfg.aliases = aliases
    cfg.save()

    await message.edit(
        f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</emoji> "
        f"<b>Алиас создан:</b> <code>{_escape(pref)}{_escape(name)}</code> → "
        f"<code>{_escape(pref)}{_escape(target)}</code></blockquote>",
        parse_mode='html'
    )


async def delalias_cmd(client, message, args):
    pref = _get_prefix(client)

    if not args:
        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</emoji> "
            f"<b>Usage:</b> <code>{_escape(pref)}delalias &lt;name&gt;</code></blockquote>",
            parse_mode='html'
        )
        return

    name = args[0].lower()
    cfg = _cfg(client)
    aliases = dict(cfg.aliases)

    if name not in aliases:
        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</emoji> "
            f"<b>Алиас</b> <code>{_escape(name)}</code> <b>не найден.</b></blockquote>",
            parse_mode='html'
        )
        return

    del aliases[name]
    cfg.aliases = aliases
    cfg.save()

    await message.edit(
        f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</emoji> "
        f"<b>Алиас</b> <code>{_escape(name)}</code> <b>удалён.</b></blockquote>",
        parse_mode='html'
    )


async def aliases_cmd(client, message, args):
    pref = _get_prefix(client)
    aliases = _cfg(client).aliases

    if not aliases:
        await message.edit(
            "<blockquote><tg-emoji emoji-id=5897962422169243693>👻</emoji> "
            "<b>Нет алиасов.</b></blockquote>",
            parse_mode='html'
        )
        return

    lines = []
    for name, target in sorted(aliases.items()):
        lines.append(
            f"<code>{_escape(pref)}{_escape(name)}</code> → "
            f"<code>{_escape(pref)}{_escape(target)}</code>"
        )

    text = (
        "<tg-emoji emoji-id=5897962422169243693>👻</emoji> <b>Алиасы</b>\n\n"
        "<blockquote>" + "\n".join(lines) + "</blockquote>"
    )
    await message.edit(text, parse_mode='html')


def register(app, commands, module_name):
    commands["alias"] = {"func": alias_cmd, "module": module_name, "description": "Создать алиас команды"}
    commands["delalias"] = {"func": delalias_cmd, "module": module_name, "description": "Удалить алиас"}
    commands["aliases"] = {"func": aliases_cmd, "module": module_name, "description": "Список алиасов"}
