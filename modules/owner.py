import asyncio
import time

from telethon.tl.custom import Message  # noqa: F401  (re-exported for module contract)
from telethon.tl.types import User  # noqa: F401

from forelka.config import AccountConfig
from forelka.i18n import for_client


def _ensure_cleanup_task(client):
    """Запускает фоновую задачу очистки просроченных прав."""
    if not hasattr(client, "temp_access"):
        client.temp_access = {}
    if not hasattr(client, "temp_cleanup_task") or client.temp_cleanup_task.done():
        async def _cleanup_loop():
            while True:
                await asyncio.sleep(15)
                now = time.time()
                temp = client.temp_access
                to_remove = []
                for uid, cmds in temp.items():
                    expired = [c for c, exp in cmds.items() if now >= exp]
                    for c in expired:
                        del cmds[c]
                    if not cmds:
                        to_remove.append(uid)
                for uid in to_remove:
                    del temp[uid]

        client.temp_cleanup_task = asyncio.create_task(_cleanup_loop())


async def tsec_cmd(client, message, args):
    """Выдает временный доступ к команде."""
    tr = for_client(client)
    reply = await message.get_reply_message()

    if reply:
        if len(args) < 2:
            return await message.edit(
                f"<blockquote>{tr('cmd.tsec.usage_reply')}</blockquote>",
                parse_mode="html",
            )
        try:
            duration = int(args[0])
            if duration <= 0:
                raise ValueError
        except ValueError:
            return await message.edit(
                f"<blockquote>{tr('cmd.tsec.bad_seconds')}</blockquote>",
                parse_mode="html",
            )

        target_id = reply.sender_id
        target_name = (
            (reply.sender.first_name or f"User {target_id}") if reply.sender else f"User {target_id}"
        )
        command = args[1].lower().lstrip(".")
    else:
        if len(args) < 3:
            return await message.edit(
                f"<blockquote>{tr('cmd.tsec.usage_args')}</blockquote>",
                parse_mode="html",
            )
        try:
            duration = int(args[0])
            if duration <= 0:
                raise ValueError
        except ValueError:
            return await message.edit(
                f"<blockquote>{tr('cmd.tsec.bad_seconds')}</blockquote>",
                parse_mode="html",
            )

        user_arg = args[1]
        command = args[2].lower().lstrip(".")

        try:
            target_id = int(user_arg)
            target_name = f"User {target_id}"
        except ValueError:
            try:
                entity = await client.get_entity(user_arg)
                target_id = entity.id
                target_name = entity.first_name or f"User {target_id}"
            except Exception:
                return await message.edit(
                    f"<blockquote>{tr('cmd.tsec.user_not_found')}</blockquote>",
                    parse_mode="html",
                )

    if target_id == client._self_id:
        return await message.edit(
            f"<blockquote>{tr('cmd.tsec.self_forbidden')}</blockquote>",
            parse_mode="html",
        )
    if command not in client.commands:
        return await message.edit(
            f"<blockquote>{tr('cmd.tsec.unknown_command', command=command)}</blockquote>",
            parse_mode="html",
        )

    expiry = time.time() + duration
    _ensure_cleanup_task(client)
    client.temp_access.setdefault(target_id, {})[command] = expiry

    await message.edit(
        f"<blockquote>"
        f"{tr('cmd.tsec.granted', name=target_name, id=target_id, command=command, seconds=duration)}"
        f"</blockquote>",
        parse_mode="html",
    )


async def addowner_cmd(client, message, args):
    tr = for_client(client)
    if not args and not await message.get_reply_message():
        return await message.edit(
            f"<blockquote>{tr('cmd.owner.add_usage')}</blockquote>",
            parse_mode="html",
        )
    reply_msg = await message.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
        user_name = (
            (await reply_msg.get_sender()).first_name
            if reply_msg.sender
            else f"User {user_id}"
        )
    else:
        try:
            user_id = int(args[0])
            user_name = f"User {user_id}"
        except (ValueError, IndexError):
            return await message.edit(
                f"<blockquote>{tr('cmd.owner.invalid_id')}</blockquote>",
                parse_mode="html",
            )

    cfg = AccountConfig.load(client._self_id)
    if not cfg.add_owner(user_id):
        return await message.edit(
            f"<blockquote>{tr('cmd.owner.already_owner')}: <b>{user_name}</b></blockquote>",
            parse_mode="html",
        )
    cfg.save()

    await message.edit(
        f"<blockquote>"
        f"{tr('cmd.owner.added', name=user_name, id=user_id)}\n\n"
        f"<b>Всего овнеров:</b> <code>{len(cfg.owners)}</code>"
        f"</blockquote>",
        parse_mode="html",
    )


async def delowner_cmd(client, message, args):
    tr = for_client(client)
    if not args and not await message.get_reply_message():
        return await message.edit(
            "<blockquote>❗️ <b>Usage:</b>\n\n"
            "<code>.delowner [user_id]</code> — удалить по ID\n"
            "<code>.delowner</code> (ответом на сообщение) — удалить пользователя</blockquote>",
            parse_mode="html",
        )
    reply_msg = await message.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
    else:
        try:
            user_id = int(args[0])
        except (ValueError, IndexError):
            return await message.edit(
                f"<blockquote>{tr('cmd.owner.invalid_id')}</blockquote>",
                parse_mode="html",
            )

    if user_id == client._self_id:
        return await message.edit(
            "<blockquote>❌ <b>Нельзя удалить владельца бота</b></blockquote>",
            parse_mode="html",
        )

    cfg = AccountConfig.load(client._self_id)
    if not cfg.remove_owner(user_id):
        return await message.edit(
            "<blockquote>❌ <b>Пользователь не является овнером</b></blockquote>",
            parse_mode="html",
        )
    cfg.save()

    await message.edit(
        "<blockquote>✅ <b>Овнер удалён!</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Осталось овнеров:</b> <code>{len(cfg.owners)}</code></blockquote>",
        parse_mode="html",
    )


async def owners_cmd(client, message, args):
    cfg = AccountConfig.load(client._self_id)
    owners = list(cfg.owners)
    if client._self_id not in owners:
        owners.insert(0, client._self_id)
    if not owners:
        return await message.edit(
            "<blockquote>❗️ <b>Нет добавленных овнеров</b></blockquote>",
            parse_mode="html",
        )

    text = "👻 <b>Список овнеров</b>\n\n"
    for owner_id in owners:
        if owner_id == client._self_id:
            text += f"<blockquote>✅ <code>{owner_id}</code> (Владелец бота)</blockquote>\n"
        else:
            text += f"<blockquote>➡️ <code>{owner_id}</code></blockquote>\n"
    text += f"\n<b>Всего:</b> <code>{len(owners)}</code> овнеров"
    await message.edit(text, parse_mode="html")


def register(app, commands, module_name):
    commands["tsec"] = {"func": tsec_cmd, "module": module_name}
    commands["addowner"] = {"func": addowner_cmd, "module": module_name}
    commands["delowner"] = {"func": delowner_cmd, "module": module_name}
    commands["owners"] = {"func": owners_cmd, "module": module_name}
