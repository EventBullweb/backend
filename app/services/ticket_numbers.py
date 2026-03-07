import hashlib
import secrets


def generate_ticket_number(length: int = 13) -> str:
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def build_lottery_code(ticket_number: str) -> str:
    digest = hashlib.sha256(ticket_number.encode("utf-8")).hexdigest().upper()
    numeric_part = (int(digest[:12], 16) % 900000) + 100000
    suffix = digest[12:17]
    return f"{numeric_part}_{suffix}"
