from django.core.management.base import BaseCommand
from risks.models import Organization, ComplianceFramework, FrameworkRequirement, GovernanceCommittee, GovernancePolicy


class Command(BaseCommand):
    help = "Seed representative governance frameworks, requirements, committees, and policies for demo organizations."

    def handle(self, *args, **options):
        created = 0
        for organization in Organization.objects.all():
            framework, made = ComplianceFramework.objects.get_or_create(
                organization=organization, code="ISO27001", version="2022",
                defaults={"name": "Information Security Management System", "regulator": "ISO", "description": "Representative information-security governance framework."},
            )
            created += made
            requirements = [
                ("A.5", "Information security policies", FrameworkRequirement.Status.IMPLEMENTED),
                ("A.8", "Asset management", FrameworkRequirement.Status.IN_PROGRESS),
                ("A.12", "Operational security", FrameworkRequirement.Status.EVIDENCE_REVIEW),
                ("A.16", "Incident management", FrameworkRequirement.Status.GAP),
            ]
            for reference, title, status in requirements:
                _, made = FrameworkRequirement.objects.get_or_create(
                    framework=framework, reference=reference,
                    defaults={"title": title, "status": status},
                )
                created += made
            _, made = GovernanceCommittee.objects.get_or_create(
                organization=organization, name="Enterprise Risk Committee",
                defaults={"purpose": "Review enterprise risk exposure, appetite, incidents, and assurance.", "meeting_frequency": "Quarterly",},
            )
            created += made
            _, made = GovernancePolicy.objects.get_or_create(
                organization=organization, reference="GOV-001",
                defaults={"title": "Enterprise Risk Management Policy", "status": GovernancePolicy.Status.APPROVED},
            )
            created += made
        self.stdout.write(self.style.SUCCESS(f"Governance demonstration data seeded; {created} records created or confirmed."))
