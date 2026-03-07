import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Event Backend")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/event_db",
    )
    bot_token: str = os.getenv("BOT_TOKEN", "")
    content_channel_id: int = int(os.getenv("CONTENT_CHANNEL_ID", "0"))
    broadcast_batch_size: int = int(os.getenv("BROADCAST_BATCH_SIZE", "25"))
    broadcast_concurrency: int = int(os.getenv("BROADCAST_CONCURRENCY", "8"))


settings = Settings()
