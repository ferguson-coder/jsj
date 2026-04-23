import json
import os
import time
import asyncio
from telethon.tl.custom import Message
from telethon.tl.types import User

def _ensure_cleanup_task(client):
    """Запускает фоновую задачу очистки просроченных прав."""
    if not hasattr(client, 'temp_access'):
        client.temp_access = {}
    if not hasattr(client, 'temp_cleanup_task') or client.temp_cleanup_task.done():
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
    reply = await message.get_reply_message()
    
    if reply:
        # .tsec <сек> <команда> (через реплай)
        if len(args) < 2:
            return await message.edit(
                "<blockquote>❗️ <b>Usage:</b>\n\n<code>.tsec [сек] [команда]</code> (ответ на сообщение)\n"
                "Пример: <code>.tsec 60 calc</code></blockquote>",
                parse_mode='html'
            )
        try:
            duration = int(args[0])
            if duration <= 0: raise ValueError
        except ValueError:
            return await message.edit("<blockquote>❌ Неверное количество секунд</blockquote>", parse_mode='html')
            
        target_id = reply.sender_id
        target_name = (reply.sender.first_name or f"User {target_id}") if reply.sender else f"User {target_id}"
        command = args[1].lower().lstrip('.')
    else:
        # .tsec <сек> <user/@id> <команда>
        if len(args) < 3:
            return await message.edit(
                "<blockquote>❗️ <b>Usage:</b>\n\n<code>.tsec [сек] [@user|id] [команда]</code>\n"
                "Пример: <code>.tsec 60 @username term</code></blockquote>",
                parse_mode='html'
            )
        try:
            duration = int(args[0])
            if duration <= 0: raise ValueError
        except ValueError:
            return await message.edit("<blockquote>❌ Неверное количество секунд</blockquote>", parse_mode='html')
            
        user_arg = args[1]
        command = args[2].lower().lstrip('.')
        
        try:
            target_id = int(user_arg)
            target_name = f"User {target_id}"
        except ValueError:
            try:
                entity = await client.get_entity(user_arg)
                target_id = entity.id
                target_name = entity.first_name or f"User {target_id}"
            except Exception:
                return await message.edit("<blockquote>❌ Пользователь не найден</blockquote>", parse_mode='html')

    if target_id == client._self_id:
        return await message.edit("<blockquote>❌ Нельзя выдать доступ самому себе</blockquote>", parse_mode='html')
    if command not in client.commands:
        return await message.edit(f"<blockquote>❌ Команда <code>{command}</code> не найдена</blockquote>", parse_mode='html')

    expiry = time.time() + duration
    _ensure_cleanup_task(client)
    client.temp_access.setdefault(target_id, {})[command] = expiry

    await message.edit(
        f"<blockquote>✅ <b>Временный доступ выдан</b>\n\n"
        f"<b>Пользователь:</b> {target_name} [<code>{target_id}</code>]\n"
        f"<b>Команда:</b> <code>.{command}</code>\n"
        f"<b>Время:</b> {duration} сек.</blockquote>",
        parse_mode='html'
    )

async def addowner_cmd(client, message, args):
    if not args and not await message.get_reply_message():
        return await message.edit(
            "<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n"
            "<code>.addowner [user_id]</code> - добавить по ID\n"
            "<code>.addowner</code> (ответ на сообщение) - добавить пользователя</blockquote>",
            parse_mode='html'
        )
    reply_msg = await message.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
        user_name = (await reply_msg.get_sender()).first_name if reply_msg.sender else f"User {user_id}"
    else:
        try:
            user_id = int(args[0])
            user_name = f"User {user_id}"
        except:
            return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Неверный ID</b></blockquote>", parse_mode='html')

    config_path = f"config-{client._self_id}.json"
    config = {"prefix": "."}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f: config = json.load(f)
        except: pass

    owners = config.get("owners", [])
    if user_id in owners:
        return await message.edit(f"<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>{user_name}</b> уже является овнером</blockquote>", parse_mode='html')

    owners.append(user_id)
    config["owners"] = owners
    with open(config_path, "w") as f: json.dump(config, f, indent=4)

    await message.edit(
        f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Овнер добавлен!</b>\n\n"
        f"<b>User:</b> <code>{user_name}</code>\n<b>ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Всего овнеров:</b> <code>{len(owners)}</code></blockquote>",
        parse_mode='html'
    )

async def delowner_cmd(client, message, args):
    if not args and not await message.get_reply_message():
        return await message.edit(
            "<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n"
            "<code>.delowner [user_id]</code> - удалить по ID\n"
            "<code>.delowner</code> (ответ на сообщение) - удалить пользователя</blockquote>",
            parse_mode='html'
        )
    reply_msg = await message.get_reply_message()
    if reply_msg:
        user_id = reply_msg.sender_id
    else:
        try:
            user_id = int(args[0])
        except:
            return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Неверный ID</b></blockquote>", parse_mode='html')

    if user_id == client._self_id:
        return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Нельзя удалить владельца бота</b></blockquote>", parse_mode='html')

    config_path = f"config-{client._self_id}.json"
    config = {"prefix": "."}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f: config = json.load(f)
        except: pass

    owners = config.get("owners", [])
    if user_id not in owners:
        return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Пользователь не является овнером</b></blockquote>", parse_mode='html')

    owners.remove(user_id)
    config["owners"] = owners
    with open(config_path, "w") as f: json.dump(config, f, indent=4)

    await message.edit(
        f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Овнер удален!</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n\n"
        f"<b>Осталось овнеров:</b> <code>{len(owners)}</code></blockquote>",
        parse_mode='html'
    )

async def owners_cmd(client, message, args):
    config_path = f"config-{client._self_id}.json"
    config = {"prefix": "."}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f: config = json.load(f)
        except: pass
    owners = config.get("owners", [])
    if client._self_id not in owners: owners.insert(0, client._self_id)
    if not owners:
        return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Нет добавленных овнеров</b></blockquote>", parse_mode='html')

    text = "<tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Список овнеров</b>\n\n"
    for i, owner_id in enumerate(owners, 1):
        if owner_id == client._self_id:
            text += f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <code>{owner_id}</code> (Владелец бота)</blockquote>\n"
        else:
            text += f"<blockquote><tg-emoji emoji-id=5877468380125990242>➡️</tg-emoji> <code>{owner_id}</code></blockquote>\n"
    text += f"\n<b>Всего:</b> <code>{len(owners)}</code> овнеров"
    await message.edit(text, parse_mode='html')

def register(app, commands, module_name):
    commands["tsec"] = {"func": tsec_cmd, "module": module_name}
    commands["addowner"] = {"func": addowner_cmd, "module": module_name}
    commands["delowner"] = {"func": delowner_cmd, "module": module_name}
    commands["owners"] = {"func": owners_cmd, "module": module_name}