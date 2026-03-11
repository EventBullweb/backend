import asyncio
import html
from pathlib import Path
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    User,
)
from sqlalchemy import select
from PIL import Image
import qrcode

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
from app.services.ticket_numbers import (
    generate_ticket_number,
    is_ticket_number_in_current_format,
)
from bot.registration_steps import REGISTRATION_STEPS

router = Router()


class RegistrationState(StatesGroup):
    waiting_for_step = State()


CALLBACK_SHOW_REGISTRATION_INFO = "registration:show-info"
CALLBACK_START_REGISTRATION = "registration:start"
CALLBACK_SHOW_MY_TICKET = "menu:my-ticket"
CALLBACK_SHOW_EVENT_PROGRAM = "menu:event-program"
CALLBACK_SHOW_PARTNERS = "menu:partners"
CALLBACK_CONTACT_ORGANIZER = "menu:contact-organizer"
CALLBACK_ANNUL_TICKET = "ticket:annul"
CALLBACK_BACK_TO_MAIN_MENU = "menu:back"
DELETE_BROADCAST_COMMAND = "/sync_delete"
DELETE_BROADCAST_MARKER = "#удалить"

INTRO_TEXT = (
    "Регистрация на мероприятие👇\n\n"
    "Закрытое мероприятие «Драгоценные камни» от ивент-агентства «Show & Circus» и его Партнеров.\n"
    "Мы пригласили  200+  гостей из ивент-сообщества  и наших уважаемых Клиентов.\n\n"
    "Локация: Papa Moscow Club\n"
    "Адрес: 1-ая Брестская, 2 стр. 3, Moscow, Russia\n"
    "Дата и время: 16 марта, \n18:00–23:00\n\n"
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
    "Регистрация прошла успешно!\n\n"
    "Ваш билет 🎫\n"
    "Номер {ticket_number}\n\n"
    "За вами забронировано место!\n\n"
    'Персональный QR в разделе "мой билет" 👇'
)

TICKET_CONGRATULATIONS_TEXT = (
    "{name}, поздравляем 🥳\n\n"
    "Вы успешно зарегистрированы на закрытый ивент «Драгоценные камни» от «Show&Circus» и партнеров.\n\n"
    "Ждем вас 16 марта в 18:00♥️\n\n"
    "Это ваш билет и вход на мероприятие!\n"
    "просто предъявите QR-код👆"
)

PARTNERS_TEXT = (
    "Организатор:\n\n"
    "Партнеры:\n\n"
    "1. Papa Moscow Club (https://clck.ru/3STemX)\n\n"
    "2. Новый балет - руководитель компании и режиссер ивента Екатерина Черных (https://clck.ru/3STepM)\n\n"
    "3. Кейтеринговая компания Modul catering   (https://clck.ru/3STetU)\n"
    "3.1. https://modulcatering.ru/\n\n"
    "4. Креативный директор Артемий Фогель (http://clck.ru/3STevE)\n\n"
    "5. Алкогольная компания «AST\" (https://www.ast-inter.ru/)\n\n"
    "6. Шоу-балет \"G-style\"  (http://clck.ru/3STewk)\n\n"
    "7. Фламенко (http://clck.ru/3STexT) 💃\n\n"
    "8. Продакшн: видеограф Дима (http://clck.ru/3STeyF)\n\n"
    "9. Рилсмейкер Настя (http://clck.ru/3STeyw)\n\n"
    "10. Внедрение AI - Загоскин Александр (https://ai-resheniya.pro/)\n\n"
    "11. Разработка программного обеспечения Bullweb (http://www.bullweb.ru/)"
)

