from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import (
    Location,
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
    Risk,
    SubscriptionPlan,
)


class BillingAccessMiddleware:
    exempt_paths = (
        "/admin/",
        "/billing/",
        "/login/",
        "/logout/",
        "/payments/daraja/callback/",
    )
    feature_paths = (
        ("/business-profile/", "business_profile"),
        ("/locations/", "locations"),
        ("/assessments/", "assessments"),
        ("/risks/", "risk_register"),
        ("/incidents/", "incidents"),
        ("/reports/", "reports"),
        ("/assets/", "assets"),
        ("/scenarios/", "scenarios"),
        ("/management/", "management"),
        ("/assurance/", "assurance"),
        ("/governance/", "governance"),
        ("/intelligence/", "intelligence"),
        ("/integrations/", "integrations"),
        ("/risk-bot/", "risk_bot"),
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.exempt_paths) or not request.user.is_authenticated:
            return self.get_response(request)

        organizations = Organization.objects.all()
        if not request.user.is_superuser:
            organizations = organizations.filter(memberships__user=request.user)
        organization_id = (
            request.POST.get("organization")
            or request.GET.get("organization")
            or request.headers.get("X-KERMS-Organization")
        )
        organization = organizations.filter(pk=organization_id).first()
        if not organization:
            organization = organizations.first()
        if not organization:
            return self.get_response(request)

        subscription = OrganizationSubscription.objects.filter(
            organization=organization
        ).select_related("plan").first()
        if not subscription:
            starter_plan = SubscriptionPlan.objects.get(code="starter")
            subscription, _ = OrganizationSubscription.objects.get_or_create(
                organization=organization,
                defaults={
                    "plan": starter_plan,
                    "status": OrganizationSubscription.Status.ONBOARDING_DUE,
                },
            )

        feature = next(
            (
                name
                for prefix, name in self.feature_paths
                if request.path.startswith(prefix)
            ),
            None,
        )
        if feature and not subscription.plan.enables(feature):
            messages.info(
                request,
                f"The {feature.replace('_', ' ')} feature is not included in your current plan.",
            )
            return redirect(f"{reverse('billing')}?organization={organization.pk}")

        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return self.get_response(request)
        if subscription.allows_writes():
            quota_message = None
            if request.path.startswith("/locations/") and not request.POST.get(
                "location_id"
            ):
                limit = subscription.plan.location_limit
                if limit and Location.objects.filter(
                    organization=organization
                ).count() >= limit:
                    quota_message = "Your plan has reached its business location limit."
            elif request.path == "/risks/new/":
                limit = subscription.plan.active_risk_limit
                if limit and Risk.objects.filter(
                    organization=organization
                ).exclude(status=Risk.Status.CLOSED).count() >= limit:
                    quota_message = "Your plan has reached its active risk limit."
            if quota_message:
                messages.info(request, quota_message)
                return redirect(f"{reverse('billing')}?organization={organization.pk}")
            return self.get_response(request)

        if subscription.status == subscription.Status.ONBOARDING_DUE:
            message = (
                "This workspace is read-only until its KES 500 onboarding payment is confirmed."
            )
        else:
            message = (
                "This workspace is read-only while its subscription is inactive. Renew to restore editing."
            )
        messages.warning(request, message)
        return redirect(f"{reverse('billing')}?organization={organization.pk}")
