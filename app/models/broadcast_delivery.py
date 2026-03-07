from datetime import datetime

from sqlalchemy import BIGINT, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BroadcastDelivery(Base):
    __tablename__ = "broadcast_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "source_chat_id",
            "source_message_id",
            "recipient_telegram_id",
            name="uq_broadcast_source_recipient",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_chat_id: Mapped[int] = mapped_column(BIGINT, nullable=False, index=True)
    source_message_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    recipient_telegram_id: Mapped[int] = mapped_column(BIGINT, nullable=False, index=True)
    recipient_message_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
