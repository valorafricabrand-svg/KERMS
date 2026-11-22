import json
import logging
import math
import anthropic
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)

DEMO_LOCATION = "Nyeri County, Kenya"
DEMO_COORDINATES = {"latitude": -0.42, "longitude": 36.95}
NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/climatology/point"
)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
MONTHS = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)

DEMO_BUSINESS = {
    "type": "fictional small mixed vegetable farm",
    "model": (
        "grows vegetables, buys seed and farm inputs, sells fresh produce "
        "to a local market and a few small retailers"
    ),
    "constraints": (
        "owner-managed, limited cash reserve, seasonal production, "
        "one main water source, and no confirmed backup supplier"
    ),
}


class AIOnboardingDemoError(Exception):
    pass


def _read_json(request, timeout, service_name):
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        logger.warning("%s returned HTTP %s.", service_name, error.code)
        raise AIOnboardingDemoError(
            f"{service_name} could not complete the request (HTTP {error.code})."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("%s request failed: %s", service_name, error)
        raise AIOnboardingDemoError(
            f"{service_name} could not be reached. Please try again later."
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("%s returned invalid JSON.", service_name)
        raise AIOnboardingDemoError(
            f"{service_name} returned an unreadable response."
        ) from error


def fetch_demo_climate_context():
    query = urlencode(
        {
            "parameters": "T2M,PRECTOTCORR",
            "community": "AG",
            "longitude": DEMO_COORDINATES["longitude"],
            "latitude": DEMO_COORDINATES["latitude"],
            "format": "JSON",
        }
    )
    request = Request(
        f"{NASA_POWER_URL}?{query}",
        headers={"User-Agent": "KERMS-AI-Onboarding-Demo/1.0"},
    )
    payload = _read_json(request, timeout=15, service_name="NASA POWER")

    try:
        parameters = payload["properties"]["parameter"]
        months = [
            {
                "month": month,
                "mean_temperature_c": float(parameters["T2M"][month]),
                "mean_daily_precipitation_mm": float(
                    parameters["PRECTOTCORR"][month]
                ),
            }
            for month in MONTHS
        ]
        elevation_m = float(payload["geometry"]["coordinates"][2])
        period = payload["header"]["range"]
    except (KeyError, TypeError, ValueError, IndexError) as error:
        logger.warning("NASA POWER returned an incomplete climate response.")
        raise AIOnboardingDemoError(
            "NASA POWER returned incomplete climate data."
        ) from error

    if any(
        not math.isfinite(value) or value == -999.0
        for month in months
        for value in (
            month["mean_temperature_c"],
            month["mean_daily_precipitation_mm"],
        )
    ):
        raise AIOnboardingDemoError(
            "NASA POWER did not provide usable climate data for the demo point."
        )

    return {
        "location": DEMO_LOCATION,
        "elevation_m": elevation_m,
        "period": period,
        "months": months,
        "source": "NASA POWER Climatology API",
    }


def _text(value, label, maximum=1600):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise AIOnboardingDemoError(
            f"The AI response did not contain a valid {label}."
        )
    return value.strip()


def _text_list(value, label, maximum_items=6):
    if (
        not isinstance(value, list)
        or not value
        or len(value) > maximum_items
    ):
        raise AIOnboardingDemoError(
            f"The AI response did not contain valid {label}."
        )
    return [_text(item, label, maximum=500) for item in value]


def _validate_analysis(value):
    if not isinstance(value, dict):
        raise AIOnboardingDemoError("The AI response was not a valid analysis.")

    scenarios = value.get("scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 5:
        raise AIOnboardingDemoError(
            "The AI response did not contain a valid set of scenarios."
        )

    validated_scenarios = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise AIOnboardingDemoError(
                "The AI response contained an invalid scenario."
            )
        validated_scenarios.append(
            {
                "title": _text(scenario.get("title"), "scenario title", 180),
                "business_impact": _text(
                    scenario.get("business_impact"), "scenario impact"
                ),
                "early_warning_signs": _text_list(
                    scenario.get("early_warning_signs"), "warning signs"
                ),
                "risk_reduction_actions": _text_list(
                    scenario.get("risk_reduction_actions"), "risk-reduction actions"
                ),
                "response_actions": _text_list(
                    scenario.get("response_actions"), "response actions"
                ),
            }
        )

    return {
        "business_model_summary": _text(
            value.get("business_model_summary"), "business model summary"
        ),
        "geographic_context": _text(
            value.get("geographic_context"), "geographic context"
        ),
        "scenarios": validated_scenarios,
        "priority_actions": _text_list(
            value.get("priority_actions"), "priority actions"
        ),
        "uncertainties": _text_list(
            value.get("uncertainties"), "uncertainties"
        ),
    }


def _build_analysis_prompt(climate_context):
    return {
        "fictional_business": DEMO_BUSINESS,
        "location": DEMO_LOCATION,
        "historical_climate_context": climate_context,
        "instructions": (
            "Prepare practical, plain-language onboarding guidance for this "
            "fictional Kenyan micro-enterprise. Return JSON with exactly these "
            "top-level keys: business_model_summary (string), geographic_context "
            "(string), scenarios (array of 3 to 5 objects), priority_actions "
            "(array of 3 to 6 strings), uncertainties (array of 1 to 6 strings). "
            "Each scenario object must have title, business_impact, "
            "early_warning_signs (array), risk_reduction_actions (array), and "
            "response_actions (array). Use only the supplied climate data for "
            "climate-related observations. Do not claim to know local flood "
            "zones, live weather, market prices, laws, or probabilities. Do not "
            "invent facts about the fictional business. Distinguish planning "
            "scenarios from forecasts. Make mitigations affordable and actionable "
            "for a small business. This is advisory, not a formal risk rating or "
            "professional advice."
        ),
    }


def _generate_claude_analysis(prompt):
    if not settings.ANTHROPIC_API_KEY:
        raise AIOnboardingDemoError(
            "Set ANTHROPIC_API_KEY in your local .env file to try the AI demo."
        )

    client = anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=30,
    )
    try:
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=3000,
            temperature=0.2,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
        )
    except anthropic.APIError as error:
        logger.warning("Claude API request failed: %s", error)
        raise AIOnboardingDemoError(
            "Claude API could not complete the request. Please try again later."
        ) from error

    try:
        generated_text = next(
            block.text for block in response.content if block.type == "text"
        )
        analysis = json.loads(generated_text)
    except (
        AttributeError,
        IndexError,
        StopIteration,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning("Claude returned an incomplete demo analysis.")
        raise AIOnboardingDemoError(
            "Claude returned an incomplete analysis. Please try again."
        ) from error

    return _validate_analysis(analysis)


def generate_demo_analysis(climate_context):
    prompt = _build_analysis_prompt(climate_context)
    if settings.AI_PROVIDER == "claude":
        return _generate_claude_analysis(prompt)
    if settings.AI_PROVIDER != "gemini":
        raise AIOnboardingDemoError(
            "Unsupported AI provider configured for the demo."
        )
    if not settings.GEMINI_API_KEY:
        raise AIOnboardingDemoError(
            "Set GEMINI_API_KEY in your local .env file to try the AI demo."
        )

    model = quote(settings.GEMINI_MODEL, safe="-.")
    request = Request(
        f"{GEMINI_API_URL}{model}:generateContent",
        data=json.dumps(
            {
                "contents": [{"parts": [{"text": json.dumps(prompt)}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2,
                    "maxOutputTokens": 3000,
                },
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY,
        },
        method="POST",
    )
    payload = _read_json(request, timeout=30, service_name="Gemini API")

    try:
        generated_text = payload["candidates"][0]["content"]["parts"][0]["text"]
        analysis = json.loads(generated_text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        logger.warning("Gemini returned an incomplete demo analysis.")
        raise AIOnboardingDemoError(
            "Gemini returned an incomplete analysis. Please try again."
        ) from error

    return _validate_analysis(analysis)
