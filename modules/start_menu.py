# modules/start_menu.py
from telethon import Button

async def start_inline_handler(event, query: str) -> bool:
    if query != "start":
        return False  # Передаём дальше другим обработчикам
    
    builder = event.builder
    result = builder.article(
        title="👻 Forelka Bot",
        text="Выберите раздел:",
        buttons=[
            [Button.inline("📦 Команды", data="show_commands")]
        ]
    )
    await event.answer([result])
    return True  # Запрос обработан

def register(app, commands, module_name, kernel=None):
    if kernel:
        kernel.register_inline_handler(start_inline_handler)