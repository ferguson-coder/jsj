import asyncio
import os
import subprocess
import sys
import time

from telethon.tl.custom import Message  # noqa: F401  (re-exported)

from forelka.i18n import for_client


async def update_cmd(client, message, args):
    tr = for_client(client)
    try:
        await message.edit(
            f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>{tr('cmd.update.checking')}</b></blockquote>",
            parse_mode="html",
        )
        res = subprocess.check_output(["git", "pull"]).decode()
        if "Already up to date" in res:
            return await message.edit(
                f"<blockquote><tg-emoji emoji-id=5775887550262546277>❗️</tg-emoji> <b>{tr('cmd.update.up_to_date')}</b></blockquote>",
                parse_mode="html",
            )

        os.environ["RESTART_INFO"] = f"{time.time()}|{message.chat_id}|{message.id}"
        os.execv(sys.executable, [sys.executable, "-m", "forelka"])
    except Exception as e:
        await message.edit(
            f"<blockquote>{tr('cmd.update.error', error=e)}</blockquote>",
            parse_mode="html",
        )


async def restart_cmd(client, message, args):
    tr = for_client(client)
    os.environ["RESTART_INFO"] = f"{time.time()}|{message.chat_id}|{message.id}"
    await message.edit(
        f"<blockquote><tg-emoji emoji-id=5891211339170326418>⌛️</tg-emoji> <b>{tr('cmd.restart.starting')}</b></blockquote>",
        parse_mode="html",
    )
    os.execv(sys.executable, [sys.executable, "-m", "forelka"])


def register(app, commands, module_name):
    commands["update"] = {"func": update_cmd, "module": module_name}
    commands["restart"] = {"func": restart_cmd, "module": module_name}

    restart_data = os.environ.get("RESTART_INFO")
    if restart_data:
        try:
            start_time, chat_id, msg_id = restart_data.split("|")
            diff = time.time() - float(start_time)

            async def notify():
                await asyncio.sleep(1.5)
                tr = for_client(app)
                await app.edit_message(
                    int(chat_id),
                    int(msg_id),
                    tr("cmd.restart.done", seconds=diff),
                    parse_mode="html",
                )

            asyncio.get_event_loop().create_task(notify())
            os.environ.pop("RESTART_INFO", None)
        except Exception:
            pass
