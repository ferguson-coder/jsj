import asyncio
import os
import sys

from telethon import Button

from forelka.config import AccountConfig


async def restart_cmd(client, message, args):
    """Команда .restart через инлайн-запрос."""
    kernel = client.kernel

    if not hasattr(kernel, 'inline_bot') or not kernel.inline_bot:
        await message.edit("❌ Инлайн-бот не настроен.")
        return

    try:
        await asyncio.sleep(0.1)
        await kernel.inline_query_and_click(
            chat_id=message.chat_id,
            query="restart",
        )
        await message.delete()
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


# === Обработчик инлайн-запроса для рестарта ===
async def restart_inline_handler(event, query: str = "") -> bool:
    if query != "restart":
        return False

    kernel = event.client.kernel
    user_id = event.sender_id

    if not is_owner(kernel, user_id):
        builder = event.builder
        no_access = builder.article(
            title="🔒 Доступ запрещён",
            text="<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Доступ запрещён.</b></blockquote>",
            parse_mode='html',
        )
        await event.answer([no_access])
        return True

    builder = event.builder
    result = builder.article(
        title="🔄 Перезагрузка юзербота",
        text=(
            "<blockquote><b>🔄 Подтверждение перезагрузки</b>\n"
            "Вы уверены, что хотите перезагрузить юзербота?</blockquote>"
        ),
        parse_mode='html',
        buttons=[
            [
                Button.inline("✅ Подтвердить", data="restart_confirm"),
                Button.inline("❌ Отмена", data="restart_cancel"),
            ]
        ],
    )
    await event.answer([result])
    return True


# === Обработчик кнопок рестарта ===
async def restart_callback_handler(event, data: str = "") -> bool:
    if data not in ("restart_confirm", "restart_cancel"):
        return False

    kernel = event.client.kernel
    user_id = event.sender_id

    if not is_owner(kernel, user_id):
        await event.answer("Доступ запрещён!", alert=True)
        return True

    if data == "restart_confirm":
        await event.edit(
            "<blockquote><tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> "
            "<b>Перезагрузка...</b>\nЮзербот будет перезапущен.</blockquote>",
            parse_mode='html',
        )
        await perform_restart(kernel)
    elif data == "restart_cancel":
        await event.delete()
    return True


async def perform_restart(kernel):
    """Перезапускает процесс юзербота через ``python -m forelka``."""
    if kernel.client and kernel.client.is_connected():
        await kernel.client.disconnect()
    os.execv(sys.executable, [sys.executable, "-m", "forelka"])


def is_owner(kernel, user_id):
    return AccountConfig.load(kernel.client._self_id).is_owner(user_id)


# === Регистрация ===
def register(app, commands, module_name, kernel=None):
    commands["restart"] = {"func": restart_cmd, "module": module_name}

    if kernel is not None:
        kernel.register_inline_handler(restart_inline_handler)
        kernel.register_callback_handler(restart_callback_handler)
