from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ticket import (
    TicketActivateRequest,
    TicketActivateResponse,
    TicketCheckinStatsResponse,
    TicketOwnerSchema,
)
from app.services.telegram_notifications import notify_ticket_activated
from app.services.tickets import activate_ticket, get_checkin_stats

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/tickets/activate", tags=["tickets"], response_model=TicketActivateResponse)
async def activate_ticket_endpoint(
    payload: TicketActivateRequest,
    db: Session = Depends(get_db),
) -> TicketActivateResponse:
    activation_status, ticket = activate_ticket(
        db=db,
        ticket_number=payload.ticket_number,
    )

    if activation_status == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Activation error",
        )

    if activation_status == "activated" and ticket.lottery_code:
        await notify_ticket_activated(
            telegram_id=ticket.visitor.telegram_id,
            lottery_code=ticket.lottery_code,
        )

    return TicketActivateResponse(
        status=activation_status,
        ticket_number=ticket.ticket_number,
        lottery_code=ticket.lottery_code,
        activated_at=ticket.activated_at,
        owner=TicketOwnerSchema(
            telegram_id=ticket.visitor.telegram_id,
            username=ticket.visitor.username,
            full_name=ticket.visitor.full_name,
            telegram_avatar_url=ticket.visitor.telegram_avatar_url,
        ),
    )


@router.get(
    "/tickets/checkin-stats",
    tags=["tickets"],
    response_model=TicketCheckinStatsResponse,
)
async def checkin_stats_endpoint(
    db: Session = Depends(get_db),
) -> TicketCheckinStatsResponse:
    expected, already_activated = get_checkin_stats(db=db)
    return TicketCheckinStatsResponse(
        expected=expected,
        already_activated=already_activated,
    )
