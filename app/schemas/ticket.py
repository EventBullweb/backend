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


class TicketCheckinStatsResponse(BaseModel):
    expected: int
    already_activated: int


class StatsFunnelSchema(BaseModel):
    visitors_total: int
    registrations_completed: int
    tickets_issued: int
    tickets_activated: int
    registration_completion_rate: float
    ticket_issue_rate_from_completed: float
    ticket_activation_rate_from_issued: float
    ticket_activation_rate_from_visitors: float


class TicketStatsDetailsSchema(BaseModel):
    expected: int
    already_activated: int
    not_activated: int
    with_lottery_code: int
    without_lottery_code: int


class AnswerStepStatsSchema(BaseModel):
    step_key: str
    step_label: str
    answers_count: int
    unique_visitors: int


class AnswersStatsSchema(BaseModel):
    total_answers: int
    unique_respondents: int
    average_answers_per_respondent: float
    top_steps: list[AnswerStepStatsSchema]


class BroadcastStatsSchema(BaseModel):
    total_deliveries: int
    unique_recipients: int


class EntityTotalsSchema(BaseModel):
    visitors: int
    registrations_completed: int
    tickets: int
    activated_tickets: int
    visitor_answers: int
    broadcast_deliveries: int


class ProjectDetailedStatsResponse(BaseModel):
    totals: EntityTotalsSchema
    funnel: StatsFunnelSchema
    tickets: TicketStatsDetailsSchema
    answers: AnswersStatsSchema
    broadcast: BroadcastStatsSchema
