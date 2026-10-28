from datetime import timedelta
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone
from risks.models import Report, ReportSchedule
from risks.reporting import generate_report


class Command(BaseCommand):
    help = "Generate and email reports whose next run is due"

    def handle(self, *args, **options):
        now = timezone.now()
        generated = 0
        for schedule in ReportSchedule.objects.filter(active=True, next_run_at__lte=now).select_related("organization", "template"):
            report = Report.objects.create(
                organization=schedule.organization,
                template=schedule.template,
                title=f"{schedule.template.name} - {schedule.frequency.title()} Report",
                report_format=schedule.report_format,
            )
            generate_report(report)
            recipients = [address.strip() for address in schedule.recipients.split(",") if address.strip()]
            if recipients and report.file:
                email = EmailMessage(report.title, report.executive_summary, None, recipients)
                report.file.open("rb")
                email.attach(report.file.name.rsplit("/", 1)[-1], report.file.read(), "application/octet-stream")
                email.send(fail_silently=True)
            intervals = {"weekly": 7, "monthly": 30, "quarterly": 90, "annual": 365}
            schedule.last_generated_at = now
            schedule.next_run_at = now + timedelta(days=intervals[schedule.frequency])
            schedule.save(update_fields=["last_generated_at", "next_run_at"])
            generated += 1
        self.stdout.write(self.style.SUCCESS(f"Generated {generated} scheduled report(s)."))
