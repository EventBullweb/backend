import asyncio
from pathlib import Path
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Ticket, Visitor, VisitorAnswer
from app.services.channel_broadcast import (
    broadcast_source_message,
    get_registered_recipient_ids,
    get_source_recipient_ids,
    has_source_deliveries,
    remove_source_deliveries,
)
from app.services.ticket_numbers import generate_ticket_number
from bot.registration_steps import REGISTRATION_STEPS

router = Router()


class RegistrationState(StatesGroup):
    waiting_for_step = State()
    waiting_for_confirmation = State()


CALLBACK_SHOW_REGISTRATION_INFO = "registration:show-info"
CALLBACK_START_REGISTRATION = "registration:start"
CALLBACK_CONFIRM_REGISTRATION = "registration:confirm"
CALLBACK_RESTART_REGISTRATION = "registration:restart"
CALLBACK_SHOW_MY_TICKET = "menu:my-ticket"
CALLBACK_SHOW_EVENT_PROGRAM = "menu:event-program"
CALLBACK_CONTACT_ORGANIZER = "menu:contact-organizer"
CALLBACK_ANNUL_TICKET = "ticket:annul"
CALLBACK_BACK_TO_MAIN_MENU = "menu:back"
DELETE_BROADCAST_COMMAND = "/sync_delete"
DELETE_BROADCAST_MARKER = "#удалить"

INTRO_TEXT = (
    "Давай добавим деталей!\n\n"
    "Закрытое мероприятие от ивент-агентства Show & Circus.\n"
    "Мы собираем в Москве 200 гостей из индустрии событий.\n\n"
    "Локация: Papa Moscow Club\n"
    "Дата и время: 16 марта, 18:00-23:00\n\n"
    "Вход на мероприятие по спискам. Количество мест ограничено."
)

REGISTRATION_INFO_TEXT = (
    "Чтобы подтвердить участие в мероприятии и получить персональный билет, "
    "необходимо пройти короткую регистрацию.\n\n"
    "Бот задаст несколько простых вопросов. Пожалуйста, укажите:\n"
    "- имя\n"
    "- номер телефона\n\n"
    "После регистрации вы получите электронный билет с уникальным QR-кодом, "
    "который необходимо показать на входе."
)

REGISTRATION_SUCCESS_TEXT = (
    "Поздравляем, вы успешно прошли регистрацию!\n\n"
    "За вами забронировано место на закрытом мероприятии Show & Circus.\n"
    "Ваш персональный билет уже сформирован.\n"
    "Получить его можно в меню ниже - просто откройте раздел Мой билет."
)

EVENT_PROGRAM_TEXT = (
    "Примерная программа мероприятия\n\n"
    "18:00 - Сбор гостей и welcome\n"
    "18:30 - Открытие вечера\n"
    "19:00 - Тренды 2026 в индустрии мероприятий\n"
    "20:00 - Шоу-программа\n"
    "21:00 - Розыгрыш призов от партнеров\n"
    "21:30 - Нетворкинг и свободное общение\n"
    "22:30 - Финальная шоу-программа\n"
    "23:00 - Завершение мероприятия"
)


async def fetch_telegram_avatar_url(bot: Bot, telegram_id: int) -> str | None:
    try:
        photos = await bot.get_user_profile_photos(user_id=telegram_id, limit=1)
        if not photos.photos:
            return None

        largest_photo = photos.photos[0][-1]
        file = await bot.get_file(largest_photo.file_id)
        if not file.file_path:
            return None

        avatars_dir = Path(__file__).resolve().parents[1] / "app" / "static" / "avatars"
        avatars_dir.mkdir(parents=True, exist_ok=True)

        file_extension = Path(file.file_path).suffix or ".jpg"
        avatar_filename = f"{telegram_id}{file_extension}"
        avatar_path = avatars_dir / avatar_filename
        await bot.download_file(file.file_path, destination=avatar_path)
        return f"/static/avatars/{avatar_filename}"
    except Exception:
        return None


def build_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ПРОЙТИ РЕГИСТРАЦИЮ",
                    callback_data=CALLBACK_SHOW_REGISTRATION_INFO,
                )
            ]
        ]
    )


def build_registration_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ПОЛУЧИТЬ БИЛЕТ",
                    callback_data=CALLBACK_START_REGISTRATION,
                )
            ]
        ]
    )


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить регистрацию",
                    callback_data=CALLBACK_CONFIRM_REGISTRATION,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Заполнить заново",
                    callback_data=CALLBACK_RESTART_REGISTRATION,
                )
            ],
        ]
    )


