from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ticket import TicketActivateRequest, TicketActivateResponse
from app.services.tickets import activate_ticket

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/tickets/activate", tags=["tickets"], response_model=TicketActivateResponse)
async def activate_ticket_endpoint(
    payload: TicketActivateRequest,
    db: Session = Depends(get_db),
) -> TicketActivateResponse:
    activation_status, ticket = activate_ticket(db=db, ticket_code=payload.ticket_code)

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

    return TicketActivateResponse(
        status=activation_status,
        ticket_code=ticket.ticket_code,
        activated_at=ticket.activated_at,
    )
