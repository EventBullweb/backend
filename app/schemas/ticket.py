from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field


class TicketActivateRequest(BaseModel):
    ticket_number: str = Field(
        validation_alias=AliasChoices("ticket_number", "ticket_code")
    )


class TicketOwnerSchema(BaseModel):
    telegram_id: int
    username: str | None = None
    full_name: str | None = None
    telegram_avatar_url: str | None = None


class TicketActivateResponse(BaseModel):
    status: str
    ticket_number: str
    lottery_code: str | None = None
    activated_at: datetime | None = None
    owner: TicketOwnerSchema
