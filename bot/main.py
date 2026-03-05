import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Ticket, Visitor, VisitorAnswer
from bot.registration_steps import REGISTRATION_STEPS
from bot.tickets import generate_qr_png, generate_ticket_code

router = Router()


class RegistrationState(StatesGroup):
    waiting_for_step = State()
    waiting_for_confirmation = State()


CALLBACK_START_REGISTRATION = "registration:start"
CALLBACK_CONFIRM_REGISTRATION = "registration:confirm"
CALLBACK_RESTART_REGISTRATION = "registration:restart"


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
                    text="Начать регистрацию",
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
    await message.answer(step.prompt)
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
                "Вы уже зарегистрированы.\n"
                f"Ваш билет №{visitor.ticket.ticket_code}."
            )
            return

    await state.clear()
    await state.update_data(step_index=0, answers={})
    await ask_next_step(message, state)


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
                "Вы уже зарегистрированы.\n"
                f"Ваш билет №{visitor.ticket.ticket_code}."
            )
            return

    await state.clear()
    await message.answer(
        "Нажмите кнопку ниже, чтобы начать регистрацию.",
        reply_markup=build_start_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_START_REGISTRATION)
async def start_registration_from_button(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    await state.clear()
    await state.update_data(step_index=0, answers={})
    await callback.message.answer("Начинаем регистрацию.")
    await ask_next_step(callback.message, state)
    await callback.answer()


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
            visitor.ticket = Ticket(ticket_code=generate_ticket_code())

        session.commit()
        session.refresh(visitor)
        session.refresh(visitor.ticket)

        ticket_code = visitor.ticket.ticket_code

    qr_bytes = generate_qr_png(ticket_code)
    await callback.message.answer(
        "Благодарим за регистрацию, "
        f"ваш билет №{ticket_code} зарегистрирован. "
        "Ждём вас 01-01-2026 в 14-00!"
    )
    await callback.message.answer_photo(
        BufferedInputFile(qr_bytes, filename=f"{ticket_code}.png"),
        caption=f"QR-код билета: {ticket_code}",
    )
    await state.clear()
    await callback.answer()


@router.message(RegistrationState.waiting_for_confirmation, F.text)
async def handle_confirmation_fallback(message: Message) -> None:
    await message.answer(
        "Используйте кнопки в сообщении: 'Подтвердить регистрацию' или 'Заполнить заново'."
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Напишите /start или /register, чтобы начать регистрацию.")


async def run_bot() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Fill it in .env file.")

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
