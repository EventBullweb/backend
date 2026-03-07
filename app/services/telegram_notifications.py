import logging

from aiogram import Bot

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_ticket_activated_message(lottery_code: str) -> str:
    return (
        "Поздравляем!\n\n"
        "Если вы видите это сообщение, значит ваш билет только что был активирован на входе, "
        "и вы успешно прошли на мероприятие Show & Circus.\n\n"
        "Теперь за вами закреплен уникальный номер участника, который автоматически участвует "
        "в розыгрыше призов во время вечера.\n\n"
        f"Ваш лотерейный номер: {lottery_code}\n\n"
        "Добро пожаловать на мероприятие!\n"
        "Желаем вам приятного вечера, ярких впечатлений и отличного отдыха."
    )


async def notify_ticket_activated(telegram_id: int, lottery_code: str) -> None:
    if not settings.bot_token:
        logger.warning("BOT_TOKEN is empty, skip activation notification.")
        return

    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=build_ticket_activated_message(lottery_code),
        )
    except Exception as exc:
        logger.exception(
            "Failed to send activation notification to telegram_id=%s: %s",
            telegram_id,
            exc,
        )
    finally:
        await bot.session.close()
