import os
import platform
import subprocess
import time

import requests

from forelka.config import AccountConfig

try:
    import psutil
    HAS_PSUTIL = True
except:
    HAS_PSUTIL = False

def detect_environment():
    """
    Определяет среду запуска: Termux, Userland, VDS/Linux
    Возвращает строку с названием среды и дополнительной информацией
    """
    # Termux (Android)
    prefix = os.environ.get('PREFIX', '')
    if prefix.startswith('/data/data/com.termux/files/usr'):
        termux_version = os.environ.get('TERMUX_VERSION', 'Unknown')
        return f"Termux {termux_version}"
    
    # Userland (Android chroot)
    # Проверяем наличие Android специфичных путей при Linux ядре
    if (os.path.exists('/system/bin') or 
        os.path.exists('/system/bin/app_process')) and platform.system() == 'Linux':
        return "Userland (Android chroot)"
    
    # Проверяем наличие Android kernel
    try:
        with open('/proc/version', 'r') as f:
            proc_version = f.read().lower()
            if 'android' in proc_version:
                return "Userland/Android"
    except:
        pass
    
    # VDS/Linux сервер
    # Пробуем определить тип виртуализации
    try:
        result = subprocess.run(
            ['systemd-detect-virt', '-v'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            virt_type = result.stdout.strip()
            virt_map = {
                'kvm': 'KVM VDS',
                'vmware': 'VMware VDS',
                'virtualbox': 'VirtualBox VDS',
                'xen': 'Xen VDS',
                'hyperv': 'Hyper-V VDS',
                'openvz': 'OpenVZ VPS',
                'lxc': 'LXC VPS',
                'docker': 'Docker Container',
                'none': 'Dedicated Server',
            }
            return virt_map.get(virt_type.lower(), 'VDS/Linux')
    except:
        pass
    
    # Если ничего не подошло - просто Linux
    return f"{platform.system()} {platform.release()}"

def upload_to_telegraph(image_url):
    """Загружает изображение на Telegraph и возвращает URL"""
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code != 200:
            return None

        files = {'file': ('image.jpg', response.content, 'image/jpeg')}
        upload = requests.post('https://telegra.ph/upload', files=files, timeout=10)

        if upload.status_code == 200:
            result = upload.json()
            if isinstance(result, list) and len(result) > 0:
                return f"https://telegra.ph{result[0]['src']}"
    except:
        pass
    return None

async def info_cmd(client, message, args):
    """Информация о юзерботе"""

    me = await client.get_me()
    owner_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
    if not owner_name:
        owner_name = "Unknown"

    cfg = AccountConfig.load(client._self_id)
    prefix = cfg.prefix
    quote_media = cfg.info_quote_media
    banner_url = cfg.info_banner_url
    invert_media = cfg.info_invert_media

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
    except:
        branch = "unknown"

    start_time = getattr(client, 'start_time', time.time())
    uptime_seconds = int(time.time() - start_time)
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    uptime_parts = []
    if days > 0:
        uptime_parts.append(f"{days}д")
    if hours > 0:
        uptime_parts.append(f"{hours}ч")
    if minutes > 0:
        uptime_parts.append(f"{minutes}м")
    uptime_parts.append(f"{seconds}с")
    uptime_str = " ".join(uptime_parts)

    if HAS_PSUTIL:
        try:
            process = psutil.Process()
            ram_usage_bytes = process.memory_info().rss
            ram_usage_mb = ram_usage_bytes / (1024 * 1024)
            ram_usage_str = f"{ram_usage_mb:.1f} MB"
        except:
            ram_usage_str = "N/A"
    else:
        ram_usage_str = "N/A"

    # Определяем среду запуска
    environment = detect_environment()

    info_text = f"""<blockquote><tg-emoji emoji-id=5461117441612462242>🔥</emoji> Forelka Userbot</blockquote>

<blockquote><tg-emoji emoji-id=5879770735999717115>👤</emoji> Владелец: {owner_name}</blockquote>

<blockquote><tg-emoji emoji-id=5778423822940114949>🌿</emoji> Branch: {branch}</blockquote>

<blockquote><tg-emoji emoji-id=5877396173135811032>⚙️</emoji> Prefix: «{prefix}»
<tg-emoji emoji-id=5778550614669660455>⏱</emoji> Uptime: {uptime_str}</blockquote>

<blockquote><tg-emoji emoji-id=5936130851635990622>💾</emoji> RAM usage: {ram_usage_str}
<tg-emoji emoji-id=5870982283724328568>🖥</emoji> Host: {environment}</blockquote>"""

    is_web_url = banner_url.startswith(("http://", "https://")) if banner_url else False
    is_local_file = os.path.exists(banner_url) if banner_url and not is_web_url else False

    reply_msg = await message.get_reply_message()
    reply_to = reply_msg.id if reply_msg else None

    await message.delete()

    try:
        if quote_media and is_web_url:
            # Убираем все HTML-теги вокруг самой ссылки
            # Ссылка должна быть чистой в начале текста
            text_with_link = f'{banner_url}\n\n{info_text}'

            await client.send_message(
                entity=message.chat_id,
                message=text_with_link,
                parse_mode='html',  # HTML применяется к info_text, но не к самой ссылке
                reply_to=reply_to,
                link_preview=True,
                invert_media=invert_media
            )

        elif is_local_file or (is_web_url and not quote_media):
            await client.send_file(
                entity=message.chat_id,
                file=banner_url,
                caption=info_text,
                parse_mode='html',
                reply_to=reply_to
            )

        else:
            await client.send_message(
                entity=message.chat_id,
                message=info_text,
                parse_mode='html',
                reply_to=reply_to
            )

    except Exception as e:
        await client.send_message(
            entity=message.chat_id,
            message=info_text,
            parse_mode='html',
            reply_to=reply_to
        )

async def setinfobanner_cmd(client, message, args):
    """Настройка баннера и quote media для команды info"""
    cfg = AccountConfig.load(client._self_id)

    if not args:
        quote_media = cfg.info_quote_media
        banner_url = cfg.info_banner_url or "не установлен"
        invert_media = cfg.info_invert_media

        return await message.edit(
            f"<blockquote><tg-emoji emoji-id=5897962422169243693>👻</emoji> <b>Info Banner Settings</b>\n\n"
            f"<b>Quote Media:</b> <code>{'✅ Enabled' if quote_media else '❌ Disabled'}</code>\n"
            f"<b>Invert Media:</b> <code>{'✅ ON (превью сверху)' if invert_media else '❌ OFF (превью снизу)'}</code>\n"
            f"<b>Banner URL:</b> <code>{banner_url}</code>\n\n"
            f"<b>Команды:</b>\n"
            f"<code>.setinfobanner [url]</code> - установить URL баннера\n"
            f"<code>.setinfobanner quote [on/off]</code> - quote media режим\n"
            f"<code>.setinfobanner invert [on/off]</code> - превью сверху/снизу\n"
            f"<code>.setinfobanner clear</code> - удалить настройки</blockquote>",
            parse_mode='html'
        )

    cmd = args[0].lower()

    if cmd == "invert":
        if len(args) < 2:
            return await message.edit(
                "<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</emoji> <b>Usage:</b> <code>.setinfobanner invert [on/off]</code></blockquote>",
                parse_mode='html'
            )

        state = args[1].lower()
        if state in ["on", "true", "1", "да", "yes"]:
            cfg.info_invert_media = True
            status = "✅ Включен (превью СВЕРХУ)"
        elif state in ["off", "false", "0", "нет", "no"]:
            cfg.info_invert_media = False
            status = "❌ Выключен (превью СНИЗУ)"
        else:
            return await message.edit(
                "<blockquote><tg-emoji emoji-id=5778527486270770928>❌</emoji> <b>Неверное значение. Используйте:</b> <code>on</code> или <code>off</code></blockquote>",
                parse_mode='html'
            )

        cfg.save()

        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</emoji> <b>Invert Media {status}</b></blockquote>",
            parse_mode='html'
        )

    elif cmd == "quote":
        if len(args) < 2:
            return await message.edit(
                "<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</emoji> <b>Usage:</b> <code>.setinfobanner quote [on/off]</code></blockquote>",
                parse_mode='html'
            )

        state = args[1].lower()
        if state in ["on", "true", "1", "да", "yes"]:
            cfg.info_quote_media = True
            status = "✅ Включен"
        elif state in ["off", "false", "0", "нет", "no"]:
            cfg.info_quote_media = False
            status = "❌ Выключен"
        else:
            return await message.edit(
                "<blockquote><tg-emoji emoji-id=5778527486270770928>❌</emoji> <b>Неверное значение. Используйте:</b> <code>on</code> или <code>off</code></blockquote>",
                parse_mode='html'
            )

        cfg.save()

        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</emoji> <b>Quote Media {status}</b></blockquote>",
            parse_mode='html'
        )

    elif cmd == "clear":
        cfg.info_banner_url = ""
        cfg.info_quote_media = False
        cfg.save()

        await message.edit(
            "<blockquote><tg-emoji emoji-id=5776375003280838798>✅</emoji> <b>Настройки баннера удалены</b></blockquote>",
            parse_mode='html'
        )

    else:
        banner_url = args[0]

        is_web_url = banner_url.startswith(("http://", "https://"))
        is_local_file = os.path.exists(banner_url)

        if not is_web_url and not is_local_file:
            return await message.edit(
                "<blockquote><tg-emoji emoji-id=5778527486270770928>❌</emoji> <b>Неверный URL или файл не найден</b></blockquote>",
                parse_mode='html'
            )

        cfg.info_banner_url = banner_url
        cfg.save()

        banner_type = "🌐 Web URL" if is_web_url else "📁 Local File"

        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</emoji> <b>Баннер установлен!</b>\n\n"
            f"<b>Type:</b> {banner_type}\n"
            f"<b>URL:</b> <code>{banner_url}</code>\n\n"
            f"💡 <b>Tip:</b> Используйте <code>.setinfobanner quote on</code> для включения quote media режима</blockquote>",
            parse_mode='html'
        )

def register(app, commands, module_name):
    """Регистрация команд"""
    commands["info"] = {"func": info_cmd, "module": module_name}
    commands["setinfobanner"] = {"func": setinfobanner_cmd, "module": module_name}