import hashlib
import re
import secrets

TICKET_NUMBER_PATTERN = re.compile(r"^[A-Z]{2}-\d{4}$")


def generate_ticket_number() -> str:
    letters = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(2))
    digits = "".join(secrets.choice("0123456789") for _ in range(4))
    return f"{letters}-{digits}"


def is_ticket_number_in_current_format(ticket_number: str) -> bool:
    return bool(TICKET_NUMBER_PATTERN.fullmatch(ticket_number or ""))


def build_lottery_code(ticket_number: str) -> str:
    digest = hashlib.sha256(ticket_number.encode("utf-8")).hexdigest().upper()
    numeric_part = (int(digest[:12], 16) % 900000) + 100000
    suffix = digest[12:17]
    return f"{numeric_part}_{suffix}"
