import html
import importlib.util
import inspect
import json
import os
import sys
import subprocess
import requests
from telethon import events

from forelka.config import AccountConfig
from forelka.i18n import for_client
from meta_lib import extract_command_descriptions, read_module_meta

REPOS_FILE = "repos.json"

def _personal_folder(client):
    folder = "loaded_modules"
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder

def is_protected(name):
    return os.path.exists(f"modules/{name}.py") or name in ["loader", "main"]

def _escape(value):
    return html.escape(str(value)) if value is not None else ""

def _get_prefix(client):
    pref = getattr(client, "prefix", None)
    if pref:
        return pref
    return AccountConfig.load(client._self_id).prefix

def _module_commands(app, module_name):
    cmds = [c for c, v in app.commands.items() if v.get("module") == module_name]
    cmds.sort()
    return cmds

def _first_line(text):
    if not text:
        return ""
    return str(text).strip().splitlines()[0].strip()

def _install_dependencies(requires, module_name=""):
    if not requires:
        return True, []
    missing = []
    for pkg in requires:
        if not _is_package_installed(pkg):
            missing.append(pkg)
    if not missing:
        return True, []
    try: 
        module_desc = f" для {module_name}" if module_name else ""
        print(f"[pip] Установка зависимостей{module_desc}: {', '.join(missing)}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade"] + missing,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Неизвестная ошибка"
            print(f"[pip] Ошибка установки: {error_msg}")
            return False, missing
        still_missing = [p for p in missing if not _is_package_installed(p)]
        if still_missing:
            print(f"[pip] Не удалось установить: {', '.join(still_missing)}")
            return False, still_missing
        print(f"[pip] Зависимости установлены успешно")
        return True, []
    except subprocess.TimeoutExpired:
        print(f"[pip] Таймаут установки зависимостей")
        return False, missing
    except Exception as e:
        print(f"[pip] Ошибка: {type(e).__name__}: {e}")
        return False, missing

def _is_package_installed(pkg_spec):
    import re
    match = re.match(r'^([a-zA-Z0-9_-]+)(.*)$', pkg_spec.strip())
    if not match: return False
    pkg_name = match.group(1).lower().replace('-', '_')
    version_spec = match.group(2).strip()
    try:
        try:
            from importlib.metadata import version, PackageNotFoundError
        except ImportError:
            from importlib_metadata import version, PackageNotFoundError
        installed_ver = version(pkg_name)
        if not version_spec: return True
        return _check_version(installed_ver, version_spec)
    except (PackageNotFoundError, ImportError, ModuleNotFoundError):
        return False
    except Exception:
        return False

def _check_version(installed_ver, spec):
    import re
    match = re.match(r'^([<>=~!]+)?\s*([0-9][0-9a-zA-Z.]*)?(.*)$', spec)
    if not match: return True
    op = match.group(1) or ""
    required_ver = match.group(2) or ""
    def parse_version(v):
        parts = []
        for p in re.split(r'[.-]', v):
            try: parts.append(int(p))
            except ValueError: parts.append(p)
        return parts
    inst_parts = parse_version(installed_ver)
    req_parts = parse_version(required_ver)
    try:
        if op == ">=": return inst_parts >= req_parts
        elif op == "<=": return inst_parts <= req_parts
        elif op == "==": return inst_parts == req_parts
        elif op == "!=": return inst_parts != req_parts
        elif op == ">": return inst_parts > req_parts
        elif op == "<": return inst_parts < req_parts
        elif op == "~=":
            if len(req_parts) >= 2: return inst_parts >= req_parts and inst_parts[:len(req_parts)-1] == req_parts[:len(req_parts)-1]
            return inst_parts >= req_parts
        else: return True
    except (TypeError, ValueError): return True

