from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Ticket, Visitor, VisitorAnswer
from app.services.tickets import get_project_detailed_stats

TOTALS_LABELS = {
    "visitors": "Всего пользователей",
    "registrations_completed": "Завершили регистрацию",
    "tickets": "Выдано билетов",
    "activated_tickets": "Активировано билетов",
    "visitor_answers": "Всего ответов",
    "broadcast_deliveries": "Всего доставок рассылок",
}

FUNNEL_LABELS = {
    "visitors_total": "Пользователи всего",
    "registrations_completed": "Регистрация завершена",
    "tickets_issued": "Билеты выданы",
    "tickets_activated": "Билеты активированы",
    "registration_completion_rate": "Конверсия завершения регистрации (%)",
    "ticket_issue_rate_from_completed": "Конверсия выдачи билета из завершивших (%)",
    "ticket_activation_rate_from_issued": "Конверсия активации из выданных (%)",
    "ticket_activation_rate_from_visitors": "Конверсия активации из всех пользователей (%)",
}

TICKETS_LABELS = {
    "expected": "Выдано билетов",
    "already_activated": "Активировано билетов",
    "not_activated": "Не активировано билетов",
    "with_lottery_code": "С лотерейным кодом",
    "without_lottery_code": "Без лотерейного кода",
}

ANSWERS_LABELS = {
    "total_answers": "Всего ответов",
    "unique_respondents": "Уникальных ответивших",
    "average_answers_per_respondent": "Среднее число ответов на пользователя",
}

BROADCAST_LABELS = {
    "total_deliveries": "Всего доставок",
    "unique_recipients": "Уникальных получателей",
}


def _fit_columns(sheet) -> None:
    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, len(value))
        sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 70)


def _format_datetime(value) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def build_lottery_tickets_excel(db: Session) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Лотерейные билеты"
    sheet.append(["Лотерейный код"])

    lottery_codes = db.scalars(
        select(Ticket.lottery_code)
        .where(
            Ticket.lottery_code.is_not(None),
            Ticket.lottery_code != "",
        )
        .order_by(Ticket.created_at.asc())
    ).all()
    for lottery_code in lottery_codes:
        sheet.append([lottery_code])

    _fit_columns(sheet)

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_analytics_excel(db: Session) -> bytes:
    workbook = Workbook()

    summary_sheet = workbook.active
    summary_sheet.title = "Сводная аналитика"
    stats = get_project_detailed_stats(db=db)
    summary_sheet.append(["Раздел", "Показатель", "Значение"])

    for key, value in stats["totals"].items():
        summary_sheet.append(["Итого", TOTALS_LABELS.get(key, key), value])
    for key, value in stats["funnel"].items():
        summary_sheet.append(["Воронка", FUNNEL_LABELS.get(key, key), value])
    for key, value in stats["tickets"].items():
        summary_sheet.append(["Билеты", TICKETS_LABELS.get(key, key), value])
    for key, value in stats["answers"].items():
        if key == "top_steps":
            continue
        summary_sheet.append(["Ответы", ANSWERS_LABELS.get(key, key), value])
    for key, value in stats["broadcast"].items():
        summary_sheet.append(["Рассылки", BROADCAST_LABELS.get(key, key), value])

    summary_sheet.append([])
    summary_sheet.append(["Топ шагов", "Ключ шага", "Название шага", "Ответов", "Уникальных пользователей"])
    for step in stats["answers"]["top_steps"]:
        summary_sheet.append(
            [
                "Топ шагов",
                step["step_key"],
                step["step_label"],
                step["answers_count"],
                step["unique_visitors"],
            ]
        )
    _fit_columns(summary_sheet)

    visitors_sheet = workbook.create_sheet("Пользователи")
    visitors_sheet.append(
        [
            "ID пользователя",
            "Телеграм ID",
            "Имя пользователя",
            "Полное имя",
            "Регистрация завершена",
            "Дата создания",
            "Дата обновления",
            "Номер билета",
            "Лотерейный код",
            "Билет активирован",
            "Дата активации билета",
            "Количество ответов",
        ]
    )

    visitors_rows = db.execute(
        select(
            Visitor.id,
            Visitor.telegram_id,
            Visitor.username,
            Visitor.full_name,
            Visitor.is_registration_completed,
            Visitor.created_at,
            Visitor.updated_at,
            Ticket.ticket_number,
            Ticket.lottery_code,
            Ticket.is_activated,
            Ticket.activated_at,
            func.count(VisitorAnswer.id).label("answers_count"),
        )
        .outerjoin(Ticket, Ticket.visitor_id == Visitor.id)
        .outerjoin(VisitorAnswer, VisitorAnswer.visitor_id == Visitor.id)
        .group_by(
            Visitor.id,
            Visitor.telegram_id,
            Visitor.username,
            Visitor.full_name,
            Visitor.is_registration_completed,
            Visitor.created_at,
            Visitor.updated_at,
            Ticket.ticket_number,
            Ticket.lottery_code,
            Ticket.is_activated,
            Ticket.activated_at,
        )
        .order_by(Visitor.created_at.asc())
    ).all()

    for row in visitors_rows:
        visitors_sheet.append(
            [
                row.id,
                row.telegram_id,
                row.username or "",
                row.full_name or "",
                "Да" if row.is_registration_completed else "Нет",
                _format_datetime(row.created_at),
                _format_datetime(row.updated_at),
                row.ticket_number or "",
                row.lottery_code or "",
                "Да" if row.is_activated else "Нет",
                _format_datetime(row.activated_at),
                row.answers_count,
            ]
        )
    _fit_columns(visitors_sheet)

    tickets_sheet = workbook.create_sheet("Билеты")
    tickets_sheet.append(
        [
            "ID билета",
            "ID пользователя",
            "Номер билета",
            "Лотерейный код",
            "Билет активирован",
            "Дата активации",
            "Дата создания",
            "Дата обновления",
        ]
    )

    tickets_rows = db.execute(select(Ticket).order_by(Ticket.created_at.asc())).scalars().all()
    for ticket in tickets_rows:
        tickets_sheet.append(
            [
                ticket.id,
                ticket.visitor_id,
                ticket.ticket_number,
                ticket.lottery_code or "",
                "Да" if ticket.is_activated else "Нет",
                _format_datetime(ticket.activated_at),
                _format_datetime(ticket.created_at),
                _format_datetime(ticket.updated_at),
            ]
        )
    _fit_columns(tickets_sheet)

    answers_sheet = workbook.create_sheet("Ответы пользователей")
    answers_sheet.append(
        [
            "ID ответа",
            "ID пользователя",
            "Ключ шага",
            "Название шага",
            "Ответ",
            "Дата создания",
            "Дата обновления",
        ]
    )

    answers_rows = db.execute(
        select(VisitorAnswer).order_by(
            VisitorAnswer.visitor_id.asc(),
            VisitorAnswer.created_at.asc(),
        )
    ).scalars().all()
    for answer in answers_rows:
        answers_sheet.append(
            [
                answer.id,
                answer.visitor_id,
                answer.step_key,
                answer.step_label,
                answer.value,
                _format_datetime(answer.created_at),
                _format_datetime(answer.updated_at),
            ]
        )
    _fit_columns(answers_sheet)

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
