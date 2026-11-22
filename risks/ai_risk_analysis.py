import json
import logging

import anthropic

from django.conf import settings

from .models import Risk

logger = logging.getLogger(__name__)

MIN_RISKS = 1
MAX_RISKS = 7
PROMPT_MIN_RISKS = 3
MAX_MITIGATIONS = 5
RISK_TYPE_VALUES = {value for value, _ in Risk.RiskType.choices}


class AIRiskAnalysisError(Exception):
    pass


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise AIRiskAnalysisError(f"The AI response did not contain a valid {label}.")
    return value.strip()


def _optional_text(value, label, maximum):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > maximum:
        raise AIRiskAnalysisError(f"The AI response did not contain a valid {label}.")
    return value.strip()


def _rating(value, label):
    try:
        rating = int(value)
    except (TypeError, ValueError):
        raise AIRiskAnalysisError(f"The AI response did not contain a valid {label}.")
    if not 1 <= rating <= 5:
        raise AIRiskAnalysisError(f"The AI response did not contain a valid {label}.")
    return rating


def _mitigations(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MITIGATIONS:
        raise AIRiskAnalysisError("The AI response did not contain valid mitigation actions.")
    return [_text(item, "mitigation action", 300) for item in value]


def _validate_risk_analysis(value):
    if not isinstance(value, dict):
        raise AIRiskAnalysisError("The AI response was not a valid analysis.")

    risks = value.get("risks")
    if not isinstance(risks, list) or not MIN_RISKS <= len(risks) <= MAX_RISKS:
        raise AIRiskAnalysisError("The AI response did not contain a valid set of risks.")

    validated_risks = []
    for risk in risks:
        if not isinstance(risk, dict):
            raise AIRiskAnalysisError("The AI response contained an invalid risk.")
        risk_type = risk.get("risk_type")
        if risk_type not in RISK_TYPE_VALUES:
            raise AIRiskAnalysisError("The AI response contained an unrecognized risk type.")
        validated_risks.append(
            {
                "title": _text(risk.get("title"), "risk title", 160),
                "description": _text(risk.get("description"), "risk description", 1200),
                "risk_type": risk_type,
                "likelihood": _rating(risk.get("likelihood"), "likelihood rating"),
                "impact": _rating(risk.get("impact"), "impact rating"),
                "early_warning_indicator": _optional_text(
                    risk.get("early_warning_indicator"), "early warning indicator", 255
                ),
                "mitigations": _mitigations(risk.get("mitigations")),
            }
        )

    return {
        "summary": _text(value.get("summary"), "analysis summary", 900),
        "risks": validated_risks,
    }


def _build_prompt(business_context):
    return {
        "business": business_context,
        "instructions": (
            "You are helping a small or medium business owner in Kenya think through "
            "practical risks. Using only the business details supplied, return JSON with "
            "exactly these top-level keys: summary (a 1-3 sentence plain-language overview) "
            f"and risks (an array of {PROMPT_MIN_RISKS} to {MAX_RISKS} objects). Each risk object "
            "must have: title (concise risk statement, under 160 characters), description "
            "(explain the likely cause and the effect on money, customers, staff, or "
            "operations), risk_type (exactly one of: strategic, financial, operational, "
            "political, climate, cyber, compliance, third_party), likelihood (integer 1-5, "
            "1=rare, 5=almost certain), impact (integer 1-5, 1=minor, 5=severe), "
            "early_warning_indicator (a short observable warning sign, or an empty string "
            "if none is obvious), and mitigations (an array of 2 to 5 short, affordable, "
            "practical actions this specific business could take). Base ratings only on the "
            "details given; do not invent facts about this business, its finances, or its "
            "exact location's hazards, and do not claim knowledge of live weather, markets, "
            "or law. This is general advisory guidance, not a certified or professional risk "
            "assessment."
        ),
    }


def generate_business_risk_analysis(business_context):
    if not settings.AI_RISK_ANALYSIS_ENABLED:
        raise AIRiskAnalysisError("AI risk analysis is currently disabled.")
    if not settings.ANTHROPIC_API_KEY:
        raise AIRiskAnalysisError(
            "AI risk analysis is not configured for this deployment yet."
        )

    prompt = _build_prompt(business_context)
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=30)
    try:
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=3000,
            temperature=0.2,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
        )
    except anthropic.APIError as error:
        logger.warning("Claude API request failed: %s", error)
        raise AIRiskAnalysisError(
            "The AI service could not complete the request. Please try again later."
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
        logger.warning("Claude returned an incomplete risk analysis.")
        raise AIRiskAnalysisError(
            "The AI returned an incomplete analysis. Please try again."
        ) from error

    return _validate_risk_analysis(analysis)