EVENT_PROGRAM_TEXT = (
    "⭐️ Закрытый клиентский ивент от агентства Show & Circus\n\n"
    "📍 Локация: Papa Moscow Club\n"
    "📅 Дата и время: 16 марта, 18:00–23:00\n\n"
    "Гостей вечера ждёт встреча профессионалов индустрии мероприятий: владельцев ивент-агентств Москвы, Санкт-Петербурга, Казани и Дубая, организаторов событий, режиссёров и предпринимателей.\n\n"
    "В программе вечера: тренды 2026 года в show-production, новые решения в catering и alcohol production, современные welcome-форматы, декор, event-локации, концерты и живая музыка.\n\n"
    "Программа вечера\n"
    "18:00 — Сбор гостей и welcome\n"
    "18:30 — Открытие вечера и приветственное слово организаторов\n"
    "19:00 — Презентации партнёров и тренды индустрии мероприятий\n"
    "20:00 — Шоу-программа и выступления артистов\n"
    "21:00 — Розыгрыш призов от партнёров\n"
    "21:30 — Нетворкинг и свободное общение гостей\n"
    "22:30 — Финальная шоу-программа\n"
    "23:00 — Завершение мероприятия"
)

MESSAGE_KEY_INTRO = "intro"
MESSAGE_KEY_REGISTRATION_INFO = "registration_info"
MESSAGE_KEY_REGISTRATION_SUCCESS = "registration_success"
MESSAGE_KEY_EVENT_PROGRAM = "event_program"
MESSAGE_KEY_PARTNERS = "partners"
MESSAGE_KEY_ALREADY_REGISTERED = "already_registered"
MESSAGE_KEY_START_REGISTRATION = "start_registration"
MESSAGE_KEY_CONTACT_READ_FAILED = "contact_read_failed"
MESSAGE_KEY_USER_NOT_DETECTED = "user_not_detected"
MESSAGE_KEY_CONTACT_WRONG_OWNER = "contact_wrong_owner"
MESSAGE_KEY_WRONG_STEP_EXPECTED_TEXT = "wrong_step_expected_text"
MESSAGE_KEY_PHONE_TOO_SHORT = "phone_too_short"
MESSAGE_KEY_EMPTY_ANSWER = "empty_answer"
MESSAGE_KEY_PHONE_ONLY_CONTACT = "phone_only_contact"
MESSAGE_KEY_TICKET_NOT_FOUND = "ticket_not_found"
MESSAGE_KEY_MY_TICKET = "my_ticket"
MESSAGE_KEY_TICKET_CONGRATULATIONS = "ticket_congratulations"
MESSAGE_KEY_NO_ACTIVE_TICKET = "no_active_ticket"
MESSAGE_KEY_TICKET_ALREADY_ACTIVATED = "ticket_already_activated"
MESSAGE_KEY_TICKET_ANNULLED = "ticket_annulled"
MESSAGE_KEY_MAIN_MENU = "main_menu"
MESSAGE_KEY_CONTACT_ORGANIZER = "contact_organizer"
MESSAGE_KEY_FALLBACK_START = "fallback_start"
MESSAGE_KEY_REGISTRATION_STEP_PREFIX = "registration_step_prompt"

REGISTRATION_STEPS_BY_KEY = {step.key: step for step in REGISTRATION_STEPS}
REGISTRATION_STEP_MESSAGE_KEYS = {
    step.key: f"{MESSAGE_KEY_REGISTRATION_STEP_PREFIX}.{step.key}"
    for step in REGISTRATION_STEPS
}

