import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _decimal_env(name: str, default: str) -> Decimal:
    value = os.getenv(name, default)
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal number") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{name} must be a finite, non-negative number")
    return parsed


@dataclass(frozen=True)
class Settings:
    database_path: Path
    timezone: str
    alert_hour: int
    max_single_transaction_kes: Decimal
    max_daily_payer_total_kes: Decimal
    max_daily_payer_transactions: int
    owner_phone: str
    dashboard_token: str
    whatsapp_provider: str
    ultramsg_instance_id: str
    ultramsg_token: str
    wati_base_url: str
    wati_api_token: str
    request_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        alert_hour = int(os.getenv("ALERT_HOUR", "21"))
        if not 0 <= alert_hour <= 23:
            raise ValueError("ALERT_HOUR must be between 0 and 23")

        max_daily_transactions = int(os.getenv("MAX_DAILY_PAYER_TRANSACTIONS", "20"))
        if max_daily_transactions < 1:
            raise ValueError("MAX_DAILY_PAYER_TRANSACTIONS must be at least 1")

        timeout = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
        if timeout < 1:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be positive")

        provider = os.getenv("WHATSAPP_PROVIDER", "").strip().lower()
        if provider not in {"", "ultramsg", "wati"}:
            raise ValueError("WHATSAPP_PROVIDER must be ultramsg or wati")
        timezone = os.getenv("TIMEZONE", "Africa/Nairobi")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("TIMEZONE must be a valid IANA timezone") from exc

        return cls(
            database_path=Path(os.getenv("DATABASE_PATH", "data/riskbot.sqlite3")),
            timezone=timezone,
            alert_hour=alert_hour,
            max_single_transaction_kes=_decimal_env(
                "MAX_SINGLE_TRANSACTION_KES", "100000"
            ),
            max_daily_payer_total_kes=_decimal_env(
                "MAX_DAILY_PAYER_TOTAL_KES", "250000"
            ),
            max_daily_payer_transactions=max_daily_transactions,
            owner_phone=os.getenv("OWNER_WHATSAPP_NUMBER", "").strip(),
            dashboard_token=os.getenv("DASHBOARD_TOKEN", "").strip(),
            whatsapp_provider=provider,
            ultramsg_instance_id=os.getenv("ULTRAMSG_INSTANCE_ID", "").strip(),
            ultramsg_token=os.getenv("ULTRAMSG_TOKEN", "").strip(),
            wati_base_url=os.getenv("WATI_BASE_URL", "").strip().rstrip("/"),
            wati_api_token=os.getenv("WATI_API_TOKEN", "").strip(),
            request_timeout_seconds=timeout,
        )
