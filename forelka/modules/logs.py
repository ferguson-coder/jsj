import os

from forelka.config import AccountConfig


async def log_cmd(client, message, args):
    user_id = message.sender_id
    cfg = AccountConfig.load(client._self_id)

    if not cfg.is_owner(user_id):
        await message.edit("❌ Доступ запрещён.")
        return

    if not os.path.exists("forelka.log"):
        await message.edit("❌ Файл лога не найден.")
        return

    # --- Бот должен быть подключён, чтобы отправить в management-group ---
    if (
        hasattr(client, 'kernel')
        and client.kernel.inline_bot
        and client.kernel.inline_bot.bot_client
        and client.kernel.inline_bot.bot_client.is_connected()
    ):
        bot_client = client.kernel.inline_bot.bot_client
        group_id = cfg.management_group_id
        logs_topic_id = cfg.management_topics.get("Логи")

        if group_id and logs_topic_id:
            try:
                await bot_client.send_file(
                    entity=group_id,
                    file="forelka.log",
                    message_thread_id=logs_topic_id,
                )
                await message.edit("✅ Логи отправлены инлайн-ботом в топик 'Логи'.")
                return
            except Exception:
                pass

    # Если бот не готов, отправляем от юзербота
    await client.send_file(message.chat_id, "forelka.log", caption="📋 Логи юзербота")
    await message.delete()


def register(app, commands, module_name):
    commands["log"] = {"func": log_cmd, "module": module_name}
