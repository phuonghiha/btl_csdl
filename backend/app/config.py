import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables or backend/.env."""

    def __init__(self) -> None:
        self.mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
        self.mysql_user: str = os.getenv("MYSQL_USER", "root")
        self.mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
        self.mysql_database: str = os.getenv("MYSQL_DATABASE", "quan_ly_khach_san")
        self.jwt_secret: str = os.getenv("JWT_SECRET", "btl-csdl-dev-secret-change-me-32-bytes-minimum")
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))
        raw_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5175,http://127.0.0.1:5175",
        )
        self.cors_origins: list[str] = [o.strip() for o in raw_origins.split(",") if o.strip()]
        self.bank_code: str = os.getenv("BANK_CODE", "MB")
        self.bank_bin: str = os.getenv("BANK_BIN", "970422")
        self.bank_name: str = os.getenv("BANK_NAME", "MB Bank (Ngân hàng Quân đội)")
        self.bank_account_no: str = os.getenv("BANK_ACCOUNT_NO", "0383356237")
        self.bank_account_name: str = os.getenv("BANK_ACCOUNT_NAME", "VU NAM KHANH")
        self.bank_webhook_secret: str = os.getenv("BANK_WEBHOOK_SECRET", "btl-bank-webhook-secret-demo")


@lru_cache
def get_settings() -> Settings:
    return Settings()
