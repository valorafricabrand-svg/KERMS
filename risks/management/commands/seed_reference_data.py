from django.core.management.base import BaseCommand

from risks.models import RiskCategory, RiskTheme


CATEGORIES = [
    ("AIA", "AI & Analytics"),
    ("AUD", "Audit"),
    ("BCP", "Business Continuity"),
    ("CLM", "Claims"),
    ("CMP", "Compliance"),
    ("CRD", "Credit"),
    ("CYB", "Cybersecurity"),
    ("DPR", "Data Protection"),
    ("DRP", "Disaster Recovery"),
    ("ESG", "ESG & Climate"),
    ("EMG", "Emerging"),
    ("FIN", "Financial"),
    ("FRP", "Financial Reporting"),
    ("FRD", "Fraud"),
    ("GOV", "Governance"),
    ("OHS", "Health & Safety"),
    ("HRM", "Human Resource"),
    ("ICT", "ICT"),
    ("ISC", "Information Security"),
    ("LEG", "Legal"),
    ("LIQ", "Liquidity"),
    ("MKT", "Market"),
    ("MNE", "Monitoring & Evaluation"),
    ("OPS", "Operational"),
    ("PRF", "Performance"),
    ("PHS", "Physical Security"),
    ("PRT", "Portfolio"),
    ("PRC", "Procurement"),
    ("PRJ", "Project"),
    ("REC", "Recoveries"),
    ("REP", "Reputation"),
    ("STK", "Stakeholder"),
    ("STR", "Strategic"),
    ("TPR", "Third-Party"),
]

THEMES = [
    "Claims Management",
    "Financial Sustainability",
    "Governance & Compliance",
    "Institutional Transition",
    "Operational Resilience",
    "Portfolio Quality",
]


class Command(BaseCommand):
    help = "Load the official CGS risk categories and themes."

    def handle(self, *args, **options):
        for position, (code, name) in enumerate(CATEGORIES, start=1):
            RiskCategory.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "display_order": position * 10,
                    "is_active": True,
                },
            )

        for name in THEMES:
            RiskTheme.objects.get_or_create(name=name)

        self.stdout.write(
            self.style.SUCCESS(
                f"Reference data loaded: {len(CATEGORIES)} categories "
                f"and {len(THEMES)} themes."
            )
        )