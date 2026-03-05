import random
import string
from io import BytesIO

import qrcode


def generate_ticket_code() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=4))
    digits = "".join(random.choices(string.digits, k=6))
    return f"{letters}-{digits}"


def generate_qr_png(ticket_code: str) -> bytes:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(ticket_code)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()
