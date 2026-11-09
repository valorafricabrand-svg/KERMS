from .models import BusinessProfile


SITE_RISK_PROMPTS = {
    BusinessProfile.Sector.AGRICULTURE: (
        "Water availability, dry spells, and heavy rainfall",
        "Pests, animal health, and crop or livestock disease",
        "Seed, feed, fertiliser, and other input availability",
        "Harvest storage, spoilage, and access to markets",
    ),
    BusinessProfile.Sector.RETAIL: (
        "Customer access, stock security, and damage to premises",
        "Supplier delays, stock shortages, and changing input prices",
        "Power, mobile-money, or connectivity interruption",
        "Cash handling, theft, and payment reconciliation",
    ),
    BusinessProfile.Sector.FOOD: (
        "Safe water, hygiene, and food contamination",
        "Power, refrigeration, and perishable stock spoilage",
        "Supplier interruption and changing food input prices",
        "Fire, customer safety, and weather-related access disruption",
    ),
    BusinessProfile.Sector.TRANSPORT: (
        "Road closures, weather disruption, and route alternatives",
        "Fuel availability and price changes",
        "Vehicle condition, accident prevention, and driver safety",
        "Mobile connectivity, dispatch, and payment interruption",
    ),
    BusinessProfile.Sector.MANUFACTURING: (
        "Electricity, water, and essential production inputs",
        "Equipment breakdown, maintenance, and fire prevention",
        "Worker health and safety, product quality, and waste",
        "Supplier delays and inability to deliver customer orders",
    ),
    BusinessProfile.Sector.CONSTRUCTION: (
        "Weather delays, site drainage, and safe work conditions",
        "Material prices, shortages, and supplier reliability",
        "Equipment security, breakdown, and worker safety",
        "Customer payment delays and project cash-flow gaps",
    ),
    BusinessProfile.Sector.PROFESSIONAL: (
        "Reliance on a few customers or one key employee",
        "Client records, confidentiality, and device or account security",
        "Internet, power, and ability to continue serving clients",
        "Contracts, professional obligations, and delayed payments",
    ),
    BusinessProfile.Sector.HEALTH: (
        "Medicine and critical supply availability",
        "Safe water, power, refrigeration, and continuity of care",
        "Patient safety, infection prevention, and staff availability",
        "Sensitive records, device security, and system outages",
    ),
    BusinessProfile.Sector.EDUCATION: (
        "Learner and staff safety, site access, and safeguarding",
        "Power, internet, and continuity of teaching",
        "Staff availability and dependence on key individuals",
        "Fees, operating cash, and essential learning materials",
    ),
    BusinessProfile.Sector.DIGITAL: (
        "Internet, cloud, and critical service-provider outages",
        "Cybersecurity, account access, and recovery of business data",
        "Payment-provider interruption and customer support",
        "Customer concentration, supplier dependence, and cash runway",
    ),
    BusinessProfile.Sector.FINANCE: (
        "Fraud, cyber incidents, and protection of customer information",
        "Cash flow, credit exposure, and currency or market movements",
        "Payment-provider, power, and connectivity interruption",
        "Customer identification, record keeping, and changing obligations",
    ),
    BusinessProfile.Sector.OTHER: (
        "People, customer demand, suppliers, and cash flow",
        "Premises, equipment, utilities, and access to the site",
        "Safety, permits, records, payments, and disruption recovery",
    ),
}


def site_risk_prompts(profile):
    if not profile:
        return (
            "People, customer demand, suppliers, and cash flow",
            "Premises, equipment, utilities, and access to the site",
            "Safety, permits, records, payments, and disruption recovery",
        )
    return SITE_RISK_PROMPTS.get(
        profile.sector, SITE_RISK_PROMPTS[BusinessProfile.Sector.OTHER]
    )
