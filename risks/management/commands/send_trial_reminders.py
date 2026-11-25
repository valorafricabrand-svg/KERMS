import logging
import math
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from risks.models import (
    BillingConfiguration,
    OrganizationMembership,
    OrganizationSubscription,
)

logger = logging.getLogger(__name__)

STAGE_ORDER = {"": 0, "7d": 1, "1d": 2, "expired": 3}
# Trials that ended before this window are not emailed, so the first run does
# not notify workspaces that expired long ago.
EXPIRED_NOTICE_WINDOW = timedelta(days=3)
SUBJECTS = {
    "7d": "Your KERMS free trial ends in {days} days",
    "1d": "Your KERMS free trial ends tomorrow",
    "expired": "Your KERMS free trial has ended",
}


def due_stage(subscription, now):
    remaining = subscription.trial_ends_at - now
    if remaining <= timedelta(0):
        return "expired" if remaining > -EXPIRED_NOTICE_WINDOW else None
    if remaining <= timedelta(days=1):
        return "1d"
    if remaining <= timedelta(days=7):
        return "7d"
    return None


class Command(BaseCommand):
    help = "Email workspace administrators before and when their free trial ends. Run daily."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the reminders that would be sent without sending them.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        trial = timedelta(days=OrganizationSubscription.TRIAL_DAYS)
        subscriptions = OrganizationSubscription.objects.filter(
            status=OrganizationSubscription.Status.ONBOARDING_DUE,
            onboarding_fee_paid_at__isnull=True,
            onboarding_fee_waived_at__isnull=True,
            created_at__lte=now - trial + timedelta(days=7),
            created_at__gt=now - trial - EXPIRED_NOTICE_WINDOW,
        ).select_related("organization")
        config = BillingConfiguration.objects.filter(pk=1).first()
        onboarding_fee = config.onboarding_fee if config else Decimal("500.00")
        base_url = settings.PUBLIC_BASE_URL or "http://localhost:8000"

        sent = 0
        for subscription in subscriptions:
            stage = due_stage(subscription, now)
            if not stage or STAGE_ORDER[stage] <= STAGE_ORDER[subscription.last_trial_reminder]:
                continue
            organization = subscription.organization
            recipients = sorted(
                {
                    membership.user.email
                    for membership in OrganizationMembership.objects.filter(
                        organization=organization,
                        role__in=[
                            OrganizationMembership.Role.ADMIN,
                            OrganizationMembership.Role.RISK_MANAGER,
                        ],
                        user__is_active=True,
                    ).select_related("user")
                    if membership.user.email
                }
            )
            if not recipients:
                continue

            days_left = max(math.ceil((subscription.trial_ends_at - now) / timedelta(days=1)), 0)
            subject = SUBJECTS[stage].format(days=days_left)
            if options["dry_run"]:
                self.stdout.write(f"[dry run] {organization.name}: {subject} -> {', '.join(recipients)}")
                continue

            body = render_to_string(
                "emails/trial_reminder.txt",
                {
                    "stage": stage,
                    "organization": organization,
                    "days_left": days_left,
                    "trial_ends_at": subscription.trial_ends_at,
                    "onboarding_fee": onboarding_fee,
                    "billing_url": f"{base_url}{reverse('billing')}?organization={organization.pk}",
                },
            )
            messages = [EmailMessage(subject, body, None, [address]) for address in recipients]
            try:
                get_connection().send_messages(messages)
            except Exception:
                logger.exception("Could not send %s trial reminder for organization %s.", stage, organization.pk)
                continue
            subscription.last_trial_reminder = stage
            subscription.save(update_fields=["last_trial_reminder", "updated_at"])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent trial reminders for {sent} workspace(s)."))
