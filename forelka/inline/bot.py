import asyncio
import aiohttp
import json
import os
import re
import sys
import html
from telethon import TelegramClient, events, Button

class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

class InlineBot:
    def __init__(self, kernel):
        self.kernel = kernel
        self.bot_client = None
        self.token = None
        self.username = None

    async def setup(self):
        self.token = self.kernel.config.get("inline_bot_token")
        self.username = self.kernel.config.get("inline_bot_username")
        if not self.token:
            await self.create_bot()
        else:
            await self.start_bot()

    async def create_bot(self):
        self.kernel.logger.info("Настройка инлайн-бота")
        choice = input(f"{Colors.YELLOW}1. Автоматически создать бота\n2. Ввести токен вручную\nВыберите (1/2): {Colors.RESET}").strip()
        if choice == "1": await self.auto_create_bot()
        elif choice == "2": await self.manual_setup()
        else: self.kernel.logger.error("Неверный выбор при создании бота")

    async def auto_create_bot(self):
        try:
            botfather = await self.kernel.client.get_entity("BotFather")
            while True:
                username = input(f"{Colors.YELLOW}Желаемый username для бота (без @): {Colors.RESET}").strip()
                if not username:
                    print(f"{Colors.RED}=X Username не может быть пустым{Colors.RESET}"); continue
                if not username.endswith(('bot', '_bot', 'Bot', '_Bot')):
                    username += '_bot'; print(f"{Colors.YELLOW}=? Username автоматически изменен на: {username}{Colors.RESET}")
                if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                    self.kernel.logger.error(f"Некорректный формат username: {username}"); continue
                break

            async def wait_for_botfather_response(max_wait=30):
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < max_wait:
                    messages = await self.kernel.client.get_messages(botfather, limit=3)
                    for msg in messages:
                        if hasattr(msg, "text") and msg.text: yield msg
                    await asyncio.sleep(2)

            await self.kernel.client.send_message(botfather, "/newbot")
            await asyncio.sleep(2)
            await self.kernel.client.send_message(botfather, "🪄 Forelka Inline Bot")
            await asyncio.sleep(2)
            await self.kernel.client.send_message(botfather, username)

            token = None; bot_username = None
            async for msg in wait_for_botfather_response(15):
                text = msg.text
                token_match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                if token_match and "token" in text.lower(): token = token_match.group(1)
                username_match_tme = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
                if username_match_tme: bot_username = username_match_tme.group(1)
                if "error" in text.lower() or "invalid" in text.lower():
                    self.kernel.logger.error(f"BotFather вернул ошибку: {text[:100]}"); return

            if not bot_username: bot_username = username
            if token and bot_username:
                self.token = token; self.username = bot_username
                self.kernel.logger.info(f"Получен токен для бота @{bot_username}")
                self.kernel.config["inline_bot_token"] = self.token
                self.kernel.config["inline_bot_username"] = self.username
                self.kernel.save_config()
                self.kernel.logger.info("Бот создан, настройка аватара...")
                
                await self.kernel.client.send_message(botfather, "/setuserpic")
                await asyncio.sleep(5)
                await self.kernel.client.send_message(botfather, f"@{bot_username}")
                await asyncio.sleep(5)
                
                from pathlib import Path as _Path
                assets_dir = _Path(__file__).resolve().parent.parent / "assets"
                candidates = [
                    assets_dir / "avatar_inline.jpg",
                    assets_dir / "avatar_inline.png",
                    assets_dir / "avatar.jpg",
                    assets_dir / "avatar.png",
                    _Path("assets/avatar_inline.jpg"),  # legacy cwd fallback
                ]
                avatar_path = next((str(p) for p in candidates if p.exists()), None)
                if avatar_path:
                    await self.kernel.client.send_file(botfather, avatar_path)
                    self.kernel.logger.info(f"Аватар установлен из {avatar_path}")
                else:
                    self.kernel.logger.warning(
                        f"Аватар не найден (искал в {assets_dir})"
                    )
                
                await asyncio.sleep(2)
                self.kernel.logger.info("Перезапуск для применения настроек...")
                os.execl(sys.executable, sys.executable, *sys.argv)
            else: self.kernel.logger.error("Не удалось получить данные бота из ответов BotFather")
        except Exception as e: self.kernel.logger.error(f"Ошибка создания бота: {str(e)}", exc_info=True)

    async def manual_setup(self):
        self.kernel.logger.info("Ручная настройка бота")
        while True:
            token = input(f"{Colors.YELLOW}Введите токен бота: {Colors.RESET}").strip()
            if not token: self.kernel.logger.error("Пустой токен при ручной настройке"); continue
            username = input(f"{Colors.YELLOW}Введите username бота (без @): {Colors.RESET}").strip()
            if not username: self.kernel.logger.error("Пустой username при ручной настройке"); continue
            if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username): self.kernel.logger.error(f"Некорректный формат username: {username}"); continue
            break

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.telegram.org/bot{token}/getMe") as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        actual_username = bot_info.get("username", "")
                        if actual_username.lower() != username.lower():
                            self.kernel.logger.warning(f"Введенный username ({username}) не совпадает с фактическим ({actual_username})")
                            username = actual_username
                        self.token = token; self.username = username
                        self.kernel.config["inline_bot_token"] = token
                        self.kernel.config["inline_bot_username"] = username
                        self.kernel.save_config()
                        self.kernel.logger.info(f"Бот проверен и сохранен: @{username}")
                        await self.start_bot()
                    else: self.kernel.logger.error(f"Неверный токен бота: {data.get('description', 'Неизвестная ошибка')}")
        except Exception as e: self.kernel.logger.error(f"Ошибка проверки токена: {str(e)}", exc_info=True)

    async def _apply_registered_handlers(self):
        """Применяет обработчики: системные (жёстко) + внешние (через kernel)"""
        
        # 1. Команды бота (/cmd) с проверкой владельца
        for cmd, (old_pattern, handler) in self.kernel.bot_command_handlers.items():
            pattern = f'/{cmd}(@{self.username})?$'
            self.kernel.bot_command_handlers[cmd] = (pattern, handler)
            async def owner_middleware(event, h=handler):
                if not self._is_owner(event.sender_id):
                    await event.reply(
                        "<blockquote>❌ <b>Доступ запрещен.</b>\nКоманда доступна только владельцам юзербота.</blockquote>",
                        parse_mode='html'
                    )
                    return
                await h(event)
            self.bot_client.add_event_handler(owner_middleware, events.NewMessage(pattern=pattern))

        # 2. Глобальный роутер сообщений (Фидбек + /start)
        @self.bot_client.on(events.NewMessage)
        async def global_message_router(event):
            if hasattr(event.client, 'feedback_reply_to'):
                from modules.feedback import owner_reply_handler
                await owner_reply_handler(event); return

            text = event.raw_text or ""
            user_id = event.sender_id
            if user_id in self.kernel.feedback_users:
                if not text.startswith('/') and not event.message.action and not event.message.out:
                    from modules.feedback import feedback_message_handler
                    await feedback_message_handler(event); return
                if not text.startswith('/start'): return

            if not text.startswith('/'): return
            command_match = re.match(r'^/(\w+)(@\w+)?$', text, re.IGNORECASE)
            if not command_match: return
                
            command = command_match.group(1).lower()
            if command in ("start", "feedback"):
                if command in self.kernel.bot_command_handlers:
                    _, handler = self.kernel.bot_command_handlers[command]
                    await handler(event)
                elif command == "start":
                    await _start_handler_impl(event, self)
                return

            if command in self.kernel.bot_command_handlers:
                _, handler = self.kernel.bot_command_handlers[command]
                await owner_middleware(event, handler)

        # 3. Инлайн-роутер: Системные триггеры → Внешние обработчики
        @self.bot_client.on(events.InlineQuery)
        async def inline_router(event):
            query = event.text.strip()
            
            # Системный trigger_
            if query.startswith("trigger_"):
                trigger_name = query[len("trigger_"):]
                handler = self.kernel.inline_trigger_handlers.get(trigger_name)
                if handler: await handler(event); return
                await event.answer([]); return

            # Внешние обработчики (останавливаемся на первом успешном)
            for ext_handler in self.kernel.inline_query_handlers:
                try:
                    if await _safe_invoke_handler(ext_handler, event, query): return
                except Exception as e:
                    self.kernel.logger.error(f"External inline handler error: {e}")
            
            await event.answer([])

        # 4. Колбэк-роутер: Системные (fb_, ai_) → Внешние обработчики
        @self.bot_client.on(events.CallbackQuery)
        async def callback_router(event):
            data = event.data.decode('utf-8')

            # Системный: Фидбек
            if data.startswith("fb_reply_"):
                try:
                    target_user_id = int(data.split("_")[2])
                    event.client.feedback_reply_to = target_user_id
                    await event.edit("<blockquote>✍️ Введите ваш ответ:</blockquote>", parse_mode='html', buttons=None)
                except Exception as e: await event.answer(f"Ошибка: {e}", alert=True)
                return
            if data.startswith("fb_delete_"):
                await event.delete(); return

            # Системный: AI Пагинация
            if data.startswith("ai_page_"):
                parts = data.split('_')
                if len(parts) < 4: return
                req_id, page_num = parts[2], int(parts[3])
                kernel = self.kernel
                if not hasattr(kernel, 'ai_pages') or req_id not in kernel.ai_pages:
                    await event.answer("Страницы не найдены или устарели", alert=True); return
                pages = kernel.ai_pages[req_id]
                if page_num < 1 or page_num > len(pages):
                    await event.answer("Неверная страница", alert=True); return

                page_text = pages[page_num - 1]
                escaped = html.escape(page_text)
                row1 = [Button.inline(str(i+1), data=f"ai_page_{req_id}_{i+1}") for i in range(min(5, len(pages)))]
                row2 = [Button.inline(str(i+1), data=f"ai_page_{req_id}_{i+1}") for i in range(5, min(10, len(pages)))]
                buttons = [row1] if not row2 else [row1, row2]
                
                await event.edit(f"<blockquote expandable><b>Ответ [стр {page_num}/{len(pages)}]:</b>\n<code>{escaped}</code></blockquote>", parse_mode='html', buttons=buttons)
                return

            # Системный: show_bot_commands
            if data == "show_bot_commands":
                await _show_commands_handler_impl(event)
                return

            # Внешние обработчики
            for ext_handler in self.kernel.callback_handlers:
                try:
                    if await _safe_invoke_handler(ext_handler, event, data): return
                except Exception as e:
                    self.kernel.logger.error(f"External callback handler error: {e}")
            
            await event.answer("⚠️ Кнопка не найдена или устарела", alert=True)

        self.kernel.logger.info(
            f"Applied {len(self.kernel.bot_command_handlers)} bot commands, "
            f"{len(self.kernel.inline_query_handlers)} inline handlers, "
            f"{len(self.kernel.callback_handlers)} callback handlers."
        )

    def _is_owner(self, user_id):
        config_path = f"config-{self.kernel.client._self_id}.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    owners = config.get("owners", [])
                    if self.kernel.client._self_id not in owners: owners.append(self.kernel.client._self_id)
                    return user_id in owners
            except: pass
        return user_id == self.kernel.client._self_id

    async def start_bot(self):
        if not self.token: self.kernel.logger.error("Токен бота не указан"); return
        try:
            self.kernel.logger.info("Запуск инлайн-бота...")
            api_id, api_hash = self.kernel.get_api_credentials()
            if not api_id or not api_hash: raise ValueError("API ID или Hash не найдены в конфигурации ядра.")
            self.bot_client = TelegramClient("inline_bot_session", api_id, api_hash)
            await self.bot_client.start(bot_token=self.token)
            me = await self.bot_client.get_me()
            self.username = me.username
            self.bot_client.kernel = self.kernel
            await self._apply_registered_handlers()
            self.kernel.logger.info(f"=> Инлайн-бот запущен @{self.username}")
            asyncio.create_task(self.bot_client.run_until_disconnected())
        except Exception as e: self.kernel.logger.error(f"Ошибка запуска инлайн-бота: {str(e)}", exc_info=True)

    async def stop_bot(self):
        if self.bot_client and self.bot_client.is_connected():
            await self.bot_client.disconnect()
            self.kernel.logger.info("Инлайн-бот остановлен")

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (вне класса, чтобы избежать проблем с декораторами) ===

async def _safe_invoke_handler(handler, event, data):
    """Вызывает обработчик. Поддерживает (event) и (event, data) -> bool"""
    try: return await handler(event, data)
    except TypeError: return await handler(event)

async def _start_handler_impl(event, inline_bot):
    buttons = [
        [Button.url("📦 Официальный репозиторий", "https://github.com/your-repo"),
         Button.url("👥 Группа поддержки", "https://t.me/your_support_chat")],
        [Button.inline("🤖 Команды бота", data="show_bot_commands")]
    ]
    await event.reply(
        "<blockquote><tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Привет!</b>\n"
        "Это юзербот <b>Forelka</b>!\nСпасибо за твой выбор!\n\n"
        "Ниже ты можешь ознакомиться с нашими разделами, а также вступить в группу поддержки юзербота.</blockquote>",
        buttons=buttons, parse_mode='html'
    )

async def _show_commands_handler_impl(event):
    commands_text = (
        "<blockquote><b>🤖 Команды инлайн-бота:</b>\n\n"
        "<b>/calc</b> - Калькулятор\n"
        "<b>/ping</b> - Проверка активности\n"
        "</blockquote>"
    )
    await event.edit(commands_text, parse_mode='html')