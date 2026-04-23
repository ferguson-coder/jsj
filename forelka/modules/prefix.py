from forelka.config import AccountConfig


async def prefix_cmd(client, message, args):
    cfg = AccountConfig.load(client._self_id)

    if not args:
        return await message.edit(
            f"<tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Settings</b>\n"
            f"<blockquote><b>Current prefix:</b> <code>{cfg.prefix}</code></blockquote>",
            parse_mode='html',
        )

    new_prefix = args[0][:3]
    cfg.prefix = new_prefix
    cfg.save()
    client.prefix = new_prefix
    await message.edit(
        f"<tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Settings</b>\n"
        f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> "
        f"<b>Prefix set to:</b> <code>{new_prefix}</code></blockquote>",
        parse_mode='html',
    )


def register(app, commands, module_name):
    commands["prefix"] = {"func": prefix_cmd, "module": module_name}
