from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from risks.models import Organization, ExternalRiskSource, ExternalRiskAlert


class Command(BaseCommand):
    help = "Create clearly labeled demonstration external intelligence alerts"

    def handle(self, *args, **options):
        source, _ = ExternalRiskSource.objects.get_or_create(
            name="Demonstration Intelligence Scenario", feed_url="https://example.com/demo-intelligence", defaults={
                "category": "other", "provider_type": "demo", "active": False, "verified_source": False
            }
        )
        for organization in Organization.objects.all():
            alerts = [
                ("DEMO-CLIMATE-1", "Severe rainfall scenario affecting Manila operations", "Demonstration only: scenario indicates heavy rainfall could disrupt facilities and continuity controls.", "climate", "high", "Philippines", 75),
                ("DEMO-POLITICAL-1", "Election disruption scenario affecting Lagos operations", "Demonstration only: a regional election escalation could interrupt branch operations and third-party services.", "geopolitical", "medium", "Nigeria", 70),
                ("DEMO-CYBER-1", "Critical ransomware signal affecting customer systems", "Demonstration only: ransomware activity may increase cyber and continuity exposure across customer-facing systems.", "cyber", "critical", "United Kingdom", 80),
            ]
            for external_id, title, summary, category, severity, country, confidence in alerts:
                alert, created = ExternalRiskAlert.objects.update_or_create(
                    organization=organization, source=source, external_id=external_id,
                    defaults={"title": title, "summary": summary, "category": category,
                              "severity": severity, "country": country, "confidence": confidence,
                              "source_url": "https://example.com/demo-intelligence",
                              "source_published_at": timezone.now() - timedelta(days=1)}
                )
                for location in organization.locations.filter(country=country):
                    alert.locations.add(location)
                for risk in organization.risks.filter(location__country=country):
                    alert.risks.add(risk)
                for asset in organization.assets.filter(location__country=country):
                    alert.assets.add(asset)
                for portfolio in organization.portfolios.filter(assets__location__country=country):
                    alert.portfolios.add(portfolio)
        self.stdout.write(self.style.SUCCESS("Demonstration external alerts loaded."))