BOT_MESSAGE_TEMPLATES = {
    MESSAGE_KEY_INTRO: INTRO_TEXT,
    MESSAGE_KEY_REGISTRATION_INFO: REGISTRATION_INFO_TEXT,
    MESSAGE_KEY_REGISTRATION_SUCCESS: REGISTRATION_SUCCESS_TEXT,
    MESSAGE_KEY_EVENT_PROGRAM: EVENT_PROGRAM_TEXT,
    MESSAGE_KEY_PARTNERS: PARTNERS_TEXT,
    MESSAGE_KEY_ALREADY_REGISTERED: (
        """Вы зарегистрированы на закрытом мероприятии Show & Circus.

Ваш персональный билет ждёт вас в разделе «Мой билет».

Если ваши планы изменятся вы можете аннулировать билет

До встречи на мероприятии."""
    ),
    MESSAGE_KEY_CONTACT_READ_FAILED: "Не удалось прочитать контакт. Попробуйте еще раз.",
    MESSAGE_KEY_USER_NOT_DETECTED: "Не удалось определить пользователя. Попробуйте снова.",
    MESSAGE_KEY_CONTACT_WRONG_OWNER: (
        "Нужно отправить контакт именно вашего Telegram-аккаунта. "
        "Нажмите кнопку 'Отправить контакт'."
    ),
    MESSAGE_KEY_WRONG_STEP_EXPECTED_TEXT: "Сейчас ожидается другой шаг. Введите ответ в тексте.",
    MESSAGE_KEY_PHONE_TOO_SHORT: (
        "Номер выглядит слишком коротким. Отправьте корректный номер."
    ),
    MESSAGE_KEY_EMPTY_ANSWER: "Пустой ответ не подходит. Введите значение еще раз.",
    MESSAGE_KEY_PHONE_ONLY_CONTACT: (
        "Номер телефона принимается только через кнопку 'Отправить контакт'."
    ),
    MESSAGE_KEY_TICKET_NOT_FOUND: "Билет не найден. Пройдите регистрацию через /start.",
    MESSAGE_KEY_MY_TICKET: (
        "ВАШ БИЛЕТ № {ticket_number}\n"
        "на закрытое мероприятие от «Show & Circus».\n\n"
        "Локация: Papa Moscow Club\n"
        "Дата и время: 16 марта, 18:00–23:00\n\n"
        "Концепция вечера — «Драгоценные камни».\n"
        "Гость это драгоценность, которая делает индустрию ярче."
    ),
    MESSAGE_KEY_TICKET_CONGRATULATIONS: TICKET_CONGRATULATIONS_TEXT,
    MESSAGE_KEY_NO_ACTIVE_TICKET: "Активного билета не найдено.",
    MESSAGE_KEY_TICKET_ALREADY_ACTIVATED: (
        "Этот билет уже активирован на входе, аннулирование недоступно."
    ),
    MESSAGE_KEY_TICKET_ANNULLED: (
        "Ваш билет аннулирован.\n\n"
        "Нам очень жаль, что вы не сможете присутствовать на мероприятии Show & Circus.\n"
        "Будем рады видеть вас на следующих событиях."
    ),
    MESSAGE_KEY_MAIN_MENU: "Выберите нужный раздел👇",
    MESSAGE_KEY_CONTACT_ORGANIZER: (
        "Имя: Sabina\n"
        "Телефон: +79857759888\n"
        "Telegram: @showandcircus\n\n"
        "Show&Circus\n"
        "Сайт: https://showandcircus.com\n"
        "IG: https://www.instagram.com/showandcircus\n\n"
        "Звоните, пишите!\n"
        "Мы на связи 📱\n\n"
        "*IG — социальная сеть признанная экстремистской и запрещённая на территории РФ"
    ),
    MESSAGE_KEY_FALLBACK_START: (
        "Напишите /start, чтобы открыть главное меню и регистрацию."
    ),
}
BOT_MESSAGE_TEMPLATES.update(
    {
        key: REGISTRATION_STEPS_BY_KEY[step_key].prompt
        for step_key, key in REGISTRATION_STEP_MESSAGE_KEYS.items()
    }
)

BOT_STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"
BOT_MESSAGES_IMAGES_DIR = BOT_STATIC_DIR / "bot_messages"
BOT_MESSAGES_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
BOT_TICKETS_IMAGES_DIR = BOT_STATIC_DIR / "tickets"
BOT_TICKETS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
TICKET_TEMPLATE_IMAGE_PATH = BOT_MESSAGES_IMAGES_DIR / "without_qr_code.jpg"
TICKET_FOREGROUND_COLOR = (0x58, 0x2D, 0x15, 0xFF)
TICKET_QR_SIDE = 357
TICKET_QR_TOP_LEFT = (580, 258+75)

