import hashlib
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import RiskBotAlert, RiskBotPolicy, RiskBotTransaction


def _masked_phone(phone):
    return f"{'*' * max(0, len(phone) - 4)}{phone[-4:]}" if phone else "unknown payer"


def _record_alert(
    *,
    policy,
    transaction_record,
    event_key,
    rule_code,
    severity,
    message,
    evidence,
):
    alert, created = RiskBotAlert.objects.get_or_create(
        organization=policy.organization,
        event_key=event_key,
        defaults={
            "transaction": transaction_record,
            "risk": policy.linked_risk,
            "rule_code": rule_code,
            "severity": severity,
            "message": message,
            "evidence": evidence,
        },
    )
    if not created:
        alert.transaction = transaction_record
        alert.message = message
        alert.evidence = evidence
        alert.save(update_fields=("transaction", "message", "evidence", "updated_at"))
    return alert


@transaction.atomic
def evaluate_bot_transaction(policy, transaction_record):
    if not policy.enabled:
        return []

    alerts = []
    amount = transaction_record.amount
    currency = policy.currency
    receipt = transaction_record.receipt_number
    if amount > policy.max_single_transaction:
        alerts.append(
            _record_alert(
                policy=policy,
                transaction_record=transaction_record,
                event_key=f"transaction:{receipt}:single_amount",
                rule_code="single_transaction_limit",
                severity=RiskBotAlert.Severity.HIGH,
                message=(
                    f"Payment {receipt} is {amount} {currency}, above the "
                    f"configured single-payment limit of "
                    f"{policy.max_single_transaction} {currency}."
                ),
                evidence={
                    "amount": str(amount),
                    "currency": currency,
                    "limit": str(policy.max_single_transaction),
                    "receipt_number": receipt,
                },
            )
        )

    if not transaction_record.payer_phone:
        return alerts

    local_time = timezone.localtime(
        transaction_record.transaction_time, ZoneInfo(policy.timezone)
    )
    business_date = local_time.date()
    start = datetime.combine(business_date, time.min, tzinfo=ZoneInfo(policy.timezone))
    end = start + timedelta(days=1)
    payer_transactions = RiskBotTransaction.objects.filter(
        organization=policy.organization,
        payer_phone=transaction_record.payer_phone,
        currency=currency,
        transaction_time__gte=start,
        transaction_time__lt=end,
    )
    count = payer_transactions.count()
    daily_total = sum(payer_transactions.values_list("amount", flat=True), Decimal("0"))
    payer_hash = hashlib.sha256(
        transaction_record.payer_phone.encode("utf-8")
    ).hexdigest()[:20]
    payer_label = _masked_phone(transaction_record.payer_phone)

    if daily_total > policy.max_daily_payer_total:
        alerts.append(
            _record_alert(
                policy=policy,
                transaction_record=transaction_record,
                event_key=f"daily:{business_date}:payer:{payer_hash}:daily_total",
                rule_code="daily_payer_total_limit",
                severity=RiskBotAlert.Severity.HIGH,
                message=(
                    f"Payer {payer_label} has paid {daily_total} {currency} "
                    f"on {business_date}, above the configured daily limit of "
                    f"{policy.max_daily_payer_total} {currency}."
                ),
                evidence={
                    "business_date": business_date.isoformat(),
                    "payer": payer_label,
                    "transaction_count": count,
                    "daily_total": str(daily_total),
                    "currency": currency,
                    "limit": str(policy.max_daily_payer_total),
                },
            )
        )
    if count > policy.max_daily_payer_transactions:
        alerts.append(
            _record_alert(
                policy=policy,
                transaction_record=transaction_record,
                event_key=f"daily:{business_date}:payer:{payer_hash}:frequency",
                rule_code="daily_payer_frequency_limit",
                severity=RiskBotAlert.Severity.MEDIUM,
                message=(
                    f"Payer {payer_label} has made {count} payments on "
                    f"{business_date}, above the configured limit of "
                    f"{policy.max_daily_payer_transactions}."
                ),
                evidence={
                    "business_date": business_date.isoformat(),
                    "payer": payer_label,
                    "transaction_count": count,
                    "limit": policy.max_daily_payer_transactions,
                },
            )
        )
    return alerts
