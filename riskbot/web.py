import logging
import hmac
import os
from contextlib import closing
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from waitress import serve

from riskbot.config import Settings
from riskbot.daraja import CallbackError, parse_confirmation
from riskbot.risk import evaluate_risks
from riskbot.storage import connect, initialize_database, save_transaction
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    configured = settings or Settings.from_env()
    initialize_database(configured.database_path)

    @app.get("/")
    def dashboard() -> Any:
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/healthz")
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.get("/api/dashboard")
    def dashboard_data() -> Any:
        if not configured.dashboard_token:
            return jsonify({"error": "Dashboard access is not configured"}), 503
        authorization = request.headers.get("Authorization", "")
        supplied_token = authorization.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied_token, configured.dashboard_token):
            return jsonify({"error": "Dashboard token is missing or invalid"}), 401

        business_date = datetime.now(ZoneInfo(configured.timezone)).date()
        count, total_minor, risks = evaluate_risks(configured, business_date)
        with closing(connect(configured.database_path)) as connection, connection:
            rows = connection.execute(
                """
                SELECT receipt_number, amount_minor, payer_phone, transaction_time,
                       account_reference
                FROM transactions
                ORDER BY transaction_time DESC
                LIMIT 10
                """
            ).fetchall()

        return jsonify(
            {
                "mode": "live",
                "business_date": business_date.isoformat(),
                "timezone": configured.timezone,
                "transaction_count": count,
                "total_minor": total_minor,
                "risk_count": len(risks),
                "risks": risks,
                "rules": {
                    "max_single_transaction_kes": str(
                        configured.max_single_transaction_kes
                    ),
                    "max_daily_payer_total_kes": str(
                        configured.max_daily_payer_total_kes
                    ),
                    "max_daily_payer_transactions": (
                        configured.max_daily_payer_transactions
                    ),
                },
                "transactions": [
                    {
                        "receipt_number": row["receipt_number"],
                        "amount_minor": row["amount_minor"],
                        "payer_phone": row["payer_phone"],
                        "transaction_time": row["transaction_time"],
                        "account_reference": row["account_reference"],
                    }
                    for row in rows
                ],
            }
        )

    @app.post("/mpesa/confirmation")
    def confirmation() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        try:
            transaction = parse_confirmation(payload, configured.timezone)
        except CallbackError as exc:
            logger.warning("Rejected invalid M-Pesa confirmation: %s", exc)
            return jsonify({"error": str(exc)}), 400

        inserted = save_transaction(
            configured.database_path,
            **transaction,
            raw_payload=payload,
        )
        return jsonify(
            {
                "ResultCode": 0,
                "ResultDesc": "Accepted",
                "duplicate": not inserted,
            }
        )

    @app.post("/mpesa/validation")
    def validation() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ResultCode": 1, "ResultDesc": "Invalid request"}), 400
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    serve(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")), threads=4)


if __name__ == "__main__":
    main()
