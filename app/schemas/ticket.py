from datetime import datetime

from pydantic import BaseModel


class TicketActivateRequest(BaseModel):
    ticket_code: str


class TicketActivateResponse(BaseModel):
    status: str
    ticket_code: str
    activated_at: datetime | None = None