# message_key -> источник фото:
# - прямая ссылка: "https://example.com/image.jpg"
# - имя файла в app/static/bot_messages: "intro.jpg"
# - статический путь: "/static/bot_messages/intro.jpg"
MESSAGE_PHOTO_SOURCES: dict[str, str] = {
    MESSAGE_KEY_INTRO: "start_command.png",
    MESSAGE_KEY_REGISTRATION_INFO: "go_registration.png",
    REGISTRATION_STEP_MESSAGE_KEYS["full_name"]: "go_registration.png",
    MESSAGE_KEY_REGISTRATION_SUCCESS: "registration_success.png",
    MESSAGE_KEY_MAIN_MENU: "main_menu.png",
    MESSAGE_KEY_EVENT_PROGRAM: "programma_of_event.png",
    MESSAGE_KEY_PARTNERS: "partners.png",
    MESSAGE_KEY_CONTACT_ORGANIZER: "contacts.png",
    MESSAGE_KEY_TICKET_ALREADY_ACTIVATED: "ticket_activated.png",
    MESSAGE_KEY_TICKET_ANNULLED: "ticket_annulirovan.png",
}


def build_ticket_image_path(ticket_number: str) -> Path:
    safe_ticket_number = re.sub(r"[^a-zA-Z0-9_-]", "_", ticket_number)
    return BOT_TICKETS_IMAGES_DIR / f"{safe_ticket_number}.png"


