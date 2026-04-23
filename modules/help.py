import html
import os
import sys
import json
from telethon import events, Button

def _escape(v):
    return html.escape(str(v)) if v is not None else ""

def _get_prefix(client):
    p = getattr(client, "prefix", None)
    if p: return p
    path = f"config-{client._self_id}.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("prefix", ".")
        except: pass
    return "."

def _is_owner(client, user_id):
    """Проверяет, является ли user_id владельцем бота."""
    path = f"config-{client._self_id}.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                owners = cfg.get("owners", [])
                if client._self_id not in owners:
                    owners.append(client._self_id)
                return user_id in owners
        except: pass
    return user_id == client._self_id

def _collect_modules(client):
    sys_mods, ext_mods = {}, {}
    for cmd_name, info in client.commands.items():
        mod = info.get("module", "unknown")
        fpath = getattr(sys.modules.get(mod), "__file__", "")
        target = ext_mods if "loaded_modules" in fpath else sys_mods
        target.setdefault(mod, []).append(cmd_name)
    for d in (sys_mods, ext_mods):
        for cmds in d.values():
            cmds.sort()
    return sys_mods, ext_mods

def _get_paginated_modules(client, page=1, page_size=10):
    sys_mods, ext_mods = _collect_modules(client)
    all_mods = []
    for m, c in sys_mods.items(): all_mods.append((m, c, True))
    for m, c in ext_mods.items(): all_mods.append((m, c, False))
    all_mods.sort(key=lambda x: x[0])

    total = len(all_mods)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    
    start = (page - 1) * page_size
    page_mods = all_mods[start:start + page_size]
    
    sys_page = {m: c for m, c, is_sys in page_mods if is_sys}
    ext_page = {m: c for m, c, is_sys in page_mods if not is_sys}
    return sys_page, ext_page, page, total_pages

def _build_template(sys_mods, ext_mods, pref, page, total_pages):
    lines = [f"<tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Forelka Modules</b> ({page}/{total_pages})\n"]
    
    lines.append("<b>System:</b>")
    if sys_mods:
        for m, cmds in sorted(sys_mods.items()):
            c = " | ".join([f"{pref}{x}" for x in cmds])
            lines.append(f"<blockquote>➡️ <b>{_escape(m)}</b> (<code>{_escape(c)}</code>)</blockquote>")
    else:
        lines.append("<blockquote>Нет системных модулей</blockquote>")

    lines.append("\n<b>External:</b>")
    if ext_mods:
        for m, cmds in sorted(ext_mods.items()):
            c = " | ".join([f"{pref}{x}" for x in cmds])
            lines.append(f"<blockquote>➡️ <b>{_escape(m)}</b> (<code>{_escape(c)}</code>)</blockquote>")
    else:
        lines.append("<blockquote>Нет внешних модулей</blockquote>")
        
    return "\n".join(lines)

# === КОМАНДА .help ===
async def help_cmd(client, message, args):
    kernel = client.kernel
    if not hasattr(kernel, 'inline_bot') or not kernel.inline_bot:
        return await message.edit("❌ Инлайн-бот не настроен.")
    try:
        await kernel.inline_query_and_click(chat_id=message.chat_id, query="help")
        await message.delete()
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")

# === ИНЛАЙН-ОБРАБОТЧИК ===
async def help_inline_handler(event, query: str = ""):
    if not query.lower().startswith("help"):
        return False  # Передаём дальше

    page = 1
    if ":" in query:
        try: page = int(query.split(":")[1])
        except: pass

    kernel = getattr(event.client, 'kernel', None)
    if not kernel or not hasattr(kernel, 'client'):
        return False
    client = kernel.client

    # 🔒 ПРОВЕРКА ВЛАДЕЛЬЦА
    if not _is_owner(client, event.sender_id):
        builder = event.builder
        await event.answer([builder.article(
            title="🔒 Доступ запрещён",
            text="<blockquote>Эта функция доступна только владельцам юзербота.</blockquote>",
            parse_mode='html'
        )])
        return True

    pref = _get_prefix(client)
    sys_page, ext_page, cur_page, total_pages = _get_paginated_modules(client, page)
    text = _build_template(sys_page, ext_page, pref, cur_page, total_pages)

    builder = event.builder
    buttons = []
    if total_pages > 1:
        row = []
        if cur_page > 1: row.append(Button.inline("⬅️", data=f"help_page:{cur_page-1}"))
        row.append(Button.inline(f"{cur_page}/{total_pages}", data="noop"))
        if cur_page < total_pages: row.append(Button.inline("➡️", data=f"help_page:{cur_page+1}"))
        buttons.append(row)

    await event.answer([builder.article(
        title="📚 Forelka Modules",
        description=f"Страница {cur_page} из {total_pages}",
        text=text,
        parse_mode='html',
        buttons=buttons if buttons else None
    )])
    return True

# === КАЛБЭК-ОБРАБОТЧИК (ПАГИНАЦИЯ) ===
async def help_callback_handler(event, data: str = ""):
    if not data.startswith("help_page:"):
        return False  # Не наш триггер
    
    try:
        new_page = int(data.split(":")[1])
        kernel = getattr(event.client, 'kernel', None)
        if not kernel or not hasattr(kernel, 'client'):
            return False
        client = kernel.client

        # 🔒 ПОВТОРНАЯ ПРОВЕРКА ВЛАДЕЛЬЦА (КНОПКИ МОГУТ НАЖАТЬ ВСЕ)
        if not _is_owner(client, event.sender_id):
            await event.answer("❌ Доступ запрещён.", alert=True)
            return True
        
        pref = _get_prefix(client)
        sys_page, ext_page, cur_page, total_pages = _get_paginated_modules(client, new_page)
        text = _build_template(sys_page, ext_page, pref, cur_page, total_pages)

        buttons = []
        if total_pages > 1:
            row = []
            if cur_page > 1: row.append(Button.inline("⬅️", data=f"help_page:{cur_page-1}"))
            row.append(Button.inline(f"{cur_page}/{total_pages}", data="noop"))
            if cur_page < total_pages: row.append(Button.inline("➡️", data=f"help_page:{cur_page+1}"))
            buttons.append(row)

        await event.edit(f"<blockquote>{text}</blockquote>", parse_mode='html', buttons=buttons if buttons else None)
    except Exception:
        await event.answer("Ошибка навигации", alert=True)
    return True

# === РЕГИСТРАЦИЯ ===
def register(app, commands, module_name, kernel=None):
    commands["help"] = {"func": help_cmd, "module": module_name}
    if kernel is not None:
        kernel.register_inline_handler(help_inline_handler)
        kernel.register_callback_handler(help_callback_handler)