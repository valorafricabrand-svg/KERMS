import argparse
import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from zoneinfo import ZoneInfo

from riskbot.config import Settings
from riskbot.service import run_daily_check
from riskbot.storage import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the risk check immediately instead of starting the scheduler",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="Business date in YYYY-MM-DD format (only with --once)",
    )
    arguments = parser.parse_args()
    if arguments.date and not arguments.once:
        parser.error("--date can only be used with --once")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = Settings.from_env()
    initialize_database(settings.database_path)
    if arguments.once:
        run_daily_check(settings, arguments.date)
        return

    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        run_daily_check,
        trigger="cron",
        hour=settings.alert_hour,
        minute=0,
        args=[settings],
        id="daily-risk-check",
        max_instances=1,
        coalesce=True,
    )
    logging.getLogger(__name__).info(
        "Daily risk check scheduled for %02d:00 %s",
        settings.alert_hour,
        settings.timezone,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