def build_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить контакт", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="МОЙ БИЛЕТ / ФОРМАТ QR КОД",
                    callback_data=CALLBACK_SHOW_MY_TICKET,
                )
            ],
            [
                InlineKeyboardButton(
                    text="ПРОГРАММА МЕРОПРИЯТИЯ",
                    callback_data=CALLBACK_SHOW_EVENT_PROGRAM,
                )
            ],
            [
                InlineKeyboardButton(
                    text="СВЯЗАТЬСЯ С ОРГАНИЗАТОРОМ",
                    callback_data=CALLBACK_CONTACT_ORGANIZER,
                )
            ],
        ]
    )


def build_ticket_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="АННУЛИРОВАТЬ БИЛЕТ",
                    callback_data=CALLBACK_ANNUL_TICKET,
                )
            ],
            [
                InlineKeyboardButton(
                    text="ВЕРНУТЬСЯ В ГЛАВНОЕ МЕНЮ",
                    callback_data=CALLBACK_BACK_TO_MAIN_MENU,
                )
            ],
        ]
    )


def build_back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ВЕРНУТЬСЯ В ГЛАВНОЕ МЕНЮ",
                    callback_data=CALLBACK_BACK_TO_MAIN_MENU,
                )
            ]
        ]
    )


def normalize_phone(raw_phone: str) -> str:
    normalized = re.sub(r"[^\d+]", "", raw_phone.strip())
    if normalized.count("+") > 1 or ("+" in normalized and not normalized.startswith("+")):
        return ""
    return normalized


def generate_unique_ticket_number(session) -> str:
    for _ in range(100):
        candidate = generate_ticket_number()
        existing = session.scalar(
            select(Ticket.id).where(Ticket.ticket_number == candidate)
        )
        if existing is None:
            return candidate
    raise RuntimeError("Failed to generate unique ticket number.")


async def edit_navigation_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
    await callback.answer()


async def ask_next_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    step_index = data.get("step_index", 0)
    if step_index >= len(REGISTRATION_STEPS):
        answers = data.get("answers", {})
        summary_lines = [
            f"{step.label}: {answers.get(step.key, '')}" for step in REGISTRATION_STEPS
        ]
        await state.set_state(RegistrationState.waiting_for_confirmation)
        await message.answer(
            "Проверьте введенные данные:\n\n"
            + "\n".join(summary_lines)
            + "\n\nПодтвердить регистрацию?",
            reply_markup=build_confirm_keyboard(),
        )
        return

    step = REGISTRATION_STEPS[step_index]
    if step.key == "phone":
        await message.answer(step.prompt, reply_markup=build_phone_keyboard())
    else:
        await message.answer(step.prompt, reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegistrationState.waiting_for_step)


@router.message(Command("register"))
async def start_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    with SessionLocal() as session:
        visitor = session.scalar(
            select(Visitor).where(Visitor.telegram_id == telegram_id)
        )
        if visitor and visitor.is_registration_completed and visitor.ticket:
            await message.answer(
                f"Вы уже зарегистрированы. Ваш билет №{visitor.ticket.ticket_number}.",
                reply_markup=build_main_menu_keyboard(),
            )
            return

    await state.clear()
    await message.answer(
        REGISTRATION_INFO_TEXT,
        reply_markup=build_registration_entry_keyboard(),
    )


