from telethon import Button

from forelka.modules.feedback import feedback_exit_on_start


async def bot_start_handler(event):
    if await feedback_exit_on_start(event):
        return

    buttons = [
        [
            Button.url("📦 Репозиторий", "https://github.com/ferguson-coder/jsj"),
            Button.url("👥 Поддержка", "https://t.me/your_support_chat"),
        ],
        [Button.inline("🤖 Команды", data="show_bot_commands")],
    ]
    await event.reply(
        "<blockquote><tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Привет!</b>\n"
        "Это юзербот <b>Forelka</b>!\nСпасибо за твой выбор!</blockquote>",
        buttons=buttons,
        parse_mode='html',
    )


async def show_commands_handler(event, data: str = "") -> bool:
    if data != "show_bot_commands":
        return False
    await event.edit(
        "<blockquote><b>🤖 Команды инлайн-бота:</b>\n\n"
        "<b>/calc</b> - Калькулятор\n"
        "<b>/ping</b> - Проверка активности\n"
        "</blockquote>",
        parse_mode='html',
    )
    return True


def register(app, commands, module_name, kernel=None):
    if kernel:
        kernel.register_bot_command("start", bot_start_handler)
        kernel.register_callback_handler(show_commands_handler)
