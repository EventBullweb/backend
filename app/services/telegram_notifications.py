import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings

logger = logging.getLogger(__name__)
BOT_MESSAGES_IMAGES_DIR = Path(__file__).resolve().parents[1] / "static" / "bot_messages"
TICKET_ACTIVATED_IMAGE_PATH = BOT_MESSAGES_IMAGES_DIR / "ticket_activated.png"

# Callback data совпадает с bot/main.py (меню: программа, партнёры, организатор)
NOTIFICATION_QUICK_MENU_CALLBACKS = {
    "program": "menu:event-program",
    "partners": "menu:partners",
    "organizer": "menu:contact-organizer",
}


def _build_notification_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под уведомлением: Программа, Партнёры, Организатор."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Программа 🚀",
                    callback_data=NOTIFICATION_QUICK_MENU_CALLBACKS["program"],
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤝 Партнеры 🤝",
                    callback_data=NOTIFICATION_QUICK_MENU_CALLBACKS["partners"],
                )
            ],
            [
                InlineKeyboardButton(
                    text="☎️ Организатор ☎️",
                    callback_data=NOTIFICATION_QUICK_MENU_CALLBACKS["organizer"],
                )
            ],
        ]
    )


def build_ticket_activated_message(lottery_code: str) -> str:
    return (
        "Добро пожаловать на мероприятие 🎉\n\n"
        "За вами закреплён номер, который участвует в розыгрыше призов\n\n"
        f"№ участника: {lottery_code}\n\n"
        "Желаем вам приятного вечера, ярких впечатлений и отличного отдыха."
    )


async def notify_ticket_activated(telegram_id: int, lottery_code: str) -> None:
    if not settings.bot_token:
        logger.warning("BOT_TOKEN is empty, skip activation notification.")
        return

    bot = Bot(token=settings.bot_token)
    try:
        message_text = build_ticket_activated_message(lottery_code)
        keyboard = _build_notification_keyboard()
        if TICKET_ACTIVATED_IMAGE_PATH.exists():
            await bot.send_photo(
                chat_id=telegram_id,
                photo=FSInputFile(str(TICKET_ACTIVATED_IMAGE_PATH)),
                caption=message_text,
                reply_markup=keyboard,
            )
        else:
            logger.warning(
                "Activation image not found at %s, sending text-only notification.",
                TICKET_ACTIVATED_IMAGE_PATH,
            )
            await bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                reply_markup=keyboard,
            )
    except Exception as exc:
        logger.exception(
            "Failed to send activation notification to telegram_id=%s: %s",
            telegram_id,
            exc,
        )
    finally:
        await bot.session.close()
