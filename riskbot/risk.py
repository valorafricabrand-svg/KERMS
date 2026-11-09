from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from riskbot.config import Settings
from riskbot.storage import connect


def _minor_units(amount_kes: Decimal) -> int:
    return int(amount_kes * 100)


def evaluate_risks(settings: Settings, report_date: date) -> tuple[int, int, list[str]]:
    local_zone = ZoneInfo(settings.timezone)
    start_local = datetime.combine(report_date, time.min, tzinfo=local_zone)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).isoformat()
    end_utc = end_local.astimezone(timezone.utc).isoformat()

    with closing(connect(settings.database_path)) as connection, connection:
        rows = connection.execute(
            """
            SELECT receipt_number, amount_minor, payer_phone, transaction_time
            FROM transactions
            WHERE transaction_time >= ? AND transaction_time < ?
            ORDER BY transaction_time, receipt_number
            """,
            (start_utc, end_utc),
        ).fetchall()

    grouped: dict[str, list] = defaultdict(list)
    risks: list[str] = []
    total_minor = 0
    for row in rows:
        total_minor += row["amount_minor"]
        payer = row["payer_phone"] or f"unknown (receipt {row['receipt_number']})"
        grouped[payer].append(row)
        if row["amount_minor"] > _minor_units(settings.max_single_transaction_kes):
            amount = Decimal(row["amount_minor"]) / 100
            risks.append(
                f"Large payment: KES {amount:,.2f} "
                f"(receipt {row['receipt_number']}, payer {payer})."
            )

    for payer, payer_rows in grouped.items():
        payer_total = sum(row["amount_minor"] for row in payer_rows)
        if payer_total > _minor_units(settings.max_daily_payer_total_kes):
            total = Decimal(payer_total) / 100
            risks.append(
                f"Daily payer total is high: KES {total:,.2f} "
                f"across {len(payer_rows)} payment(s) for {payer}."
            )
        if len(payer_rows) > settings.max_daily_payer_transactions:
            risks.append(
                f"High payment frequency: {len(payer_rows)} payments "
                f"from {payer} today."
            )

    return len(rows), total_minor, risks


def format_alert(
    report_date: date, transaction_count: int, total_minor: int, risks: list[str]
) -> str:
    total = Decimal(total_minor) / 100
    lines = [
        f"Daily M-Pesa risk alert — {report_date.isoformat()}",
        f"Reviewed: {transaction_count} payment(s), KES {total:,.2f} total.",
        "",
        *risks[:20],
    ]
    if len(risks) > 20:
        lines.append(f"...and {len(risks) - 20} more risk flag(s).")
    return "\n".join(lines)
