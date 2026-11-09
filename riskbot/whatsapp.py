import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from riskbot.config import Settings

logger = logging.getLogger(__name__)


class WhatsAppDeliveryError(RuntimeError):
    pass


def _post(url: str, headers: dict[str, str], body: bytes, timeout: int) -> None:
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
            if not 200 <= response.status < 300:
                raise WhatsAppDeliveryError(
                    f"WhatsApp provider returned HTTP {response.status}"
                )
    except HTTPError as exc:
        raise WhatsAppDeliveryError(
            f"WhatsApp provider returned HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise WhatsAppDeliveryError(
            f"Could not reach WhatsApp provider: {exc.reason}"
        ) from exc


def send_message(settings: Settings, message: str) -> None:
    if not settings.owner_phone:
        raise WhatsAppDeliveryError("OWNER_WHATSAPP_NUMBER is not configured")

    if settings.whatsapp_provider == "ultramsg":
        if not settings.ultramsg_instance_id or not settings.ultramsg_token:
            raise WhatsAppDeliveryError(
                "ULTRAMSG_INSTANCE_ID and ULTRAMSG_TOKEN are required"
            )
        url = (
            "https://api.ultramsg.com/"
            f"{settings.ultramsg_instance_id}/messages/chat"
        )
        body = urlencode(
            {
                "token": settings.ultramsg_token,
                "to": settings.owner_phone,
                "body": message,
            }
        ).encode()
        _post(
            url,
            {"Content-Type": "application/x-www-form-urlencoded"},
            body,
            settings.request_timeout_seconds,
        )
        return

    if settings.whatsapp_provider == "wati":
        if not settings.wati_base_url or not settings.wati_api_token:
            raise WhatsAppDeliveryError(
                "WATI_BASE_URL and WATI_API_TOKEN are required"
            )
        url = (
            f"{settings.wati_base_url}/api/v1/sendSessionMessage/"
            f"{settings.owner_phone}"
        )
        body = json.dumps({"messageText": message}).encode()
        _post(
            url,
            {
                "Authorization": f"Bearer {settings.wati_api_token}",
                "Content-Type": "application/json",
            },
            body,
            settings.request_timeout_seconds,
        )
        return

    logger.error("WhatsApp delivery is not configured")
    raise WhatsAppDeliveryError(
        "Set WHATSAPP_PROVIDER to ultramsg or wati before running alerts"
    )
