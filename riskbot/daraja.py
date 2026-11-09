from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo


class CallbackError(ValueError):
    pass


def _first_value(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = payload.get(name)
        if value is not None and value != "":
            return value
    return None


def _stk_fields(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get("Body")
    if not isinstance(body, dict):
        return {}
    callback = body.get("stkCallback")
    if not isinstance(callback, dict):
        return {}
    metadata = callback.get("CallbackMetadata", {})
    items = metadata.get("Item", []) if isinstance(metadata, dict) else []
    fields: dict[str, Any] = {}
    for item in items:
        if isinstance(item, dict) and item.get("Name"):
            fields[item["Name"]] = item.get("Value")
    return {
        "TransID": fields.get("MpesaReceiptNumber"),
        "TransAmount": fields.get("Amount"),
        "TransTime": fields.get("TransactionDate"),
        "MSISDN": fields.get("PhoneNumber"),
        "BillRefNumber": fields.get("AccountReference"),
    }


def _parse_time(value: Any, timezone: str) -> datetime:
    if value is None:
        raise CallbackError("Missing transaction timestamp")
    text = str(value)
    try:
        if len(text) == 14 and text.isdigit():
            parsed = datetime.strptime(text, "%Y%m%d%H%M%S")
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CallbackError("Invalid transaction timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed


def normalize_phone(value: Any) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits or None


def parse_confirmation(
    payload: dict[str, Any], timezone: str
) -> dict[str, Any]:
    body = payload.get("Body")
    stk_callback = body.get("stkCallback") if isinstance(body, dict) else None
    if (
        isinstance(stk_callback, dict)
        and stk_callback.get("ResultCode") is not None
        and str(stk_callback["ResultCode"]) != "0"
    ):
        raise CallbackError("STK transaction did not complete successfully")

    fields = _stk_fields(payload)
    source = {**fields, **payload}
    receipt = _first_value(source, "TransID", "MpesaReceiptNumber", "transId")
    amount = _first_value(source, "TransAmount", "Amount", "transAmount")
    timestamp = _first_value(source, "TransTime", "TransactionDate", "transTime")
    if not receipt:
        raise CallbackError("Missing transaction receipt")
    receipt = str(receipt).strip()
    if not receipt:
        raise CallbackError("Missing transaction receipt")
    if amount is None:
        raise CallbackError("Missing transaction amount")
    try:
        parsed_amount = Decimal(str(amount))
    except InvalidOperation as exc:
        raise CallbackError("Invalid transaction amount") from exc
    if not parsed_amount.is_finite() or parsed_amount <= 0:
        raise CallbackError("Transaction amount must be positive")
    try:
        amount_minor = int(
            (parsed_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    except (InvalidOperation, OverflowError) as exc:
        raise CallbackError("Transaction amount is outside the supported range") from exc
    if amount_minor <= 0:
        raise CallbackError("Transaction amount is below the supported precision")
    if amount_minor > 9_223_372_036_854_775_807:
        raise CallbackError("Transaction amount is outside the supported range")

    return {
        "receipt_number": receipt,
        "amount_minor": amount_minor,
        "payer_phone": normalize_phone(
            _first_value(source, "MSISDN", "PhoneNumber", "msisdn")
        ),
        "transaction_time": _parse_time(timestamp, timezone),
        "business_shortcode": _first_value(
            source, "BusinessShortCode", "businessShortCode"
        ),
        "account_reference": _first_value(
            source, "BillRefNumber", "AccountReference", "accountReference"
        ),
    }
