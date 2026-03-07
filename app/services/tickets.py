from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket
from app.services.ticket_numbers import build_lottery_code


def activate_ticket(db: Session, ticket_number: str) -> tuple[str, Ticket | None]:
    ticket = db.scalar(select(Ticket).where(Ticket.ticket_number == ticket_number))
    if ticket is None:
        return "not_found", None

    if ticket.is_activated:
        return "already_activated", ticket

    ticket.is_activated = True
    ticket.activated_at = datetime.now(timezone.utc)
    ticket.lottery_code = build_lottery_code(ticket.ticket_number)
    db.commit()
    db.refresh(ticket)
    return "activated", ticket
