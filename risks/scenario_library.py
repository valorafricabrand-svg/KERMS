from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioTemplate:
    key: str
    name: str
    scenario_type: str
    audience: str
    description: str
    assumptions: str


SCENARIO_TEMPLATES = (
    ScenarioTemplate(
        key="dry-season",
        name="Extended dry spell or water shortage",
        scenario_type="climate",
        audience="Farms and food businesses",
        description=(
            "Explore how an extended dry spell could affect water access, crop or "
            "livestock output, operating costs, and delivery commitments."
        ),
        assumptions=(
            "Choose a locally relevant duration and affected locations. Consider "
            "water storage, irrigation, feed, insurance, and alternative income."
        ),
    ),
    ScenarioTemplate(
        key="flood-disruption",
        name="Flooding disrupts production or access",
        scenario_type="flooding",
        audience="Farms and location-dependent businesses",
        description=(
            "Consider a flood affecting fields, stock, premises, roads, or access "
            "to customers and suppliers."
        ),
        assumptions=(
            "Select exposed locations and a locally plausible duration. Include "
            "business interruption and recovery costs without assuming a forecast."
        ),
    ),
    ScenarioTemplate(
        key="crop-or-livestock-health",
        name="Crop pest or livestock health event",
        scenario_type="climate",
        audience="Farms and agricultural value chains",
        description=(
            "Consider a localized crop pest, crop disease, or livestock health "
            "event that reduces output or delays sales."
        ),
        assumptions=(
            "Identify affected products, prevention measures, veterinary or "
            "extension support, and the time needed to restore production."
        ),
    ),
    ScenarioTemplate(
        key="input-or-market-shock",
        name="Farm input or selling-price shock",
        scenario_type="market",
        audience="Farms and small enterprises",
        description=(
            "Test the effect of a sharp change in input costs or the price received "
            "for a major product."
        ),
        assumptions=(
            "Use your own purchase costs, selling prices, inventory, and cash "
            "buffer. Do not treat this scenario as a market-price prediction."
        ),
    ),
    ScenarioTemplate(
        key="mobile-money-outage",
        name="Mobile money or network outage",
        scenario_type="payment",
        audience="All enterprises",
        description=(
            "Consider losing access to mobile payments or mobile connectivity "
            "during a busy trading or collection period."
        ),
        assumptions=(
            "Set a disruption duration and estimate delayed transactions, "
            "alternative payment costs, reconciliation effort, and customer impact."
        ),
    ),
    ScenarioTemplate(
        key="key-person-change",
        name="Key-person departure or management handover",
        scenario_type="people",
        audience="All enterprises",
        description=(
            "Explore disruption if an owner, manager, or specialist leaves or "
            "changes role before knowledge and approvals are handed over."
        ),
        assumptions=(
            "Consider access to accounts and records, delegated approvals, "
            "customer and supplier relationships, and continuity cover."
        ),
    ),
    ScenarioTemplate(
        key="supplier-interruption",
        name="Critical supplier interruption",
        scenario_type="supplier",
        audience="All enterprises",
        description=(
            "Test a delay or failure affecting a key supplier, input, transporter, "
            "or service provider."
        ),
        assumptions=(
            "Select the suppliers and assets that matter to your operations. "
            "Estimate substitution time, extra costs, and customer delays."
        ),
    ),
    ScenarioTemplate(
        key="power-or-fuel-disruption",
        name="Power or fuel disruption",
        scenario_type="custom",
        audience="All enterprises",
        description=(
            "Consider a prolonged power or fuel interruption affecting production, "
            "cold storage, transport, communications, or service delivery."
        ),
        assumptions=(
            "Set a duration that fits your location and operating model. Consider "
            "backup capacity, spoilage, fuel costs, and restoration time."
        ),
    ),
    ScenarioTemplate(
        key="records-or-fraud-event",
        name="Business records loss or digital fraud",
        scenario_type="cyber",
        audience="All enterprises",
        description=(
            "Explore the impact of unavailable business records, account takeover, "
            "or payment fraud."
        ),
        assumptions=(
            "Consider recovery from backups, account access, reporting duties, "
            "customer trust, and the time needed to verify transactions."
        ),
    ),
)


def get_scenario_template(key: str | None) -> ScenarioTemplate | None:
    if key is None:
        return None
    return next((template for template in SCENARIO_TEMPLATES if template.key == key), None)
