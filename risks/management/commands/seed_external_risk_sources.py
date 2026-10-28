from django.core.management.base import BaseCommand
from risks.models import ExternalRiskSource


SOURCES = [
    ("GDACS Global Disaster Alerts", "climate", "https://www.gdacs.org/xml/rss.xml", True),
    ("CISA Cybersecurity Advisories", "cyber", "https://www.cisa.gov/cybersecurity-advisories/rss.xml", True),
]


class Command(BaseCommand):
    help = "Seed approved open external risk intelligence sources"

    def handle(self, *args, **options):
        for name, category, url, verified in SOURCES:
            ExternalRiskSource.objects.update_or_create(feed_url=url, defaults={"name": name, "category": category, "provider_type": "rss", "active": True, "verified_source": verified})
        self.stdout.write(self.style.SUCCESS("External intelligence sources loaded."))