def _get_module_requires(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        import re
        meta_match = re.search(r'__meta__\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if meta_match:
            meta_content = meta_match.group(1)
            requires_match = re.search(r'["\']requires["\']\s*:\s*\[([^\]]+)\]', meta_content)
            if requires_match:
                requires_str = requires_match.group(1)
                requires = re.findall(r'["\']([^"\']+)["\']', requires_str)
                if requires: return requires
        requires_match = re.search(r'__requires__\s*=\s*\[([^\]]+)\]', content)
        if requires_match:
            requires_str = requires_match.group(1)
            requires = re.findall(r'["\']([^"\']+)["\']', requires_str)
            if requires: return requires
        requires_match = re.search(r'__requires__\s*=\s*["\']([^"\']+)["\']', content)
        if requires_match:
            requires_str = requires_match.group(1)
            requires = re.split(r'[,\s]+', requires_str)
            requires = [r.strip() for r in requires if r.strip()]
            if requires: return requires
    except Exception as e:
        print(f"[!] Ошибка чтения зависимостей из {path}: {e}")
    return []

def _command_descriptions(app, module_name, commands):
    module = sys.modules.get(module_name)
    raw_meta = getattr(module, "__meta__", None) if module else None
    meta_descs = extract_command_descriptions(raw_meta)
    result = {}
    for cmd in commands:
        key = cmd.lower()
        desc = ""
        info = app.commands.get(cmd, {})
        if isinstance(info, dict):
            desc = info.get("description") or info.get("desc") or info.get("about") or info.get("help") or ""
            desc = _first_line(desc)
        if not desc: desc = meta_descs.get(key, "")
        if not desc:
            func = app.commands.get(cmd, {}).get("func")
            desc = _first_line(getattr(func, "__doc__", ""))
        result[key] = desc
    return result

def _format_meta_block(app, module_name):
    module = sys.modules.get(module_name)
    commands = _module_commands(app, module_name)
    meta = read_module_meta(module, module_name, commands)
    display = meta.get("name") or module_name
    author = meta.get("author") or "Не указан"
    description = _first_line(meta.get("description")) or "Нет описания"
    pref = _get_prefix(app)
    cmd_descs = _command_descriptions(app, module_name, commands)
    if commands:
        lines = []
        for cmd in commands:
            desc = cmd_descs.get(cmd.lower()) or "нет описания"
            lines.append(f"{_escape(pref + cmd)} — {_escape(desc)}")
        cmds_block = "\n".join(lines)
    else:
        cmds_block = _escape("Нет команд")
    loaded_line = f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Модуль</b> <code>{_escape(display)}</code> <b>загружен</b></blockquote>"
    desc_line = f"<blockquote><tg-emoji emoji-id=5877396173135811032>⚙️</tg-emoji> <b>Описание:</b> {_escape(description)}</blockquote>"
    commands_block = f"<blockquote expandable><code>{cmds_block}</code></blockquote>"
    author_line = f"<blockquote><tg-emoji emoji-id=5879770735999717115>👤</tg-emoji> <b>Разработчик:</b> <code>{_escape(author)}</code></blockquote>"
    return f"{loaded_line}\n{desc_line}\n\n{commands_block}\n\n{author_line}"

def load_repos():
    if os.path.exists(REPOS_FILE):
        try:
            with open(REPOS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return []

def save_repos(repos):
    with open(REPOS_FILE, "w", encoding="utf-8") as f: json.dump(repos, f, indent=2, ensure_ascii=False)

async def addrepo_cmd(client, message, args):
    if not args:
        repos = load_repos()
        if repos:
            repo_list = "\n".join([f" • <code>{r}</code>" for r in repos])
            await message.edit(f"<blockquote><tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Список репозиториев:</b>\n{repo_list}</blockquote>", parse_mode='html')
        else:
            await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Нет добавленных репозиториев</b></blockquote>", parse_mode='html')
        return
    repo_url = args[0].rstrip('/')
    if not repo_url.startswith(("http://", "https://")):
        return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>URL должен начинаться с http:// или https://</b></blockquote>", parse_mode='html')
    repos = load_repos()
    if repo_url in repos:
        return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Репозиторий уже добавлен.</b></blockquote>", parse_mode='html')
    repos.append(repo_url)
    save_repos(repos)
    await message.edit(f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Репозиторий добавлен:</b> <code>{repo_url}</code>\n\nТеперь можно пробовать .dlm имя_модуля</blockquote>", parse_mode='html')

async def dlm_cmd(client, message, args):
    if len(args) < 1:
        return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n<code>.dlm [module_name]</code> или <code>.dlm https://.../module.py</code></blockquote>", parse_mode='html')
    input_str = args[0].strip()
    if input_str.startswith(("http://", "https://")) and input_str.lower().endswith(".py"):
        download_url = input_str
        module_name = os.path.basename(input_str)[:-3].lower()
        if is_protected(module_name): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Access Denied</b></blockquote>", parse_mode='html')
        folder = _personal_folder(client)
        path = f"{folder}/{module_name}.py"
        try:
            await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Загрузка по прямой ссылке: {module_name}...</b></blockquote>", parse_mode='html')
            r = requests.get(download_url, timeout=15); r.raise_for_status()
            with open(path, "wb") as f: f.write(r.content)
            requires = _get_module_requires(path)
            if requires:
                await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Проверка зависимостей...</b></blockquote>", parse_mode='html')
                success, missing = _install_dependencies(requires, module_name)
                if not success:
                    os.remove(path)
                    return await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Не удалось установить зависимости:</b> <code>{', '.join(missing)}</code>\nМодуль не загружен.</blockquote>", parse_mode='html')
            if hasattr(client, 'loaded_modules') and module_name in client.loaded_modules: unload_module(client, module_name)
            if load_module(client, module_name, folder, kernel=getattr(client, 'kernel', None)):
                await message.edit(_format_meta_block(client, module_name), parse_mode='html')
            else:
                await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Не удалось загрузить модуль (ошибка в register)</b></blockquote>", parse_mode='html')
        except Exception as e:
            await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка загрузки:</b> <code>{str(e)}</code></blockquote>", parse_mode='html')
        return

    module_name = input_str.lower()
    if is_protected(module_name): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Access Denied</b></blockquote>", parse_mode='html')
    repos = load_repos()
    if not repos: return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Нет репозиториев. Добавьте через .addrepo или используйте прямую ссылку</b></blockquote>", parse_mode='html')
    await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Поиск модуля {module_name} в репозиториях...</b></blockquote>", parse_mode='html')
    found_repo = None; download_url = None
    for repo_url in repos:
        repo_url = repo_url.rstrip('/')
        test_url = f"{repo_url}/{module_name}.py"
        try:
            head_resp = requests.head(test_url, timeout=5, allow_redirects=True)
            if head_resp.status_code == 200: found_repo = repo_url; download_url = test_url; break
        except: pass
        try:
            get_resp = requests.get(test_url, timeout=8, stream=True)
            if get_resp.status_code == 200: found_repo = repo_url; download_url = test_url; get_resp.close(); break
        except: continue
    if not found_repo:
        repo_list = "\n".join([f" • <code>{r}</code>" for r in repos])
        return await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Модуль '{module_name}' не найден.</b>\n\nПроверенные репозитории:\n{repo_list}\n\nПопробуйте прямую ссылку: .dlm https://.../{module_name}.py</blockquote>", parse_mode='html')
    folder = _personal_folder(client); path = f"{folder}/{module_name}.py"
    try:
        await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Загрузка {module_name} из {found_repo}...</b></blockquote>", parse_mode='html')
        r = requests.get(download_url, timeout=15); r.raise_for_status()
        with open(path, "wb") as f: f.write(r.content)
        requires = _get_module_requires(path)
        if requires:
            await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Проверка зависимостей...</b></blockquote>", parse_mode='html')
            success, missing = _install_dependencies(requires, module_name)
            if not success:
                os.remove(path)
                return await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Не удалось установить зависимости:</b> <code>{', '.join(missing)}</code>\nМодуль не загружен.</blockquote>", parse_mode='html')
        if hasattr(client, 'loaded_modules') and module_name in client.loaded_modules: unload_module(client, module_name)
        if load_module(client, module_name, folder, kernel=getattr(client, 'kernel', None)):
            await message.edit(_format_meta_block(client, module_name), parse_mode='html')
        else:
            await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Не удалось загрузить модуль (проблема в коде модуля)</b></blockquote>", parse_mode='html')
    except Exception as e:
        await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка при скачивании:</b> <code>{str(e)}</code></blockquote>", parse_mode='html')

async def lm_cmd(client, message, args):
    reply_msg = await message.get_reply_message()
    if not reply_msg or not reply_msg.file:
        out = "<blockquote><tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Loaded Modules:</b>\n" + "\n".join([f" • <code>{m}</code>" for m in sorted(getattr(client, 'loaded_modules', set()))]) + "</blockquote>"
        return await message.edit(out, parse_mode='html')
    if not reply_msg.file or not reply_msg.file.name or not reply_msg.file.name.lower().endswith(".py"):
        return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Только .py файлы</b></blockquote>", parse_mode='html')
    name = (args[0] if args else reply_msg.file.name[:-3]).lower()
    if is_protected(name): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Access Denied</b></blockquote>", parse_mode='html')
    folder = _personal_folder(client); path = f"{folder}/{name}.py"
    await message.edit(f"<blockquote><tg-emoji emoji-id=5899757765743615694>⬇️</tg-emoji> <b>Saving {name}...</b></blockquote>", parse_mode='html')
    try:
        await client.download_media(reply_msg, file=path)
        requires = _get_module_requires(path)
        if requires:
            await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Проверка зависимостей...</b></blockquote>", parse_mode='html')
            success, missing = _install_dependencies(requires, name)
            if not success:
                os.remove(path)
                return await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Не удалось установить зависимости:</b> <code>{', '.join(missing)}</code>\nМодуль не загружен.</blockquote>", parse_mode='html')
        if hasattr(client, 'loaded_modules') and name in client.loaded_modules: unload_module(client, name)
        if load_module(client, name, folder, kernel=getattr(client, 'kernel', None)):
            await message.edit(_format_meta_block(client, name), parse_mode='html')
        else:
            await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Не удалось загрузить модуль</b></blockquote>", parse_mode='html')
    except Exception as e:
        await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка:</b> <code>{str(e)}</code></blockquote>", parse_mode='html')

async def ulm_cmd(client, message, args):
    if not args:
        return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n<code>.ulm [name]</code></blockquote>", parse_mode='html')
    name = args[0].lower()
    if is_protected(name): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Access Denied</b></blockquote>", parse_mode='html')
    folder = _personal_folder(client); path = f"{folder}/{name}.py"
    if os.path.exists(path):
        unload_module(client, name)
        os.remove(path)
        await message.edit(f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Module {name} deleted</b></blockquote>", parse_mode='html')
    else:
        await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Not found</b></blockquote>", parse_mode='html')

async def ml_cmd(client, message, args):
    if not args:
        return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n<code>.ml [name]</code></blockquote>", parse_mode='html')
    name = args[0]
    file_name = f"{name}.py" if not name.endswith('.py') else name
    mod_name = name.replace('.py', '')
    folder = _personal_folder(client)
    path = os.path.join(folder, file_name)
    if not os.path.exists(path): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Not found</b></blockquote>", parse_mode='html')
    pref = _get_prefix(client)
    await message.delete()
    await client.send_file(
        message.chat_id, path,
        caption=(
            f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Module:</b> <code>{file_name}</code></blockquote>\n"
            f"<blockquote><b>Установка:</b> <code>{pref}lm {mod_name}</code></blockquote>"
        ),
        parse_mode='html'
    )

async def reload_cmd(client, message, args):
    if not args: return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n<code>.reload [module_name]</code></blockquote>", parse_mode='html')
    name = args[0].lower()
    if is_protected(name): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Access Denied</b> (Системный модуль)</blockquote>", parse_mode='html')
    folder = _personal_folder(client)
    path = os.path.join(folder, f"{name}.py")
    if not os.path.exists(path): return await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Файл модуля не найден</b></blockquote>", parse_mode='html')
    unload_module(client, name)
    if name in sys.modules: del sys.modules[name]
    kernel = getattr(client, 'kernel', None)
    await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Перезагрузка {name}...</b></blockquote>", parse_mode='html')
    if load_module(client, name, folder, kernel=kernel):
        meta_block = _format_meta_block(client, name)
        await message.edit(f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Модуль перезагружен:</b> <code>{name}</code></blockquote>\n{meta_block}", parse_mode='html')
    else:
        await message.edit("<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка при перезагрузке (проверь логи)</b></blockquote>", parse_mode='html')

async def pip_cmd(client, message, args):
    if not args:
        return await message.edit(
            "<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b>\n\n"
            "<code>.pip install &lt;package&gt;</code> - установить пакет\n"
            "<code>.pip uninstall &lt;package&gt;</code> - удалить пакет\n"
            "<code>.pip list</code> - список установленных пакетов\n"
            "<code>.pip show &lt;package&gt;</code> - информация о пакете</blockquote>",
            parse_mode='html'
        )
    action = args[0].lower()
    if action == "install":
        if len(args) < 2: return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b> <code>.pip install &lt;package&gt;</code></blockquote>", parse_mode='html')
        packages = args[1:]
        await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Установка:</b> <code>{', '.join(packages)}</code></blockquote>", parse_mode='html')
        success, missing = _install_dependencies(packages, "manual")
        if success: await message.edit(f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Пакеты установлены:</b> <code>{', '.join(packages)}</code></blockquote>", parse_mode='html')
        else: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка установки:</b> <code>{', '.join(missing)}</code></blockquote>", parse_mode='html')
    elif action == "uninstall":
        if len(args) < 2: return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b> <code>.pip uninstall &lt;package&gt;</code></blockquote>", parse_mode='html')
        packages = args[1:]
        await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Удаление:</b> <code>{', '.join(packages)}</code></blockquote>", parse_mode='html')
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "--quiet"] + packages, capture_output=True, text=True, timeout=60)
            if result.returncode == 0: await message.edit(f"<blockquote><tg-emoji emoji-id=5776375003280838798>✅</tg-emoji> <b>Пакеты удалены:</b> <code>{', '.join(packages)}</code></blockquote>", parse_mode='html')
            else: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка:</b> <code>{result.stderr.strip() or result.stdout.strip()}</code></blockquote>", parse_mode='html')
        except Exception as e: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка:</b> <code>{type(e).__name__}: {e}</code></blockquote>", parse_mode='html')
    elif action == "list":
        await message.edit("<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Загрузка списка пакетов...</b></blockquote>", parse_mode='html')
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=freeze"], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                packages_list = result.stdout.strip().split('\n')
                packages_list.sort(key=str.lower)
                if len(packages_list) > 50:
                    temp_file = "pip_packages.txt"
                    with open(temp_file, "w") as f: f.write("\n".join(packages_list))
                    await message.delete()
                    await client.send_file(message.chat_id, temp_file, caption=f"<blockquote><tg-emoji emoji-id=5897962422169243693>👻</tg-emoji> <b>Установленные пакеты</b>\n<code>{len(packages_list)} пакетов</code></blockquote>", parse_mode='html')
                    os.remove(temp_file)
                else:
                    text = "<blockquote><b>Установленные пакеты:</b>\n" + "\n".join([f"<code>{p}</code>" for p in packages_list]) + "</blockquote>"
                    await message.edit(text, parse_mode='html')
            else: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка:</b> <code>{result.stderr.strip()}</code></blockquote>", parse_mode='html')
        except Exception as e: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка:</b> <code>{type(e).__name__}: {e}</code></blockquote>", parse_mode='html')
    elif action == "show":
        if len(args) < 2: return await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Usage:</b> <code>.pip show &lt;package&gt;</code></blockquote>", parse_mode='html')
        package = args[1]
        await message.edit(f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>Информация о {package}...</b></blockquote>", parse_mode='html')
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", package], capture_output=True, text=True, timeout=30)
            if result.returncode == 0: await message.edit(f"<blockquote expandable><b>Информация о {package}:</b>\n<code>{result.stdout.strip()}</code></blockquote>", parse_mode='html')
            else: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Пакет не найден:</b> <code>{package}</code></blockquote>", parse_mode='html')
        except Exception as e: await message.edit(f"<blockquote><tg-emoji emoji-id=5778527486270770928>❌</tg-emoji> <b>Ошибка:</b> <code>{type(e).__name__}: {e}</code></blockquote>", parse_mode='html')
    else:
        await message.edit("<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>Неизвестное действие</b>\nИспользуйте: <code>install</code>, <code>uninstall</code>, <code>list</code>, <code>show</code></blockquote>", parse_mode='html')

def load_module(app, name, folder, kernel=None):
    path = os.path.abspath(os.path.join(folder, f"{name}.py"))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None: return False
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        reg = getattr(mod, "register", None)
        if reg is None:
            if not hasattr(app, 'loaded_modules'): app.loaded_modules = set()
            app.loaded_modules.add(name)
            return True
        sig = inspect.signature(reg)
        count = len(sig.parameters)
        if count >= 4 and kernel is not None: reg(app, app.commands, name, kernel)
        elif count == 3: reg(app, app.commands, name)
        elif count == 2: reg(app, app.commands)
        elif count == 1: reg(app)
        elif count == 0: reg()
        else: return False
        if not hasattr(app, 'loaded_modules'): app.loaded_modules = set()
        app.loaded_modules.add(name)
        return True
    except Exception as e:
        print(f"Ошибка загрузки модуля {name}: {type(e).__name__}: {str(e)}")
        return False

def unload_module(app, name):
    if not hasattr(app, 'loaded_modules'): app.loaded_modules = set()
    if name in app.loaded_modules: app.loaded_modules.remove(name)
    if hasattr(app, 'commands'):
        to_remove = [k for k, v in app.commands.items() if v.get("module") == name]
        for k in to_remove: app.commands.pop(k, None)

def register_loader_commands(app):
    app.commands.update({
        "dlm":     {"func": dlm_cmd,     "module": "loader"},
        "lm":      {"func": lm_cmd,      "module": "loader"},
        "ulm":     {"func": ulm_cmd,     "module": "loader"},
        "ml":      {"func": ml_cmd,      "module": "loader"},
        "addrepo": {"func": addrepo_cmd, "module": "loader"},
        "pip":     {"func": pip_cmd,     "module": "loader"},
        "reload":  {"func": reload_cmd,  "module": "loader"}
    })
    if not hasattr(app, 'loaded_modules'): app.loaded_modules = set()
    app.loaded_modules.add("loader")

def load_all(app, kernel=None):
    personal = _personal_folder(app)
    for d in ["modules", personal]:
        if not os.path.exists(d): os.makedirs(d)
        for f in sorted(os.listdir(d)):
            if f.endswith(".py") and not f.startswith("_"):
                load_module(app, f[:-3], d, kernel)
    register_loader_commands(app)