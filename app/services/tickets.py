from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BroadcastDelivery, Ticket, Visitor, VisitorAnswer
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


def get_checkin_stats(db: Session) -> tuple[int, int]:
    expected = db.scalar(select(func.count(Ticket.id))) or 0
    already_activated = (
        db.scalar(
            select(func.count(Ticket.id)).where(Ticket.is_activated.is_(True))
        )
        or 0
    )
    return expected, already_activated


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def get_project_detailed_stats(db: Session) -> dict:
    """Возвращает плоский объект воронки для API: 9 целочисленных счётчиков."""
    started_bot = db.scalar(select(func.count(Visitor.id))) or 0
    started_registration = (
        db.scalar(
            select(func.count(func.distinct(VisitorAnswer.visitor_id))).where(
                VisitorAnswer.step_key == "full_name"
            )
        )
        or 0
    )
    left_contact = (
        db.scalar(
            select(func.count(func.distinct(VisitorAnswer.visitor_id))).where(
                VisitorAnswer.step_key == "phone"
            )
        )
        or 0
    )
    registration_completed = (
        db.scalar(
            select(func.count(Visitor.id)).where(
                Visitor.is_registration_completed.is_(True)
            )
        )
        or 0
    )
    tickets_issued = db.scalar(select(func.count(Ticket.id))) or 0
    opened_my_ticket = 0  # в БД не логируется
    tickets_annulled = 0  # при аннулировании билет удаляется, истории нет
    attended_qr_scan = (
        db.scalar(
            select(func.count(Ticket.id)).where(Ticket.is_activated.is_(True))
        )
        or 0
    )
    lottery_participants = (
        db.scalar(
            select(func.count(Ticket.id)).where(Ticket.lottery_code.is_not(None))
        )
        or 0
    )
    return {
        "started_bot": started_bot,
        "started_registration": started_registration,
        "left_contact": left_contact,
        "registration_completed": registration_completed,
        "tickets_issued": tickets_issued,
        "opened_my_ticket": opened_my_ticket,
        "tickets_annulled": tickets_annulled,
        "attended_qr_scan": attended_qr_scan,
        "lottery_participants": lottery_participants,
    }


def get_project_analytics_for_excel(db: Session) -> dict:
    """Расширенная аналитика для экспорта в Excel (totals, funnel, tickets, answers, broadcast)."""
    visitors_total = db.scalar(select(func.count(Visitor.id))) or 0
    registrations_completed = (
        db.scalar(
            select(func.count(Visitor.id)).where(
                Visitor.is_registration_completed.is_(True)
            )
        )
        or 0
    )
    tickets_issued = db.scalar(select(func.count(Ticket.id))) or 0
    tickets_activated = (
        db.scalar(
            select(func.count(Ticket.id)).where(Ticket.is_activated.is_(True))
        )
        or 0
    )
    answers_total = db.scalar(select(func.count(VisitorAnswer.id))) or 0
    broadcast_deliveries_total = db.scalar(select(func.count(BroadcastDelivery.id))) or 0

    unique_respondents = (
        db.scalar(select(func.count(func.distinct(VisitorAnswer.visitor_id)))) or 0
    )
    unique_broadcast_recipients = (
        db.scalar(
            select(func.count(func.distinct(BroadcastDelivery.recipient_telegram_id)))
        )
        or 0
    )
    tickets_with_lottery_code = (
        db.scalar(
            select(func.count(Ticket.id)).where(Ticket.lottery_code.is_not(None))
        )
        or 0
    )

    top_steps_rows = db.execute(
        select(
            VisitorAnswer.step_key,
            VisitorAnswer.step_label,
            func.count(VisitorAnswer.id).label("answers_count"),
            func.count(func.distinct(VisitorAnswer.visitor_id)).label("unique_visitors"),
        )
        .group_by(VisitorAnswer.step_key, VisitorAnswer.step_label)
        .order_by(
            func.count(VisitorAnswer.id).desc(),
            VisitorAnswer.step_key.asc(),
        )
        .limit(10)
    ).all()

    not_activated = max(tickets_issued - tickets_activated, 0)
    without_lottery_code = max(tickets_issued - tickets_with_lottery_code, 0)

    return {
        "totals": {
            "visitors": visitors_total,
            "registrations_completed": registrations_completed,
            "tickets": tickets_issued,
            "activated_tickets": tickets_activated,
            "visitor_answers": answers_total,
            "broadcast_deliveries": broadcast_deliveries_total,
        },
        "funnel": {
            "visitors_total": visitors_total,
            "registrations_completed": registrations_completed,
            "tickets_issued": tickets_issued,
            "tickets_activated": tickets_activated,
            "registration_completion_rate": _safe_rate(
                registrations_completed,
                visitors_total,
            ),
            "ticket_issue_rate_from_completed": _safe_rate(
                tickets_issued,
                registrations_completed,
            ),
            "ticket_activation_rate_from_issued": _safe_rate(
                tickets_activated,
                tickets_issued,
            ),
            "ticket_activation_rate_from_visitors": _safe_rate(
                tickets_activated,
                visitors_total,
            ),
        },
        "tickets": {
            "expected": tickets_issued,
            "already_activated": tickets_activated,
            "not_activated": not_activated,
            "with_lottery_code": tickets_with_lottery_code,
            "without_lottery_code": without_lottery_code,
        },
        "answers": {
            "total_answers": answers_total,
            "unique_respondents": unique_respondents,
            "average_answers_per_respondent": (
                round(answers_total / unique_respondents, 2)
                if unique_respondents
                else 0.0
            ),
            "top_steps": [
                {
                    "step_key": row.step_key,
                    "step_label": row.step_label,
                    "answers_count": row.answers_count,
                    "unique_visitors": row.unique_visitors,
                }
                for row in top_steps_rows
            ],
        },
        "broadcast": {
            "total_deliveries": broadcast_deliveries_total,
            "unique_recipients": unique_broadcast_recipients,
        },
    }
