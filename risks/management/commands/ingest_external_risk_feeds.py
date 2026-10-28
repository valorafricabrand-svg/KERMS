from datetime import datetime, timezone as dt_timezone
import feedparser
from django.core.management.base import BaseCommand
from django.utils import timezone
from risks.models import Organization, ExternalRiskSource, ExternalRiskAlert, Location, Asset, Portfolio, Risk


class Command(BaseCommand):
    help = "Ingest alerts from configured verified RSS or JSON intelligence sources"

    def handle(self, *args, **options):
        organizations = Organization.objects.all()
        created_total = 0
        for source in ExternalRiskSource.objects.filter(active=True):
            try:
                parsed = feedparser.parse(source.feed_url)
                if parsed.bozo and not getattr(parsed, "entries", None):
                    raise ValueError(str(getattr(parsed, "bozo_exception", "Invalid feed")))
                for organization in organizations:
                    if source.organization_id and source.organization_id != organization.id:
                        continue
                    for entry in parsed.entries[:100]:
                        external_id = getattr(entry, "id", None) or getattr(entry, "link", None) or getattr(entry, "title", "")
                        if not external_id:
                            continue
                        title = getattr(entry, "title", "Untitled intelligence alert")[:255]
                        summary = getattr(entry, "summary", getattr(entry, "description", ""))[:4000]
                        source_url = getattr(entry, "link", "")[:500]
                        published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                        published_at = None
                        if published:
                            published_at = datetime(*published[:6], tzinfo=dt_timezone.utc)
                        text = f"{title} {summary}".lower()
                        country_matches = []
                        severity = "low"
                        if any(word in text for word in ("red", "critical", "catastrophic", "severe", "extreme", "exploited", "ransomware")):
                            severity = "critical" if "critical" in text or "extreme" in text else "high"
                        elif any(word in text for word in ("orange", "warning", "high", "election", "sanction")):
                            severity = "medium"
                        alert, created = ExternalRiskAlert.objects.get_or_create(
                            organization=organization, source=source, external_id=str(external_id)[:255],
                            defaults={"title": title, "summary": summary, "category": source.category,
                                      "severity": severity, "source_url": source_url,
                                      "source_published_at": published_at, "confidence": 85 if source.verified_source else 60}
                        )
                        if created:
                            created_total += 1
                            for location in Location.objects.filter(organization=organization):
                                if location.country.lower() in text:
                                    alert.locations.add(location)
                                    country_matches.append(location.country)
                            if country_matches:
                                alert.country = sorted(set(country_matches))[0]
                                alert.save(update_fields=["country"])
                            for risk in Risk.objects.filter(organization=organization):
                                if risk.location and risk.location in alert.locations.all():
                                    alert.risks.add(risk)
                                elif risk.risk_type == source.category and risk.title.lower().split()[:1] and any(word in text for word in risk.title.lower().split() if len(word) > 4):
                                    alert.risks.add(risk)
                            for asset in Asset.objects.filter(organization=organization):
                                if asset.location and asset.location in alert.locations.all():
                                    alert.assets.add(asset)
                            for portfolio in Portfolio.objects.filter(organization=organization):
                                if portfolio.assets.filter(location__in=alert.locations.all()).exists():
                                    alert.portfolios.add(portfolio)
                source.last_checked_at = timezone.now(); source.last_error = ""
            except Exception as exc:
                source.last_error = str(exc)
            source.save(update_fields=["last_checked_at", "last_error"])
        self.stdout.write(self.style.SUCCESS(f"Ingested {created_total} new external alert(s)."))
