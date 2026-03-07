import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import BroadcastDelivery, Visitor

logger = logging.getLogger(__name__)


def get_registered_recipient_ids(session: Session) -> list[int]:
    query = select(Visitor.telegram_id).where(Visitor.is_registration_completed.is_(True))
    return list(session.scalars(query).all())


def get_source_recipient_ids(
    session: Session,
    source_chat_id: int,
    source_message_id: int,
) -> list[int]:
    query = (
        select(BroadcastDelivery.recipient_telegram_id)
        .where(BroadcastDelivery.source_chat_id == source_chat_id)
        .where(BroadcastDelivery.source_message_id == source_message_id)
    )
    return list(session.scalars(query).all())


def has_source_deliveries(session: Session, source_chat_id: int, source_message_id: int) -> bool:
    query = (
        select(BroadcastDelivery.id)
        .where(BroadcastDelivery.source_chat_id == source_chat_id)
        .where(BroadcastDelivery.source_message_id == source_message_id)
        .limit(1)
    )
    return session.scalar(query) is not None


async def _copy_message_with_retry(
    bot: Bot,
    source_chat_id: int,
    source_message_id: int,
    recipient_telegram_id: int,
    retries: int = 3,
) -> int | None:
    for attempt in range(1, retries + 1):
        try:
            message = await bot.copy_message(
                chat_id=recipient_telegram_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id,
            )
            return message.message_id
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramForbiddenError:
            logger.info(
                "Skip recipient %s: bot is blocked or no access.",
                recipient_telegram_id,
            )
            return None
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if "chat not found" in error_text or "user is deactivated" in error_text:
                logger.info(
                    "Skip recipient %s: invalid or inactive chat.",
                    recipient_telegram_id,
                )
                return None
            if attempt >= retries:
                logger.exception(
                    "Failed to copy source message %s to %s: %s",
                    source_message_id,
                    recipient_telegram_id,
                    exc,
                )
                return None
            await asyncio.sleep(attempt)
        except Exception as exc:
            if attempt >= retries:
                logger.exception(
                    "Unexpected copy error for recipient %s: %s",
                    recipient_telegram_id,
                    exc,
                )
                return None
            await asyncio.sleep(attempt)
    return None


async def _delete_message_with_retry(
    bot: Bot,
    recipient_telegram_id: int,
    recipient_message_id: int,
    retries: int = 2,
) -> None:
    for attempt in range(1, retries + 1):
        try:
            await bot.delete_message(
                chat_id=recipient_telegram_id,
                message_id=recipient_message_id,
            )
            return
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
        except (TelegramForbiddenError, TelegramBadRequest):
            return
        except Exception:
            if attempt >= retries:
                return
            await asyncio.sleep(attempt)


async def broadcast_source_message(
    bot: Bot,
    session: Session,
    source_chat_id: int,
    source_message_id: int,
    recipient_ids: list[int],
) -> int:
    if not recipient_ids:
        return 0

    deliveries: list[BroadcastDelivery] = []
    semaphore = asyncio.Semaphore(max(settings.broadcast_concurrency, 1))

    async def send_to_recipient(recipient_telegram_id: int) -> None:
        async with semaphore:
            recipient_message_id = await _copy_message_with_retry(
                bot=bot,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
                recipient_telegram_id=recipient_telegram_id,
            )
            if recipient_message_id is None:
                return
            deliveries.append(
                BroadcastDelivery(
                    source_chat_id=source_chat_id,
                    source_message_id=source_message_id,
                    recipient_telegram_id=recipient_telegram_id,
                    recipient_message_id=recipient_message_id,
                )
            )

    batch_size = max(settings.broadcast_batch_size, 1)
    for offset in range(0, len(recipient_ids), batch_size):
        batch = recipient_ids[offset : offset + batch_size]
        await asyncio.gather(*(send_to_recipient(recipient_id) for recipient_id in batch))

    if not deliveries:
        return 0

    session.add_all(deliveries)
    session.commit()
    return len(deliveries)


async def remove_source_deliveries(
    bot: Bot,
    session: Session,
    source_chat_id: int,
    source_message_id: int,
) -> int:
    mappings = list(
        session.scalars(
            select(BroadcastDelivery)
            .where(BroadcastDelivery.source_chat_id == source_chat_id)
            .where(BroadcastDelivery.source_message_id == source_message_id)
        ).all()
    )
    if not mappings:
        return 0

    semaphore = asyncio.Semaphore(max(settings.broadcast_concurrency, 1))

    async def remove_mapping(mapping: BroadcastDelivery) -> None:
        async with semaphore:
            await _delete_message_with_retry(
                bot=bot,
                recipient_telegram_id=mapping.recipient_telegram_id,
                recipient_message_id=mapping.recipient_message_id,
            )

    await asyncio.gather(*(remove_mapping(mapping) for mapping in mappings))

    session.execute(
        delete(BroadcastDelivery)
        .where(BroadcastDelivery.source_chat_id == source_chat_id)
        .where(BroadcastDelivery.source_message_id == source_message_id)
    )
    session.commit()
    return len(mappings)