@router.message(CommandStart())
async def start_command_handler(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    with SessionLocal() as session:
        visitor = session.scalar(
            select(Visitor).where(Visitor.telegram_id == telegram_id)
        )
        if visitor and visitor.is_registration_completed and visitor.ticket:
            await message.answer(
                f"Вы уже зарегистрированы. Ваш билет №{visitor.ticket.ticket_number}.",
                reply_markup=build_main_menu_keyboard(),
            )
            return

    await state.clear()
    await message.answer(
        INTRO_TEXT,
        reply_markup=build_start_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_SHOW_REGISTRATION_INFO)
async def show_registration_info(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await edit_navigation_message(
        callback,
        REGISTRATION_INFO_TEXT,
        reply_markup=build_registration_entry_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_START_REGISTRATION)
async def start_registration_from_button(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    await state.update_data(step_index=0, answers={})
    await callback.message.answer("Начинаем регистрацию.", reply_markup=ReplyKeyboardRemove())
    await ask_next_step(callback.message, state)
    await callback.answer()


@router.message(RegistrationState.waiting_for_step, F.contact)
async def process_phone_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact is None:
        await message.answer("Не удалось прочитать контакт. Попробуйте еще раз.")
        return
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя. Попробуйте снова.")
        return
    if contact.user_id != message.from_user.id:
        await message.answer(
            "Нужно отправить контакт именно вашего Telegram-аккаунта. "
            "Нажмите кнопку 'Отправить контакт'."
        )
        return

    data = await state.get_data()
    step_index = data.get("step_index", 0)
    if step_index >= len(REGISTRATION_STEPS):
        await ask_next_step(message, state)
        return

    step = REGISTRATION_STEPS[step_index]
    if step.key != "phone":
        await message.answer("Сейчас ожидается другой шаг. Введите ответ в тексте.")
        return

    phone = normalize_phone(contact.phone_number)
    if len(phone.replace("+", "")) < 10:
        await message.answer("Номер выглядит слишком коротким. Отправьте корректный номер.")
        return

    answers = dict(data.get("answers", {}))
    answers[step.key] = phone
    await state.update_data(answers=answers, step_index=step_index + 1)
    await ask_next_step(message, state)


@router.message(RegistrationState.waiting_for_step, F.text)
async def process_registration_step(message: Message, state: FSMContext) -> None:
    user_text = (message.text or "").strip()
    if not user_text:
        await message.answer("Пустой ответ не подходит. Введите значение еще раз.")
        return

    data = await state.get_data()
    step_index = data.get("step_index", 0)
    if step_index >= len(REGISTRATION_STEPS):
        await ask_next_step(message, state)
        return

    step = REGISTRATION_STEPS[step_index]
    answers = dict(data.get("answers", {}))
    if step.key == "phone":
        await message.answer(
            "Номер телефона принимается только через кнопку 'Отправить контакт'.",
            reply_markup=build_phone_keyboard(),
        )
        return
    else:
        answers[step.key] = user_text

    await state.update_data(
        answers=answers,
        step_index=step_index + 1,
    )
    await ask_next_step(message, state)


@router.callback_query(
    RegistrationState.waiting_for_confirmation,
    F.data == CALLBACK_RESTART_REGISTRATION,
)
async def restart_registration(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return

    await state.update_data(step_index=0, answers={})
    await ask_next_step(callback.message, state)
    await callback.answer()


@router.callback_query(
    RegistrationState.waiting_for_confirmation,
    F.data == CALLBACK_CONFIRM_REGISTRATION,
)
async def confirm_registration(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    data = await state.get_data()
    answers_data: dict[str, str] = data.get("answers", {})
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    full_name = answers_data.get("full_name")
    telegram_avatar_url = await fetch_telegram_avatar_url(callback.bot, telegram_id)

    with SessionLocal() as session:
        visitor = session.scalar(
            select(Visitor).where(Visitor.telegram_id == telegram_id)
        )
        if visitor is None:
            visitor = Visitor(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                telegram_avatar_url=telegram_avatar_url,
                is_registration_completed=True,
            )
            session.add(visitor)
            session.flush()
        else:
            visitor.username = username
            visitor.full_name = full_name
            if telegram_avatar_url is not None:
                visitor.telegram_avatar_url = telegram_avatar_url
            visitor.is_registration_completed = True
            visitor.answers.clear()

        for step in REGISTRATION_STEPS:
            value = answers_data.get(step.key, "")
            visitor.answers.append(
                VisitorAnswer(
                    step_key=step.key,
                    step_label=step.label,
                    value=value,
                )
            )

        if visitor.ticket is None:
            visitor.ticket = Ticket(
                ticket_number=generate_unique_ticket_number(session),
            )
        elif (
            len(visitor.ticket.ticket_number) < 13
            and not visitor.ticket.is_activated
        ):
            visitor.ticket.ticket_number = generate_unique_ticket_number(session)
            visitor.ticket.lottery_code = None

        session.commit()
        session.refresh(visitor)
        session.refresh(visitor.ticket)

        ticket_number = visitor.ticket.ticket_number

    await edit_navigation_message(
        callback,
        f"{REGISTRATION_SUCCESS_TEXT}\n\nВаш билет №{ticket_number}.",
        reply_markup=build_main_menu_keyboard(),
    )
    await state.clear()


@router.message(RegistrationState.waiting_for_confirmation, F.text)
async def handle_confirmation_fallback(message: Message) -> None:
    await message.answer(
        "Используйте кнопки: 'Подтвердить регистрацию' или 'Заполнить заново'."
    )


@router.callback_query(F.data == CALLBACK_SHOW_MY_TICKET)
async def show_my_ticket(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    with SessionLocal() as session:
        visitor = session.scalar(
            select(Visitor).where(Visitor.telegram_id == callback.from_user.id)
        )
        if visitor is None or visitor.ticket is None:
            await edit_navigation_message(
                callback,
                "Билет не найден. Пройдите регистрацию через /start.",
                reply_markup=build_back_to_main_menu_keyboard(),
            )
            return

        ticket_number = visitor.ticket.ticket_number

    await edit_navigation_message(
        callback,
        "Ваш билет на закрытое мероприятие Show & Circus.\n\n"
        f"Номер билета: {ticket_number}\n"
        "Локация: Papa Moscow Club\n"
        "Дата и время: 16 марта, 18:00-23:00\n\n"
        "Концепция вечера: Драгоценные камни.",
        reply_markup=build_ticket_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_ANNUL_TICKET)
async def annul_ticket(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    with SessionLocal() as session:
        visitor = session.scalar(
            select(Visitor).where(Visitor.telegram_id == callback.from_user.id)
        )
        if visitor is None or visitor.ticket is None:
            await edit_navigation_message(
                callback,
                "Активного билета не найдено.",
                reply_markup=build_back_to_main_menu_keyboard(),
            )
            return

        if visitor.ticket.is_activated:
            await edit_navigation_message(
                callback,
                "Этот билет уже активирован на входе, аннулирование недоступно.",
                reply_markup=build_back_to_main_menu_keyboard(),
            )
            return

        session.delete(visitor.ticket)
        visitor.is_registration_completed = False
        session.commit()

    await edit_navigation_message(
        callback,
        "Ваш билет аннулирован.\n\n"
        "Нам очень жаль, что вы не сможете присутствовать на мероприятии Show & Circus.\n"
        "Будем рады видеть вас на следующих событиях.",
        reply_markup=build_back_to_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_BACK_TO_MAIN_MENU)
async def back_to_main_menu(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        "Главное меню:",
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_SHOW_EVENT_PROGRAM)
async def show_event_program(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        EVENT_PROGRAM_TEXT,
        reply_markup=build_back_to_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_CONTACT_ORGANIZER)
async def contact_organizer(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        "Связь с организатором: @showandcircus_support\n"
        "Если у вас нет Telegram-юзернейма для связи, ответьте на это сообщение.",
        reply_markup=build_back_to_main_menu_keyboard(),
    )


@router.channel_post()
async def distribute_channel_post(message: Message) -> None:
    if settings.content_channel_id == 0:
        return
    if message.chat.id != settings.content_channel_id:
        return
    if message.text and message.text.startswith(DELETE_BROADCAST_COMMAND):
        await handle_delete_broadcast_command(message)
        return
    source_chat_id = message.chat.id
    source_message_id = message.message_id

    with SessionLocal() as session:
        if has_source_deliveries(session, source_chat_id, source_message_id):
            return

        recipient_ids = get_registered_recipient_ids(session)
        await broadcast_source_message(
            bot=message.bot,
            session=session,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            recipient_ids=recipient_ids,
        )


@router.edited_channel_post()
async def redistribute_edited_channel_post(message: Message) -> None:
    if settings.content_channel_id == 0:
        return
    if message.chat.id != settings.content_channel_id:
        return
    source_chat_id = message.chat.id
    source_message_id = message.message_id

    with SessionLocal() as session:
        if is_delete_broadcast_marker(message):
            await remove_source_deliveries(
                bot=message.bot,
                session=session,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
            )
            try:
                await message.bot.delete_message(
                    chat_id=source_chat_id,
                    message_id=source_message_id,
                )
            except TelegramBadRequest:
                pass
            return

        recipient_ids = get_source_recipient_ids(
            session=session,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )
        if not recipient_ids:
            return

        await remove_source_deliveries(
            bot=message.bot,
            session=session,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )
        await broadcast_source_message(
            bot=message.bot,
            session=session,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            recipient_ids=recipient_ids,
        )


async def handle_delete_broadcast_command(message: Message) -> None:
    payload = (message.text or "").strip()
    parts = payload.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return

    source_message_id = int(parts[1])
    with SessionLocal() as session:
        await remove_source_deliveries(
            bot=message.bot,
            session=session,
            source_chat_id=message.chat.id,
            source_message_id=source_message_id,
        )


def is_delete_broadcast_marker(message: Message) -> bool:
    text = (message.text or message.caption or "").strip().casefold()
    return text == DELETE_BROADCAST_MARKER


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Напишите /start, чтобы открыть главное меню и регистрацию."
    )


async def run_bot() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Fill it in .env file.")

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
