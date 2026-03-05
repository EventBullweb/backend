from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket


def activate_ticket(db: Session, ticket_code: str) -> tuple[str, Ticket | None]:
    ticket = db.scalar(select(Ticket).where(Ticket.ticket_code == ticket_code))
    if ticket is None:
        return "not_found", None

    if ticket.is_activated:
        return "already_activated", ticket

    ticket.is_activated = True
    ticket.activated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return "activated", ticket
