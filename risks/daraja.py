import base64
import json
import logging
from datetime import datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.conf import settings


logger = logging.getLogger(__name__)


class DarajaError(Exception):
    pass


def _api_base():
    if settings.DARAJA_ENVIRONMENT == "sandbox":
        return "https://sandbox.safaricom.co.ke"
    if settings.DARAJA_ENVIRONMENT == "production":
        return "https://api.safaricom.co.ke"
    raise DarajaError("DARAJA_ENVIRONMENT must be sandbox or production.")


def _credentials_ready():
    required = (
        settings.DARAJA_CONSUMER_KEY,
        settings.DARAJA_CONSUMER_SECRET,
        settings.DARAJA_SHORTCODE,
        settings.DARAJA_PASSKEY,
        settings.DARAJA_CALLBACK_URL,
    )
    return all(required)


def _request(path, payload=None):
    if not _credentials_ready():
        raise DarajaError("Safaricom Daraja credentials and callback URL are not configured.")
    if settings.DARAJA_ENVIRONMENT == "production" and not settings.DARAJA_CALLBACK_URL.startswith("https://"):
        raise DarajaError("The live Daraja callback URL must use HTTPS.")
    token_request = Request(
        f"{_api_base()}/oauth/v1/generate?grant_type=client_credentials",
        headers={
            "Authorization": "Basic "
            + base64.b64encode(
                f"{settings.DARAJA_CONSUMER_KEY}:{settings.DARAJA_CONSUMER_SECRET}".encode()
            ).decode(),
        },
    )
    try:
        with urlopen(token_request, timeout=15) as response:
            token_payload = json.loads(response.read())
        if not isinstance(token_payload, dict):
            raise DarajaError("Daraja returned an invalid token response.")
        access_token = token_payload.get("access_token")
        if not access_token:
            raise DarajaError("Daraja did not return an access token.")
        api_request = Request(
            f"{_api_base()}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST" if payload is not None else "GET",
        )
        with urlopen(api_request, timeout=20) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise DarajaError("Daraja returned an invalid API response.")
        return result
    except HTTPError as exc:
        logger.error("Daraja request returned HTTP %s.", exc.code)
        raise DarajaError(f"Daraja returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        logger.error("Daraja request could not be completed: %s", exc)
        raise DarajaError("Could not reach Safaricom Daraja. Please try again.") from exc
    except json.JSONDecodeError as exc:
        logger.error("Daraja returned a non-JSON response.")
        raise DarajaError("Safaricom Daraja returned an unreadable response.") from exc


def normalize_phone_number(value):
    digits = "".join(character for character in value if character.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        digits = "254" + digits
    if (
        len(digits) != 12
        or not digits.startswith("254")
        or digits[3] not in {"1", "7"}
    ):
        raise DarajaError("Enter a valid Kenyan mobile number, such as 0712345678.")
    return digits


def _password_and_timestamp():
    timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    raw_password = (
        f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}"
    )
    password = base64.b64encode(raw_password.encode()).decode()
    return password, timestamp


def initiate_stk_push(payment, account_reference):
    amount = Decimal(payment.amount)
    if amount != amount.to_integral_value():
        raise DarajaError("Daraja payments must be a whole number of Kenyan shillings.")
    password, timestamp = _password_and_timestamp()
    response = _request(
        "/mpesa/stkpush/v1/processrequest",
        {
            "BusinessShortCode": settings.DARAJA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": settings.DARAJA_TRANSACTION_TYPE,
            "Amount": int(amount),
            "PartyA": payment.phone_number,
            "PartyB": settings.DARAJA_SHORTCODE,
            "PhoneNumber": payment.phone_number,
            "CallBackURL": settings.DARAJA_CALLBACK_URL,
            "AccountReference": account_reference[:12],
            "TransactionDesc": "KERMS business risk management",
        },
    )
    if str(response.get("ResponseCode")) != "0":
        raise DarajaError(response.get("errorMessage") or response.get("ResponseDescription") or "Daraja rejected the payment request.")
    if not response.get("CheckoutRequestID"):
        raise DarajaError("Daraja accepted the request without a checkout reference.")
    return response


def query_stk_push(checkout_request_id):
    password, timestamp = _password_and_timestamp()
    return _request(
        "/mpesa/stkpushquery/v1/query",
        {
            "BusinessShortCode": settings.DARAJA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        },
    )
