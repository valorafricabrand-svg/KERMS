import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from riskbot.config import Settings
from riskbot.risk import evaluate_risks, format_alert
from riskbot.storage import (
    claim_daily_report,
    finish_daily_report,
    initialize_database,
)
from riskbot.whatsapp import send_message

logger = logging.getLogger(__name__)


def run_daily_check(settings: Settings, report_date: date | None = None) -> bool:
    initialize_database(settings.database_path)
    local_date = report_date or (
        datetime.now(ZoneInfo(settings.timezone)).date() - timedelta(days=1)
    )
    if not claim_daily_report(settings.database_path, local_date):
        logger.info("Daily report for %s is already handled or in progress", local_date)
        return False

    try:
        count, total_minor, risks = evaluate_risks(settings, local_date)
        if not risks:
            details = f"No risk flags in {count} payment(s)."
            finish_daily_report(
                settings.database_path,
                local_date,
                status="completed",
                details=details,
            )
            logger.info("%s", details)
            return True

        message = format_alert(local_date, count, total_minor, risks)
        send_message(settings, message)
        finish_daily_report(
            settings.database_path,
            local_date,
            status="sent",
            details=message,
        )
        logger.info("Sent daily risk alert for %s", local_date)
        return True
    except Exception as exc:
        finish_daily_report(
            settings.database_path,
            local_date,
            status="failed",
            details="Daily risk check failed.",
            error=str(exc),
        )
        logger.exception("Daily risk check failed for %s", local_date)
        raise
