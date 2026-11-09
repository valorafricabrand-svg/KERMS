import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database(database_path: Path) -> None:
    with closing(connect(database_path)) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                receipt_number TEXT PRIMARY KEY,
                amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
                payer_phone TEXT,
                transaction_time TEXT NOT NULL,
                business_shortcode TEXT,
                account_reference TEXT,
                raw_payload TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_transactions_time
                ON transactions(transaction_time);
            CREATE INDEX IF NOT EXISTS idx_transactions_payer_time
                ON transactions(payer_phone, transaction_time);
            CREATE TABLE IF NOT EXISTS daily_reports (
                report_date TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                details TEXT,
                error TEXT
            );
            """
        )


def save_transaction(
    database_path: Path,
    *,
    receipt_number: str,
    amount_minor: int,
    payer_phone: str | None,
    transaction_time: datetime,
    business_shortcode: str | None,
    account_reference: str | None,
    raw_payload: dict[str, Any],
) -> bool:
    with closing(connect(database_path)) as connection, connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO transactions (
                receipt_number, amount_minor, payer_phone, transaction_time,
                business_shortcode, account_reference, raw_payload, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_number,
                amount_minor,
                payer_phone,
                transaction_time.astimezone(timezone.utc).isoformat(),
                business_shortcode,
                account_reference,
                json.dumps(raw_payload, separators=(",", ":"), ensure_ascii=True),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cursor.rowcount == 1


def claim_daily_report(database_path: Path, report_date: date) -> bool:
    now = datetime.now(timezone.utc)
    with closing(connect(database_path)) as connection, connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO daily_reports
                (report_date, status, started_at)
            VALUES (?, 'running', ?)
            """,
            (report_date.isoformat(), now.isoformat()),
        )
        row = connection.execute(
            "SELECT status, started_at FROM daily_reports WHERE report_date = ?",
            (report_date.isoformat(),),
        ).fetchone()
        if row["status"] in {"sent", "completed"}:
            return False
        if row["status"] == "running":
            started_at = datetime.fromisoformat(row["started_at"])
            if (now - started_at).total_seconds() < 900:
                return False
        connection.execute(
            """
            UPDATE daily_reports
            SET status = 'running', started_at = ?, finished_at = NULL, error = NULL
            WHERE report_date = ?
            """,
            (now.isoformat(), report_date.isoformat()),
        )
        return True


def finish_daily_report(
    database_path: Path,
    report_date: date,
    *,
    status: str,
    details: str,
    error: str | None = None,
) -> None:
    with closing(connect(database_path)) as connection, connection:
        connection.execute(
            """
            UPDATE daily_reports
            SET status = ?, finished_at = ?, details = ?, error = ?
            WHERE report_date = ?
            """,
            (
                status,
                datetime.now(timezone.utc).isoformat(),
                details,
                error,
                report_date.isoformat(),
            ),
        )
