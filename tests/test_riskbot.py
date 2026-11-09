import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from riskbot.config import Settings
from riskbot.daraja import CallbackError, parse_confirmation
from riskbot.risk import evaluate_risks
from riskbot.storage import initialize_database, save_transaction
from riskbot.web import create_app


def test_settings(database_path: Path) -> Settings:
    return Settings(
        database_path=database_path,
        timezone="Africa/Nairobi",
        alert_hour=21,
        max_single_transaction_kes=Decimal("1000"),
        max_daily_payer_total_kes=Decimal("1500"),
        max_daily_payer_transactions=2,
        owner_phone="",
        dashboard_token="test-dashboard-secret",
        whatsapp_provider="",
        ultramsg_instance_id="",
        ultramsg_token="",
        wati_base_url="",
        wati_api_token="",
        request_timeout_seconds=1,
    )


class RiskBotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.sqlite3"
        self.settings = test_settings(self.database_path)
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_parses_c2b_confirmation_and_converts_amount(self) -> None:
        transaction = parse_confirmation(
            {
                "TransID": "AB123",
                "TransAmount": "123.45",
                "TransTime": "20261021120000",
                "MSISDN": "254712345678",
                "BusinessShortCode": "123456",
            },
            "Africa/Nairobi",
        )
        self.assertEqual(transaction["receipt_number"], "AB123")
        self.assertEqual(transaction["amount_minor"], 12345)
        self.assertEqual(transaction["payer_phone"], "254712345678")
        self.assertEqual(
            transaction["transaction_time"].utcoffset().total_seconds(), 10800
        )

    def test_rejects_missing_receipt(self) -> None:
        with self.assertRaises(CallbackError):
            parse_confirmation(
                {"TransAmount": "10", "TransTime": "20261021120000"},
                "Africa/Nairobi",
            )

    def test_daily_risk_rules_group_by_payer(self) -> None:
        payloads = [
            ("A1", 800, "254700000001", "20261021100000"),
            ("A2", 800, "254700000001", "20261021110000"),
            ("B1", 1100, "254700000002", "20261021120000"),
        ]
        for receipt, amount, phone, timestamp in payloads:
            transaction = parse_confirmation(
                {
                    "TransID": receipt,
                    "TransAmount": str(amount),
                    "TransTime": timestamp,
                    "MSISDN": phone,
                },
                self.settings.timezone,
            )
            self.assertTrue(
                save_transaction(
                    self.database_path,
                    **transaction,
                    raw_payload={"TransID": receipt},
                )
            )

        count, total_minor, risks = evaluate_risks(
            self.settings, date(2026, 10, 21)
        )
        self.assertEqual(count, 3)
        self.assertEqual(total_minor, 270000)
        self.assertEqual(len(risks), 2)
        self.assertTrue(any("Daily payer total" in risk for risk in risks))
        self.assertTrue(any("Large payment" in risk for risk in risks))

    def test_daily_evaluation_uses_nairobi_day_boundary(self) -> None:
        for receipt, timestamp in (
            ("LATE", "20261021233000"),
            ("NEXT", "20261022003000"),
        ):
            transaction = parse_confirmation(
                {
                    "TransID": receipt,
                    "TransAmount": "50",
                    "TransTime": timestamp,
                    "MSISDN": "254700000001",
                },
                self.settings.timezone,
            )
            save_transaction(
                self.database_path,
                **transaction,
                raw_payload={"TransID": receipt},
            )

        count, total_minor, risks = evaluate_risks(
            self.settings, date(2026, 10, 21)
        )
        self.assertEqual(count, 1)
        self.assertEqual(total_minor, 5000)
        self.assertEqual(risks, [])

    def test_confirmation_endpoint_is_idempotent(self) -> None:
        client = create_app(self.settings).test_client()
        payload = {
            "TransID": "UNIQUE1",
            "TransAmount": "25",
            "TransTime": "20261021120000",
            "MSISDN": "254712345678",
        }
        first = client.post("/mpesa/confirmation", json=payload)
        second = client.post("/mpesa/confirmation", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.get_json()["duplicate"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["duplicate"])

    def test_dashboard_requires_token_and_returns_live_summary(self) -> None:
        client = create_app(self.settings).test_client()
        self.assertEqual(client.get("/api/dashboard").status_code, 401)

        transaction = parse_confirmation(
            {
                "TransID": "DASH1",
                "TransAmount": "125",
                "TransTime": datetime.now(ZoneInfo(self.settings.timezone)).strftime(
                    "%Y%m%d%H%M%S"
                ),
                "MSISDN": "254712345678",
            },
            self.settings.timezone,
        )
        save_transaction(
            self.database_path,
            **transaction,
            raw_payload={"TransID": "DASH1"},
        )
        response = client.get(
            "/api/dashboard",
            headers={"Authorization": "Bearer test-dashboard-secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["transaction_count"], 1)
        self.assertEqual(response.get_json()["transactions"][0]["receipt_number"], "DASH1")


if __name__ == "__main__":
    unittest.main()