def create_ticket_qr_image(payload: str, qr_side: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=0,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_image = qr.make_image(
        fill_color=(TICKET_FOREGROUND_COLOR[0], TICKET_FOREGROUND_COLOR[1], TICKET_FOREGROUND_COLOR[2]),
        back_color="white",
    ).convert("RGBA")
    qr_pixels = []
    for red, green, blue, _ in qr_image.getdata():
        if red == 255 and green == 255 and blue == 255:
            qr_pixels.append((255, 255, 255, 0))
        else:
            qr_pixels.append(TICKET_FOREGROUND_COLOR)
    qr_image.putdata(qr_pixels)
    return qr_image.resize((qr_side, qr_side), Image.Resampling.NEAREST)


def ensure_ticket_image(ticket_number: str) -> Path | None:
    if not ticket_number:
        return None

    result_path = build_ticket_image_path(ticket_number)
    if not TICKET_TEMPLATE_IMAGE_PATH.exists():
        return None

    with Image.open(TICKET_TEMPLATE_IMAGE_PATH).convert("RGBA") as template_image:
        qr_image = create_ticket_qr_image(
            payload=ticket_number,
            qr_side=TICKET_QR_SIDE,
        )
        qr_x, qr_y = TICKET_QR_TOP_LEFT
        template_image.paste(qr_image, (qr_x, qr_y), qr_image)
        template_image.save(result_path, format="PNG")

    return result_path


def render_bot_message(message_key: str, **context: str) -> str:
    template = BOT_MESSAGE_TEMPLATES[message_key]
    safe_context = {k: html.escape(str(v)) for k, v in context.items()}
    return template.format(**safe_context)


def resolve_photo_source(photo_source: str) -> str | FSInputFile:
    normalized_source = photo_source.strip()
    if normalized_source.startswith(("http://", "https://")):
        return normalized_source

    if normalized_source.startswith("/static/"):
        relative_parts = normalized_source.removeprefix("/static/").split("/")
        absolute_path = BOT_STATIC_DIR.joinpath(*relative_parts)
        return FSInputFile(str(absolute_path))

    return FSInputFile(str(BOT_MESSAGES_IMAGES_DIR / normalized_source))


async def send_bot_message(
    message: Message,
    message_key: str,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
    **context: str,
) -> None:
    text = render_bot_message(message_key, **context)
    photo_source = MESSAGE_PHOTO_SOURCES.get(message_key)
    if photo_source:
        try:
            await message.answer_photo(
                photo=resolve_photo_source(photo_source),
                caption=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


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
                    text="ПОЛУЧИТЬ БИЛЕТ 🎫",
                    callback_data=CALLBACK_START_REGISTRATION,
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


def build_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="Отправить контакт",
                    request_contact=True,
                    style="primary",
                )
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="МОЙ БИЛЕТ",
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
                    text="ПАРТНЁРЫ МЕРОПРИЯТИЯ",
                    callback_data=CALLBACK_SHOW_PARTNERS,
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
    message_key: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    **context: str,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    text = render_bot_message(message_key, **context)
    photo_source = MESSAGE_PHOTO_SOURCES.get(message_key)

    if photo_source:
        await callback.message.answer_photo(
            photo=resolve_photo_source(photo_source),
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        await callback.message.answer(text, reply_markup=reply_markup)
    await callback.answer()


async def ask_next_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    step_index = data.get("step_index", 0)
    if step_index >= len(REGISTRATION_STEPS):
        if message.from_user is None:
            await send_bot_message(message, MESSAGE_KEY_USER_NOT_DETECTED)
            return

        answers = data.get("answers", {})
        ticket_number = await complete_registration(
            bot=message.bot,
            user=message.from_user,
            answers_data=answers,
        )
        ticket_path = ensure_ticket_image(ticket_number)
        name = (message.from_user.first_name or "Гость") if message.from_user else "Гость"
        caption = render_bot_message(
            MESSAGE_KEY_TICKET_CONGRATULATIONS,
            name=name,
        )
        if ticket_path:
            await message.answer_photo(
                photo=FSInputFile(str(ticket_path)),
                caption=caption,
                reply_markup=build_main_menu_keyboard(),
            )
        else:
            await message.answer(
                caption,
                reply_markup=build_main_menu_keyboard(),
            )
        await state.clear()
        return

    step = REGISTRATION_STEPS[step_index]
    step_message_key = REGISTRATION_STEP_MESSAGE_KEYS[step.key]
    if step.key == "phone":
        from_user = message.from_user
        first_name = from_user.first_name or "Пользователь"
        await send_bot_message(
            message,
            step_message_key,
            reply_markup=build_phone_keyboard(),
            first_name=first_name,
        )
    else:
        await send_bot_message(
            message,
            step_message_key,
            reply_markup=ReplyKeyboardRemove(),
        )
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
            await send_bot_message(
                message,
                MESSAGE_KEY_MAIN_MENU,
                reply_markup=build_main_menu_keyboard(),
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
            await send_bot_message(
                message,
                MESSAGE_KEY_MAIN_MENU,
                reply_markup=build_main_menu_keyboard(),
            )
            return

    await state.clear()
    await send_bot_message(
        message,
        MESSAGE_KEY_INTRO,
        reply_markup=build_start_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_SHOW_REGISTRATION_INFO)
async def show_registration_info(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    await state.clear()
    await state.update_data(step_index=0, answers={})
    await ask_next_step(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_START_REGISTRATION)
async def start_registration_from_button(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    await state.update_data(step_index=0, answers={})
    await ask_next_step(callback.message, state)
    await callback.answer()


@router.message(RegistrationState.waiting_for_step, F.contact)
async def process_phone_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact is None:
        await send_bot_message(message, MESSAGE_KEY_CONTACT_READ_FAILED)
        return
    if message.from_user is None:
        await send_bot_message(message, MESSAGE_KEY_USER_NOT_DETECTED)
        return
    if contact.user_id != message.from_user.id:
        await send_bot_message(message, MESSAGE_KEY_CONTACT_WRONG_OWNER)
        return

    data = await state.get_data()
    step_index = data.get("step_index", 0)
    if step_index >= len(REGISTRATION_STEPS):
        await ask_next_step(message, state)
        return

    step = REGISTRATION_STEPS[step_index]
    if step.key != "phone":
        await send_bot_message(message, MESSAGE_KEY_WRONG_STEP_EXPECTED_TEXT)
        return

    phone = normalize_phone(contact.phone_number)
    if len(phone.replace("+", "")) < 10:
        await send_bot_message(message, MESSAGE_KEY_PHONE_TOO_SHORT)
        return

    answers = dict(data.get("answers", {}))
    answers[step.key] = phone
    await state.update_data(answers=answers, step_index=step_index + 1)
    await ask_next_step(message, state)


@router.message(RegistrationState.waiting_for_step, F.text)
async def process_registration_step(message: Message, state: FSMContext) -> None:
    user_text = (message.text or "").strip()
    if not user_text:
        await send_bot_message(message, MESSAGE_KEY_EMPTY_ANSWER)
        return

    data = await state.get_data()
    step_index = data.get("step_index", 0)
    if step_index >= len(REGISTRATION_STEPS):
        await ask_next_step(message, state)
        return

    step = REGISTRATION_STEPS[step_index]
    answers = dict(data.get("answers", {}))
    if step.key == "phone":
        await send_bot_message(
            message,
            MESSAGE_KEY_PHONE_ONLY_CONTACT,
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


async def complete_registration(
    bot: Bot,
    user: User,
    answers_data: dict[str, str],
) -> str:
    telegram_id = user.id
    username = user.username
    full_name = answers_data.get("full_name")
    telegram_avatar_url = await fetch_telegram_avatar_url(bot, telegram_id)

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
            not is_ticket_number_in_current_format(visitor.ticket.ticket_number)
            and not visitor.ticket.is_activated
        ):
            visitor.ticket.ticket_number = generate_unique_ticket_number(session)
            visitor.ticket.lottery_code = None

        session.commit()
        session.refresh(visitor)
        session.refresh(visitor.ticket)

        return visitor.ticket.ticket_number

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
                MESSAGE_KEY_TICKET_NOT_FOUND,
                reply_markup=build_back_to_main_menu_keyboard(),
            )
            return

        ticket_number = visitor.ticket.ticket_number

    name = (callback.from_user.first_name or "Гость") if callback.from_user else "Гость"
    ticket_image_path = ensure_ticket_image(ticket_number)
    ticket_text = render_bot_message(
        MESSAGE_KEY_TICKET_CONGRATULATIONS,
        name=name,
    )
    if ticket_image_path is not None:
        await callback.message.answer_photo(
            photo=FSInputFile(str(ticket_image_path)),
            caption=ticket_text,
            reply_markup=build_back_to_main_menu_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.answer(
        ticket_text,
        reply_markup=build_back_to_main_menu_keyboard(),
    )
    await callback.answer()


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
                MESSAGE_KEY_NO_ACTIVE_TICKET,
                reply_markup=build_back_to_main_menu_keyboard(),
            )
            return

        if visitor.ticket.is_activated:
            await edit_navigation_message(
                callback,
                MESSAGE_KEY_TICKET_ALREADY_ACTIVATED,
                reply_markup=build_back_to_main_menu_keyboard(),
            )
            return

        session.delete(visitor.ticket)
        visitor.is_registration_completed = False
        session.commit()

    await edit_navigation_message(
        callback,
        MESSAGE_KEY_TICKET_ANNULLED,
        reply_markup=build_back_to_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_BACK_TO_MAIN_MENU)
async def back_to_main_menu(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        MESSAGE_KEY_MAIN_MENU,
        reply_markup=build_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_SHOW_EVENT_PROGRAM)
async def show_event_program(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        MESSAGE_KEY_EVENT_PROGRAM,
        reply_markup=build_back_to_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_SHOW_PARTNERS)
async def show_partners(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        MESSAGE_KEY_PARTNERS,
        reply_markup=build_back_to_main_menu_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_CONTACT_ORGANIZER)
async def contact_organizer(callback: CallbackQuery) -> None:
    await edit_navigation_message(
        callback,
        MESSAGE_KEY_CONTACT_ORGANIZER,
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
    await send_bot_message(message, MESSAGE_KEY_FALLBACK_START)


async def run_bot() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Fill it in .env file.")

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
