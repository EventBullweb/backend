import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from app.core.config import settings

logger = logging.getLogger(__name__)
BOT_MESSAGES_IMAGES_DIR = Path(__file__).resolve().parents[1] / "static" / "bot_messages"
TICKET_ACTIVATED_IMAGE_PATH = BOT_MESSAGES_IMAGES_DIR / "ticket_activated.png"


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
        message_text = build_ticket_activated_message(lottery_code)
        if TICKET_ACTIVATED_IMAGE_PATH.exists():
            await bot.send_photo(
                chat_id=telegram_id,
                photo=FSInputFile(str(TICKET_ACTIVATED_IMAGE_PATH)),
                caption=message_text,
            )
        else:
            logger.warning(
                "Activation image not found at %s, sending text-only notification.",
                TICKET_ACTIVATED_IMAGE_PATH,
            )
            await bot.send_message(
                chat_id=telegram_id,
                text=message_text,
            )
    except Exception as exc:
        logger.exception(
            "Failed to send activation notification to telegram_id=%s: %s",
            telegram_id,
            exc,
        )
    finally:
        await bot.session.close()
