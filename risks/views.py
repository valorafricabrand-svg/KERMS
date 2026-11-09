from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import hashlib
import secrets
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .bot_services import evaluate_bot_transaction

from .forms import (
    AssuranceTestForm,
    BusinessProfileForm,
    EntrepreneurAssessmentForm,
    EntrepreneurAssessmentReviewForm,
    FrameworkForm,
    FrameworkRequirementForm,
    GovernanceCommitteeForm,
    GovernancePolicyForm,
    IntegrationConnectionForm,
    LossIncidentForm,
    ManagementRiskAssessmentForm,
    ManagementTransitionForm,
    ComplianceMappingForm,
    RiskControlForm,
    RiskForm,
    ScenarioForm,
    WebhookEndpointForm,
)
from .models import (
    ApiCredential,
    Asset,
    AssetDependency,
    AssuranceTest,
    BusinessProfile,
    BusinessUnit,
    ComplianceFramework,
    ComplianceMapping,
    ExternalRiskAlert,
    ExternalRiskSource,
    EntrepreneurAssessment,
    FrameworkRequirement,
    GovernanceCommittee,
    GovernancePolicy,
    IntegrationConnection,
    IntegrationEvent,
    LegalEntity,
    LossIncident,
    Location,
    ManagementTransition,
    ManagementTransitionRiskReview,
    Organization,
    OrganizationMembership,
    Portfolio,
    Risk,
    RiskAssessment,
    RiskBotAlert,
    RiskBotPolicy,
    RiskBotTransaction,
    RiskControl,
    RiskTreatment,
    ScenarioImpact,
    StressScenario,
    Supplier,
    WebhookEndpoint,
)
from .asset_forms import AssetForm, DependencyForm, LocationForm, SupplierForm
from .assessment_questions import ASSESSMENT_SECTIONS, RESPONSE_CHOICES
from .scenario_library import SCENARIO_TEMPLATES, get_scenario_template
from .site_risk_prompts import site_risk_prompts


def user_organizations(request):
    if request.user.is_superuser:
        return Organization.objects.all()
    return Organization.objects.filter(memberships__user=request.user)


def organization_role(user, organization):
    if user.is_superuser:
        return OrganizationMembership.Role.ADMIN
    return OrganizationMembership.objects.filter(
        user=user, organization=organization
    ).values_list("role", flat=True).first()


@login_required
def global_search(request):
    query = request.GET.get("q", "").strip()
    organizations = user_organizations(request)
    if not query:
        return render(request, "search_results.html", {"query": "", "risks": [], "assets": [], "locations": [], "suppliers": [], "alerts": []})
    risk_rows = Risk.objects.filter(organization__in=organizations).filter(Q(title__icontains=query) | Q(reference__icontains=query) | Q(description__icontains=query))[:20]
    asset_rows = Asset.objects.filter(organization__in=organizations).filter(Q(name__icontains=query) | Q(asset_type__icontains=query))[:20]
    location_rows = Location.objects.filter(organization__in=organizations).filter(Q(name__icontains=query) | Q(country__icontains=query) | Q(region__icontains=query))[:20]
    supplier_rows = Supplier.objects.filter(organization__in=organizations).filter(Q(name__icontains=query) | Q(country__icontains=query))[:20]
    alert_rows = ExternalRiskAlert.objects.filter(organization__in=organizations).filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(country__icontains=query))[:20]
    return render(request, "search_results.html", {"query": query, "risks": risk_rows, "assets": asset_rows, "locations": location_rows, "suppliers": supplier_rows, "alerts": alert_rows})


@login_required
def business_profile(request):
    organizations = user_organizations(request)
    organization = (
        organizations.filter(pk=request.GET.get("organization")).first()
        or organizations.first()
    )
    if not organization:
        return render(
            request,
            "business_profile.html",
            {
                "organizations": organizations,
                "organization": None,
                "can_edit": False,
            },
        )

    role = organization_role(request.user, organization)
    can_edit = role in {
        OrganizationMembership.Role.ADMIN,
        OrganizationMembership.Role.RISK_MANAGER,
        OrganizationMembership.Role.ANALYST,
    }
    profile = BusinessProfile.objects.filter(organization=organization).first()
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        if profile is None:
            profile = BusinessProfile(organization=organization)
        form = BusinessProfileForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.organization = organization
            profile.updated_by = request.user
            profile.save()
            messages.success(request, "Business profile saved.")
            return redirect(f"/business-profile/?organization={organization.pk}")
    else:
        form = BusinessProfileForm(instance=profile)

    if not can_edit:
        for field in form.fields.values():
            field.disabled = True

    return render(
        request,
        "business_profile.html",
        {
            "organizations": organizations,
            "organization": organization,
            "profile": profile,
            "form": form,
            "can_edit": can_edit,
            "profile_completion": profile.profile_completion if profile else 0,
        },
    )


ASSESSMENT_EDITOR_ROLES = {
    OrganizationMembership.Role.ADMIN,
    OrganizationMembership.Role.RISK_MANAGER,
    OrganizationMembership.Role.ANALYST,
}


def build_assessment_sections(responses, form=None):
    response_labels = dict(RESPONSE_CHOICES)
    sections = []
    for section in ASSESSMENT_SECTIONS:
        questions = []
        for key, label in section["questions"]:
            value = responses.get(key, "")
            questions.append(
                {
                    "key": key,
                    "label": label,
                    "value": value,
                    "answer": response_labels.get(value, "Not answered"),
                    "field": form[key] if form else None,
                }
            )
        sections.append(
            {
                "title": section["title"],
                "description": section["description"],
                "questions": questions,
            }
        )
    return sections


@login_required
def business_locations(request):
    organizations = user_organizations(request)
    organization = (
        organizations.filter(
            pk=request.POST.get("organization") or request.GET.get("organization")
        ).first()
        or organizations.first()
    )
    location_form = LocationForm()
    locations = Location.objects.none()
    business_profile = (
        BusinessProfile.objects.filter(organization=organization).first()
        if organization
        else None
    )
    can_edit = bool(
        organization
        and organization_role(request.user, organization) in ASSESSMENT_EDITOR_ROLES
    )

    if organization:
        locations = list(
            Location.objects.filter(organization=organization)
            .annotate(risk_count=Count("risks"), asset_count=Count("assets"))
            .prefetch_related("risks")
        )

    if request.method == "POST":
        if not organization or not can_edit:
            raise PermissionDenied
        location_id = request.POST.get("location_id")
        instance = (
            get_object_or_404(
                Location, organization=organization, pk=location_id
            )
            if location_id
            else None
        )
        location_form = LocationForm(request.POST, instance=instance)
        if location_form.is_valid():
            location = location_form.save(commit=False)
            location.organization = organization
            location.save()
            messages.success(request, "Business location saved.")
            return redirect(f"/locations/?organization={organization.pk}")
    elif request.GET.get("edit") and organization:
        instance = get_object_or_404(
            Location, organization=organization, pk=request.GET["edit"]
        )
        location_form = LocationForm(instance=instance)

    return render(
        request,
        "business_locations.html",
        {
            "organizations": organizations,
            "organization": organization,
            "locations": locations,
            "location_form": location_form,
            "can_edit": can_edit,
            "editing_location": getattr(location_form.instance, "pk", None),
            "exposure_choices": Location.EXPOSURE_CHOICES,
            "business_profile": business_profile,
            "site_risk_prompts": site_risk_prompts(business_profile),
        },
    )


@login_required
def entrepreneur_assessments(request):
    organizations = user_organizations(request)
    organization = (
        organizations.filter(pk=request.GET.get("organization")).first()
        or organizations.first()
    )
    if not organization:
        return render(
            request,
            "assessment_list.html",
            {"organizations": organizations, "organization": None},
        )
    assessments = EntrepreneurAssessment.objects.filter(
        organization=organization
    ).select_related("created_by", "reviewed_by")
    can_edit = organization_role(request.user, organization) in ASSESSMENT_EDITOR_ROLES
    return render(
        request,
        "assessment_list.html",
        {
            "organizations": organizations,
            "organization": organization,
            "assessments": assessments,
            "can_edit": can_edit,
        },
    )


@login_required
def entrepreneur_assessment_create(request):
    organizations = user_organizations(request)
    organization = organizations.filter(
        pk=request.GET.get("organization") or request.POST.get("organization")
    ).first() or organizations.first()
    if not organization:
        raise PermissionDenied
    if organization_role(request.user, organization) not in ASSESSMENT_EDITOR_ROLES:
        raise PermissionDenied

    form = EntrepreneurAssessmentForm(request.POST or None)
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in {"save_draft", "submit"}:
            raise PermissionDenied
        if form.is_valid():
            if action == "submit":
                for key in form.unanswered_questions():
                    form.add_error(key, "Answer this question, or choose Not sure.")
            if not form.errors:
                assessment = form.save(commit=False)
                assessment.organization = organization
                assessment.created_by = request.user
                assessment.responses = form.assessment_responses()
                if action == "submit":
                    assessment.status = EntrepreneurAssessment.Status.SUBMITTED
                    assessment.submitted_at = timezone.now()
                assessment.save()
                messages.success(
                    request,
                    "Assessment submitted for review."
                    if action == "submit"
                    else "Assessment draft saved.",
                )
                return redirect("entrepreneur_assessment_detail", pk=assessment.pk)

    return render(
        request,
        "assessment_form.html",
        {
            "organization": organization,
            "form": form,
            "assessment_sections": build_assessment_sections({}, form),
            "is_new": True,
        },
    )


@login_required
def entrepreneur_assessment_detail(request, pk):
    organizations = user_organizations(request)
    assessment = get_object_or_404(
        EntrepreneurAssessment.objects.select_related(
            "organization", "created_by", "reviewed_by"
        ).prefetch_related("risks"),
        pk=pk,
        organization__in=organizations,
    )
    can_edit = (
        organization_role(request.user, assessment.organization)
        in ASSESSMENT_EDITOR_ROLES
    )
    form = None
    review_form = None
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        action = request.POST.get("action")
        if assessment.status == EntrepreneurAssessment.Status.DRAFT:
            if action not in {"save_draft", "submit"}:
                raise PermissionDenied
            form = EntrepreneurAssessmentForm(request.POST, instance=assessment)
            if form.is_valid():
                if action == "submit":
                    for key in form.unanswered_questions():
                        form.add_error(key, "Answer this question, or choose Not sure.")
                if not form.errors:
                    assessment = form.save(commit=False)
                    assessment.responses = form.assessment_responses()
                    if action == "submit":
                        assessment.status = EntrepreneurAssessment.Status.SUBMITTED
                        assessment.submitted_at = timezone.now()
                    assessment.save()
                    messages.success(
                        request,
                        "Assessment submitted for review."
                        if action == "submit"
                        else "Assessment draft saved.",
                    )
                    return redirect(
                        "entrepreneur_assessment_detail", pk=assessment.pk
                    )
            return render(
                request,
                "assessment_form.html",
                {
                    "organization": assessment.organization,
                    "assessment": assessment,
                    "form": form,
                    "assessment_sections": build_assessment_sections(
                        assessment.responses, form
                    ),
                    "is_new": False,
                },
            )
        if (
            assessment.status != EntrepreneurAssessment.Status.SUBMITTED
            or action != "review"
        ):
            raise PermissionDenied
        review_form = EntrepreneurAssessmentReviewForm(request.POST)
        review_form.fields["risk_links"].queryset = Risk.objects.filter(
            organization=assessment.organization
        ).order_by("reference")
        if review_form.is_valid():
            assessment.review_notes = review_form.cleaned_data["review_notes"]
            assessment.status = EntrepreneurAssessment.Status.REVIEWED
            assessment.reviewed_by = request.user
            assessment.reviewed_at = timezone.now()
            assessment.save()
            assessment.risks.set(review_form.cleaned_data["risk_links"])
            messages.success(request, "Assessment review recorded.")
            return redirect("entrepreneur_assessment_detail", pk=assessment.pk)
    else:
        form = (
            EntrepreneurAssessmentForm(instance=assessment)
            if assessment.status == EntrepreneurAssessment.Status.DRAFT and can_edit
            else None
        )
        review_form = None
        if (
            assessment.status == EntrepreneurAssessment.Status.SUBMITTED
            and can_edit
        ):
            review_form = EntrepreneurAssessmentReviewForm(
                initial={"risk_links": assessment.risks.all()}
            )
            review_form.fields["risk_links"].queryset = Risk.objects.filter(
                organization=assessment.organization
            ).order_by("reference")

    return render(
        request,
        "assessment_detail.html",
        {
            "assessment": assessment,
            "can_edit": can_edit,
            "form": form,
            "review_form": review_form,
            "assessment_sections": build_assessment_sections(
                assessment.responses, form
            ),
        },
    )


@login_required
def dashboard(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    risks = (
        Risk.objects.filter(organization=organization).exclude(
            status=Risk.Status.CLOSED
        )
        if organization
        else Risk.objects.none()
    )
    open_risk_count = risks.count()
    rating_counts = {name: 0 for name in ("Critical", "High", "Medium", "Low")}
    priority_risks = []
    for risk in risks.select_related("location"):
        rating_counts[risk.rating] += 1
        if risk.rating in {"Critical", "High"}:
            priority_risks.append(risk)
    priority_risks.sort(key=lambda risk: risk.residual_score, reverse=True)

    today = timezone.localdate()
    policy = (
        RiskBotPolicy.objects.filter(organization=organization).first()
        if organization
        else None
    )
    business_profile_record = (
        BusinessProfile.objects.filter(organization=organization).first()
        if organization
        else None
    )
    location_rows = (
        Location.objects.filter(organization=organization)
        if organization
        else Location.objects.none()
    )
    location_count = location_rows.count()
    mapped_location_count = location_rows.filter(
        latitude__isnull=False, longitude__isnull=False
    ).count()
    latest_assessment = (
        EntrepreneurAssessment.objects.filter(organization=organization)
        .select_related("created_by", "reviewed_by")
        .first()
        if organization
        else None
    )
    profile_sales_channels = []
    profile_payment_methods = []
    if business_profile_record:
        profile_sales_channels = [
            label
            for value, label in BusinessProfile.CHANNEL_CHOICES
            if value in business_profile_record.sales_channels
        ]
        profile_payment_methods = [
            label
            for value, label in BusinessProfile.PAYMENT_CHOICES
            if value in business_profile_record.payment_methods
        ]
    assessment_response_labels = dict(RESPONSE_CHOICES)
    assessment_questions = (
        [
            {
                "label": label,
                "status": latest_assessment.responses.get(key, ""),
                "status_label": assessment_response_labels.get(
                    latest_assessment.responses.get(key, ""), "Not answered"
                ),
                "status_class": latest_assessment.responses.get(key, "")
                or "not-answered",
            }
            for section in ASSESSMENT_SECTIONS
            for key, label in section["questions"]
        ]
        if latest_assessment
        else []
    )
    assessment_topics_to_discuss = [
        item
        for item in assessment_questions
        if item["status"] in {"partly", "not_in_place", "not_sure"}
    ]
    treatments = (
        RiskTreatment.objects.filter(risk__organization=organization)
        .exclude(status=RiskTreatment.Status.COMPLETE)
        if organization
        else RiskTreatment.objects.none()
    )
    overdue_actions = treatments.filter(due_date__lt=today).select_related(
        "risk", "owner"
    )
    due_today_actions = treatments.filter(due_date=today).select_related(
        "risk", "owner"
    )
    bot_alerts = (
        RiskBotAlert.objects.filter(
            organization=organization, status=RiskBotAlert.Status.NEW
        ).select_related("risk", "transaction")
        if organization
        else RiskBotAlert.objects.none()
    )
    open_incidents = (
        LossIncident.objects.filter(organization=organization)
        .exclude(status=LossIncident.Status.CLOSED)
        if organization
        else LossIncident.objects.none()
    )
    total_actions_due = overdue_actions.count() + due_today_actions.count()
    setup_needed = bool(
        organization
        and (
            not business_profile_record
            or business_profile_record.profile_completion < 100
            or not EntrepreneurAssessment.objects.filter(
                organization=organization
            ).exists()
            or not risks.exists()
            or not mapped_location_count
        )
    )

    context = {
        "organizations": organizations,
        "organization": organization,
        "policy": policy,
        "business_profile": business_profile_record,
        "business_profile_completion": (
            business_profile_record.profile_completion
            if business_profile_record
            else 0
        ),
        "location_count": location_count,
        "mapped_location_count": mapped_location_count,
        "profile_sales_channels": profile_sales_channels,
        "profile_payment_methods": profile_payment_methods,
        "latest_assessment": latest_assessment,
        "assessment_topics_to_discuss": assessment_topics_to_discuss,
        "priority_risks": priority_risks[:5],
        "open_risk_count": open_risk_count,
        "priority_risk_count": rating_counts["Critical"] + rating_counts["High"],
        "open_incident_count": open_incidents.count(),
        "open_incidents": open_incidents.select_related("risk")[:5],
        "new_bot_alert_count": bot_alerts.count(),
        "new_bot_alerts": bot_alerts[:5],
        "overdue_action_count": overdue_actions.count(),
        "due_today_action_count": due_today_actions.count(),
        "total_actions_due": total_actions_due,
        "overdue_actions": overdue_actions[:5],
        "due_today_actions": due_today_actions[:5],
        "rating_counts": rating_counts,
        "risk_profile": [
            {
                "name": name,
                "count": count,
                "percentage": round(count / open_risk_count * 100)
                if open_risk_count
                else 0,
            }
            for name, count in rating_counts.items()
        ],
        "setup_needed": setup_needed,
    }
    return render(request, "dashboard.html", context)


@login_required
def risk_bot_dashboard(request):
    organizations = user_organizations(request)
    organization = (
        organizations.filter(pk=request.GET.get("organization")).first()
        or organizations.first()
    )
    policy = (
        RiskBotPolicy.objects.select_related("linked_risk").filter(
            organization=organization
        ).first()
        if organization
        else None
    )
    alerts = (
        RiskBotAlert.objects.filter(organization=organization)
        .select_related("risk", "transaction")[:25]
        if organization
        else RiskBotAlert.objects.none()
    )
    transactions = (
        RiskBotTransaction.objects.filter(organization=organization)[:10]
        if organization
        else RiskBotTransaction.objects.none()
    )
    for payment in transactions:
        payment.masked_payer = (
            f"{'*' * max(0, len(payment.payer_phone) - 4)}{payment.payer_phone[-4:]}"
            if payment.payer_phone
            else "Unknown"
        )
    context = {
        "organizations": organizations,
        "organization": organization,
        "policy": policy,
        "alerts": alerts,
        "transactions": transactions,
        "alert_count": (
            RiskBotAlert.objects.filter(organization=organization).count()
            if organization
            else 0
        ),
        "new_alert_count": (
            RiskBotAlert.objects.filter(
                organization=organization, status=RiskBotAlert.Status.NEW
            ).count()
            if organization
            else 0
        ),
        "transaction_count": (
            RiskBotTransaction.objects.filter(organization=organization).count()
            if organization
            else 0
        ),
    }
    return render(request, "risk_bot.html", context)


@login_required
def risk_register(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    risks = Risk.objects.filter(organization=organization) if organization else Risk.objects.none()
    risk_type = request.GET.get("type")
    status = request.GET.get("status")
    search = request.GET.get("q")
    if risk_type:
        risks = risks.filter(risk_type=risk_type)
    if status:
        risks = risks.filter(status=status)
    if search:
        risks = risks.filter(title__icontains=search)
    return render(request, "risk_register.html", {
        "organizations": organizations,
        "organization": organization,
        "risks": risks,
        "risk_types": Risk.RiskType.choices,
        "statuses": Risk.Status.choices,
    })


@login_required
def risk_detail(request, pk):
    organizations = user_organizations(request)
    risk = get_object_or_404(Risk, pk=pk, organization__in=organizations)
    return render(request, "risk_detail.html", {"risk": risk, "organizations": organizations})


@login_required
def risk_create(request):
    organizations = user_organizations(request)
    organization = (
        organizations.filter(
            pk=request.POST.get("organization") or request.GET.get("organization")
        ).first()
        or organizations.first()
    )
    if (
        organization
        and organization_role(request.user, organization)
        not in ASSESSMENT_EDITOR_ROLES
    ):
        raise PermissionDenied
    if request.method == "POST":
        form = RiskForm(request.POST, organization=organization)
        if form.is_valid():
            risk = form.save(commit=False)
            risk.organization = organization
            if organization:
                risk.save()
                return redirect("risk_detail", pk=risk.pk)
    else:
        form = RiskForm(
            organization=organization,
            initial={"location": request.GET.get("location") or None},
        )
    return render(
        request,
        "risk_form.html",
        {
            "form": form,
            "organizations": organizations,
            "selected_organization": organization,
        },
    )


from django.http import FileResponse, HttpResponse
from django.core.mail import EmailMessage
from django.utils import timezone
from .report_forms import ReportTemplateForm, ReportScheduleForm
from .models import ReportTemplate, Report, ReportSchedule, AssuranceTest
from .reporting import risk_summary, generate_report


@login_required
def reports(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    if not organization:
        return render(request, "reports.html", {"organizations": organizations, "organization": None})
    risks, counts, breaches, overdue, aging, narrative = risk_summary(organization)
    templates = ReportTemplate.objects.filter(organization=organization)
    schedules = ReportSchedule.objects.filter(organization=organization)
    generated = Report.objects.filter(organization=organization)
    templates_form = ReportTemplateForm()
    schedules_form = ReportScheduleForm()
    schedules_form.fields["template"].queryset = templates
    if request.method == "POST" and request.POST.get("action") == "create_template":
        templates_form = ReportTemplateForm(request.POST)
        if templates_form.is_valid():
            template = templates_form.save(commit=False); template.organization = organization; template.save()
            return redirect(f"/reports/?organization={organization.pk}")
    if request.method == "POST" and request.POST.get("action") == "create_schedule":
        schedules_form = ReportScheduleForm(request.POST)
        schedules_form.fields["template"].queryset = templates
        if schedules_form.is_valid():
            schedule = schedules_form.save(commit=False); schedule.organization = organization
            if not schedule.next_run_at:
                schedule.next_run_at = timezone.now()
            schedule.save()
            return redirect(f"/reports/?organization={organization.pk}")
    return render(request, "reports.html", {"organizations": organizations, "organization": organization,
        "templates": templates, "schedules": schedules, "generated": generated, "templates_form": templates_form,
        "schedules_form": schedules_form, "counts": counts, "breaches": breaches, "overdue": overdue,
        "aging": aging, "narrative": narrative})


@login_required
@login_required
def assets(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    asset_rows = Asset.objects.none(); suppliers = Supplier.objects.none(); dependencies = AssetDependency.objects.none(); portfolios = Portfolio.objects.none()
    if organization:
        asset_rows = Asset.objects.filter(organization=organization)
        suppliers = Supplier.objects.filter(organization=organization)
        dependencies = AssetDependency.objects.filter(source_asset__organization=organization)
        portfolios = Portfolio.objects.filter(organization=organization)
        asset_type = request.GET.get("type")
        if asset_type:
            asset_rows = asset_rows.filter(asset_type__icontains=asset_type)
    asset_form = AssetForm()
    supplier_form = SupplierForm()
    dependency_form = DependencyForm()
    if organization:
        asset_form.fields["location"].queryset = organization.locations.all()
        asset_form.fields["portfolio"].queryset = portfolios
        asset_form.fields["business_unit"].queryset = organization.business_units.all()
        asset_form.fields["legal_entity"].queryset = organization.legal_entities.all()
        asset_form.fields["risks"].queryset = organization.risks.all()
        dependency_form.fields["source_asset"].queryset = asset_rows
        dependency_form.fields["target_asset"].queryset = asset_rows
        dependency_form.fields["supplier"].queryset = suppliers
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "asset":
            form = AssetForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False); obj.organization = organization; obj.save(); form.save_m2m()
                return redirect(f"/assets/?organization={organization.pk}")
        elif action == "supplier":
            form = SupplierForm(request.POST)
            if form.is_valid():
                obj = form.save(commit=False); obj.organization = organization; obj.save()
                return redirect(f"/assets/?organization={organization.pk}")
        elif action == "dependency":
            form = DependencyForm(request.POST)
            if form.is_valid(): form.save()
            return redirect(f"/assets/?organization={organization.pk}")
    concentration = suppliers.filter(criticality__gte=4).count()
    return render(request, "assets.html", {"organizations": organizations, "organization": organization,
        "assets": asset_rows, "suppliers": suppliers, "dependencies": dependencies, "portfolios": portfolios,
        "asset_form": asset_form, "supplier_form": supplier_form, "dependency_form": dependency_form,
        "concentration": concentration})


@login_required
def incidents(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    incident_rows = LossIncident.objects.none()
    form = LossIncidentForm(organization=organization)
    selected = None
    if organization:
        incident_rows = LossIncident.objects.filter(organization=organization)
        category = request.GET.get("category")
        status = request.GET.get("status")
        if category:
            incident_rows = incident_rows.filter(category=category)
        if status:
            incident_rows = incident_rows.filter(status=status)
        selected = incident_rows.filter(pk=request.GET.get("incident")).first() if request.GET.get("incident") else incident_rows.first()
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "create_incident":
                form = LossIncidentForm(request.POST, organization=organization)
                if form.is_valid():
                    incident = form.save(commit=False)
                    incident.organization = organization
                    incident.save()
                    return redirect(f"/incidents/?organization={organization.pk}&incident={incident.pk}")
            elif action == "update_status" and selected:
                new_status = request.POST.get("status")
                if new_status in LossIncident.Status.values:
                    selected.status = new_status
                    if new_status == LossIncident.Status.CLOSED and not selected.resolved_at:
                        selected.resolved_at = timezone.now()
                    selected.save(update_fields=["status", "resolved_at", "updated_at"])
                    return redirect(f"/incidents/?organization={organization.pk}&incident={selected.pk}")
    gross_loss = sum((item.gross_loss for item in incident_rows), Decimal("0"))
    recovered_loss = sum((item.recovered_amount for item in incident_rows), Decimal("0"))
    active_count = incident_rows.exclude(status=LossIncident.Status.CLOSED).count()
    context = {"organizations": organizations, "organization": organization, "incidents": incident_rows,
        "selected": selected, "form": form, "gross_loss": gross_loss,
        "recovered_loss": recovered_loss, "net_loss": gross_loss - recovered_loss,
        "active_count": active_count, "categories": LossIncident.Category.choices,
        "statuses": LossIncident.Status.choices}
    return render(request, "incidents.html", context)


@login_required
def scenarios(request):
    organizations = user_organizations(request)
    organization_id = request.GET.get("organization") or request.POST.get("organization")
    organization = organizations.filter(pk=organization_id).first() or organizations.first()
    scenario_rows = StressScenario.objects.none()
    template = get_scenario_template(request.GET.get("template"))
    initial = None
    if template:
        initial = {
            "name": template.name,
            "scenario_type": template.scenario_type,
            "description": template.description,
            "assumptions": template.assumptions,
            "severity": 3,
            "expected_exposure": "0.00",
        }
    form = ScenarioForm(organization=organization, initial=initial)
    selected = None
    if organization:
        scenario_rows = StressScenario.objects.filter(organization=organization)
        selected_id = request.GET.get("scenario") or request.POST.get("scenario")
        selected = scenario_rows.filter(pk=selected_id).first() if selected_id else scenario_rows.first()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create" and organization:
            form = ScenarioForm(request.POST, organization=organization)
            if form.is_valid():
                scenario = form.save(commit=False)
                scenario.organization = organization
                scenario.created_by = request.user
                scenario.save()
                form.save_m2m()
                return redirect(f"/scenarios/?organization={organization.pk}&scenario={scenario.pk}")
        elif action in ("run", "approve") and selected:
            if action == "run":
                selected.impacts.all().delete()
                severity_factor = Decimal(selected.severity) / Decimal("5")
                direct_risk_ids = set(selected.risks.values_list("pk", flat=True))
                direct_risk_ids.update(
                    Risk.objects.filter(
                        organization=organization, assets__in=selected.assets.all()
                    ).values_list("pk", flat=True)
                )
                for risk in Risk.objects.filter(
                    pk__in=direct_risk_ids, organization=organization
                ):
                    exposure = selected.expected_exposure * severity_factor * (Decimal(risk.residual_score) / Decimal("25"))
                    ScenarioImpact.objects.create(scenario=selected, risk=risk, cascade_level=0,
                        exposure=exposure.quantize(Decimal("0.01")),
                        narrative="Directly affected by the scenario or linked through a selected asset.")
                direct_assets = set(selected.assets.filter(organization=organization))
                for asset in direct_assets:
                    exposure = selected.expected_exposure * severity_factor * (Decimal(asset.criticality) / Decimal("5"))
                    ScenarioImpact.objects.create(scenario=selected, asset=asset, cascade_level=0,
                        exposure=exposure.quantize(Decimal("0.01")), narrative="Directly selected asset impact.")
                cascade_assets = set()
                cascade_suppliers = set(selected.suppliers.filter(organization=organization))
                for asset in direct_assets:
                    dependencies = AssetDependency.objects.filter(
                        source_asset=asset
                    ).select_related("target_asset", "supplier")
                    for dependency in dependencies:
                        if (
                            dependency.target_asset
                            and dependency.target_asset.organization_id == organization.pk
                        ):
                            cascade_assets.add(dependency.target_asset)
                        if (
                            dependency.supplier
                            and dependency.supplier.organization_id == organization.pk
                        ):
                            cascade_suppliers.add(dependency.supplier)
                for asset in cascade_assets:
                    exposure = selected.expected_exposure * severity_factor * (Decimal(asset.criticality) / Decimal("5")) * Decimal("0.75")
                    ScenarioImpact.objects.create(scenario=selected, asset=asset, cascade_level=1,
                        exposure=exposure.quantize(Decimal("0.01")), narrative="First-level dependency cascade.")
                    for risk in asset.risks.filter(organization=organization):
                        exposure = exposure * (Decimal(risk.residual_score) / Decimal("25"))
                        ScenarioImpact.objects.create(scenario=selected, risk=risk, cascade_level=1,
                            exposure=exposure.quantize(Decimal("0.01")), narrative="Risk connected to a cascade-affected asset.")
                for supplier in cascade_suppliers:
                    exposure = selected.expected_exposure * severity_factor * (Decimal(supplier.criticality) / Decimal("5")) * Decimal("0.65")
                    ScenarioImpact.objects.create(scenario=selected, supplier=supplier, cascade_level=1,
                        exposure=exposure.quantize(Decimal("0.01")), narrative="Supplier dependency cascade.")
                selected.status = StressScenario.Status.ASSESSED
                selected.assessed_at = timezone.now()
                selected.save(update_fields=["status", "assessed_at", "updated_at"])
            else:
                selected.status = StressScenario.Status.APPROVED
                selected.approved_by = request.user
                selected.approved_at = timezone.now()
                selected.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
            return redirect(f"/scenarios/?organization={organization.pk}&scenario={selected.pk}")
    return render(request, "scenarios.html", {"organizations": organizations, "organization": organization,
        "scenarios": scenario_rows, "selected": selected, "form": form,
        "scenario_templates": SCENARIO_TEMPLATES})


@login_required
def management(request):
    organizations = user_organizations(request)
    organization = (
        organizations.filter(pk=request.GET.get("organization")).first()
        or organizations.first()
    )
    transitions = ManagementTransition.objects.none()
    selected = None
    reviews = ManagementTransitionRiskReview.objects.none()
    transition_form = ManagementTransitionForm()
    assessment_form = None
    selected_review = None
    role = organization_role(request.user, organization) if organization else None
    can_manage = role in {
        OrganizationMembership.Role.ADMIN,
        OrganizationMembership.Role.RISK_MANAGER,
    }
    can_assess = can_manage or role == OrganizationMembership.Role.ANALYST

    if organization:
        transitions = ManagementTransition.objects.filter(
            organization=organization
        ).annotate(
            review_count=Count("reviews"),
            completed_count=Count(
                "reviews", filter=Q(reviews__assessment__isnull=False)
            ),
        )
        transition_id = request.GET.get("transition") or request.POST.get("transition")
        selected = transitions.filter(pk=transition_id).first() if transition_id else transitions.first()
        if selected:
            reviews = selected.reviews.select_related(
                "risk", "assessment", "reviewed_by"
            ).all()
            review_id = request.GET.get("review") or request.POST.get("review")
            selected_review = reviews.filter(pk=review_id).first() if review_id else None

    if request.method == "POST" and organization:
        action = request.POST.get("action")
        if action == "create_transition":
            if not can_manage:
                raise PermissionDenied
            transition_form = ManagementTransitionForm(request.POST)
            if transition_form.is_valid():
                with transaction.atomic():
                    transition = transition_form.save(commit=False)
                    transition.organization = organization
                    transition.recorded_by = request.user
                    transition.save()
                    open_risks = Risk.objects.filter(
                        organization=organization
                    ).exclude(status=Risk.Status.CLOSED)
                    ManagementTransitionRiskReview.objects.bulk_create(
                        [
                            ManagementTransitionRiskReview(
                                transition=transition, risk=risk
                            )
                            for risk in open_risks
                        ]
                    )
                return redirect(
                    f"/management/?organization={organization.pk}"
                    f"&transition={transition.pk}"
                )
        elif action == "complete_review":
            if not can_assess:
                raise PermissionDenied
            if selected_review and not selected_review.is_complete:
                assessment_form = ManagementRiskAssessmentForm(request.POST)
                if assessment_form.is_valid():
                    values = assessment_form.cleaned_data
                    with transaction.atomic():
                        assessment = RiskAssessment.objects.create(
                            risk=selected_review.risk,
                            assessor=request.user,
                            management_transition=selected_review.transition,
                            **values,
                        )
                        risk = selected_review.risk
                        risk.likelihood = values["likelihood"]
                        risk.impact = values["impact"]
                        risk.residual_likelihood = values["residual_likelihood"]
                        risk.residual_impact = values["residual_impact"]
                        risk.review_date = timezone.localdate()
                        risk.save(
                            update_fields=(
                                "likelihood",
                                "impact",
                                "residual_likelihood",
                                "residual_impact",
                                "review_date",
                                "updated_at",
                            )
                        )
                        selected_review.assessment = assessment
                        selected_review.reviewed_by = request.user
                        selected_review.reviewed_at = timezone.now()
                        selected_review.save(
                            update_fields=(
                                "assessment",
                                "reviewed_by",
                                "reviewed_at",
                            )
                        )
                    return redirect(
                        f"/management/?organization={organization.pk}"
                        f"&transition={selected_review.transition_id}"
                    )

    if selected_review and not selected_review.is_complete and assessment_form is None:
        assessment_form = ManagementRiskAssessmentForm(
            initial={
                "likelihood": selected_review.risk.likelihood,
                "impact": selected_review.risk.impact,
                "residual_likelihood": selected_review.risk.residual_likelihood,
                "residual_impact": selected_review.risk.residual_impact,
            }
        )

    return render(
        request,
        "management.html",
        {
            "organizations": organizations,
            "organization": organization,
            "transitions": transitions,
            "selected": selected,
            "reviews": reviews,
            "selected_review": selected_review,
            "transition_form": transition_form,
            "assessment_form": assessment_form,
            "can_manage": can_manage,
            "can_assess": can_assess,
        },
    )


@login_required
def assurance(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    controls = RiskControl.objects.none()
    tests = AssuranceTest.objects.none()
    control_form = RiskControlForm(organization=organization)
    test_form = AssuranceTestForm(organization=organization)
    if organization:
        controls = RiskControl.objects.filter(risk__organization=organization)
        tests = AssuranceTest.objects.filter(organization=organization)
        result = request.GET.get("result")
        if result:
            tests = tests.filter(result=result)
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "create_control":
                control_form = RiskControlForm(request.POST, organization=organization)
                if control_form.is_valid():
                    control_form.save()
                    return redirect(f"/assurance/?organization={organization.pk}")
            elif action == "create_test":
                test_form = AssuranceTestForm(request.POST, organization=organization)
                if test_form.is_valid():
                    test = test_form.save(commit=False)
                    test.organization = organization
                    test.save()
                    return redirect(f"/assurance/?organization={organization.pk}")
    effective_controls = controls.filter(effective=True).count()
    effective_tests = tests.filter(result=AssuranceTest.Result.EFFECTIVE).count()
    context = {"organizations": organizations, "organization": organization, "controls": controls,
        "tests": tests, "control_form": control_form, "test_form": test_form,
        "control_count": controls.count(), "effective_controls": effective_controls,
        "test_count": tests.count(), "effective_tests": effective_tests,
        "results": AssuranceTest.Result.choices}
    return render(request, "assurance.html", context)


@login_required
def intelligence(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    alerts = ExternalRiskAlert.objects.none()
    if organization:
        alerts = ExternalRiskAlert.objects.filter(organization=organization)
        category = request.GET.get("category")
        severity = request.GET.get("severity")
        if category:
            alerts = alerts.filter(category=category)
        if severity:
            alerts = alerts.filter(severity=severity)
    sources = ExternalRiskSource.objects.filter(Q(organization__isnull=True) | Q(organization=organization)) if organization else ExternalRiskSource.objects.none()
    return render(request, "intelligence.html", {"organizations": organizations, "organization": organization,
        "alerts": alerts, "sources": sources, "categories": ExternalRiskSource.Category.choices,
        "severities": ExternalRiskAlert.Severity.choices})


@login_required
def integrations(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    connections = IntegrationConnection.objects.none()
    credentials = ApiCredential.objects.none()
    events = IntegrationEvent.objects.none()
    webhooks = WebhookEndpoint.objects.none()
    connection_form = IntegrationConnectionForm()
    webhook_form = WebhookEndpointForm()
    new_token = request.session.pop("integration_new_token", None)

    if organization:
        connections = organization.integration_connections.all()
        credentials = organization.api_credentials.all()
        events = organization.integration_events.all()[:50]
        webhooks = organization.webhook_endpoints.all()
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "create_connection":
                connection_form = IntegrationConnectionForm(request.POST)
                if connection_form.is_valid():
                    connection = connection_form.save(commit=False)
                    connection.organization = organization
                    connection.save()
                    IntegrationEvent.objects.create(organization=organization, connection=connection, event_type="connection.created", message="Integration connection registered.", actor=request.user)
                    return redirect(f"/integrations/?organization={organization.pk}")
            elif action == "create_webhook":
                webhook_form = WebhookEndpointForm(request.POST)
                if webhook_form.is_valid():
                    webhook = webhook_form.save(commit=False)
                    webhook.organization = organization
                    webhook.secret = secrets.token_urlsafe(32)
                    webhook.save()
                    IntegrationEvent.objects.create(organization=organization, event_type="webhook.created", message=f"Webhook {webhook.name} registered.", actor=request.user)
                    return redirect(f"/integrations/?organization={organization.pk}")
            elif action == "create_token":
                token = "kerms_" + secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                credential = ApiCredential.objects.create(organization=organization, name=request.POST.get("name") or "API credential", token_prefix=token[:12], token_hash=token_hash, created_by=request.user)
                IntegrationEvent.objects.create(organization=organization, event_type="api_token.created", message=f"API credential {credential.name} created.", actor=request.user)
                request.session["integration_new_token"] = token
                return redirect(f"/integrations/?organization={organization.pk}")

    context = {"organizations": organizations, "organization": organization, "connections": connections,
        "credentials": credentials, "events": events, "webhooks": webhooks,
        "connection_form": connection_form, "webhook_form": webhook_form, "new_token": new_token}
    return render(request, "integrations.html", context)


def api_authorize(request, organizations=None):
    if request.user.is_authenticated:
        return organizations or user_organizations(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return Organization.objects.none()
    token_hash = hashlib.sha256(auth_header[7:].encode()).hexdigest()
    credential = ApiCredential.objects.select_related("organization").filter(token_hash=token_hash, active=True).first()
    if not credential:
        return Organization.objects.none()
    from django.utils import timezone
    credential.last_used_at = timezone.now()
    credential.save(update_fields=["last_used_at"])
    return Organization.objects.filter(pk=credential.organization_id)


def api_risk_summary(request):
    organizations = api_authorize(request, organizations=user_organizations(request) if request.user.is_authenticated else None)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    if not organization:
        return JsonResponse({"error": "No accessible organization"}, status=404)
    risks = organization.risks.all()
    return JsonResponse({"organization": {"id": organization.pk, "name": organization.name, "code": organization.code},
        "risk_count": risks.count(), "risks": [{"reference": r.reference, "title": r.title, "type": r.risk_type,
        "status": r.status, "residual_score": r.residual_score, "rating": r.rating} for r in risks]})


def api_health(request):
    return JsonResponse(
        {"status": "ok", "service": "Kenya ERM API", "version": "v1"}
    )


def _bot_api_organization(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer ") or not auth_header[7:].strip():
        return None, JsonResponse({"error": "A valid bearer token is required."}, status=401)
    token_hash = hashlib.sha256(auth_header[7:].strip().encode()).hexdigest()
    credential = ApiCredential.objects.select_related("organization").filter(
        token_hash=token_hash, active=True
    ).first()
    if not credential or (
        credential.expires_at and credential.expires_at <= timezone.now()
    ):
        return None, JsonResponse({"error": "Invalid or expired API credential."}, status=401)
    credential.last_used_at = timezone.now()
    credential.save(update_fields=["last_used_at"])
    return credential.organization, None


@csrf_exempt
def api_bot_policy(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    organization, error = _bot_api_organization(request)
    if error:
        return error
    policy, _ = RiskBotPolicy.objects.get_or_create(organization=organization)
    return JsonResponse(
        {
            "organization": {"id": organization.pk, "name": organization.name},
            "enabled": policy.enabled,
            "currency": policy.currency,
            "timezone": policy.timezone,
            "rules": {
                "max_single_transaction": str(policy.max_single_transaction),
                "max_daily_payer_total": str(policy.max_daily_payer_total),
                "max_daily_payer_transactions": policy.max_daily_payer_transactions,
            },
            "linked_risk": (
                {
                    "reference": policy.linked_risk.reference,
                    "title": policy.linked_risk.title,
                }
                if policy.linked_risk_id
                else None
            ),
        }
    )


@csrf_exempt
def api_bot_transactions(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    organization, error = _bot_api_organization(request)
    if error:
        return error
    content_length = request.META.get("CONTENT_LENGTH")
    try:
        body_size = int(content_length or 0)
    except ValueError:
        return JsonResponse({"error": "Invalid Content-Length header."}, status=400)
    if body_size < 0:
        return JsonResponse({"error": "Invalid Content-Length header."}, status=400)
    if body_size > 65536:
        return JsonResponse({"error": "Request body exceeds 64 KB."}, status=413)
    payload = request.body
    try:
        import json

        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    policy, _ = RiskBotPolicy.objects.get_or_create(organization=organization)
    receipt = data.get("receipt_number") or data.get("TransID")
    if not isinstance(receipt, str) or not receipt.strip() or len(receipt.strip()) > 100:
        return JsonResponse({"error": "A valid receipt_number is required."}, status=400)
    amount_value = data.get("amount", data.get("TransAmount"))
    try:
        amount = Decimal(str(amount_value))
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"error": "amount must be a non-negative number with at most 2 decimal places."}, status=400)
    if amount > Decimal("999999999999.99"):
        return JsonResponse({"error": "amount exceeds the supported range."}, status=400)
    currency = data.get("currency", policy.currency)
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency):
        return JsonResponse({"error": "currency must be a three-letter code."}, status=400)
    currency = currency.upper()
    if currency != policy.currency:
        return JsonResponse(
            {"error": f"This organization is configured for {policy.currency} transactions."},
            status=400,
        )
    payer_phone = data.get("payer_phone", data.get("MSISDN", ""))
    if payer_phone is None:
        payer_phone = ""
    if not isinstance(payer_phone, str) or len(payer_phone) > 32:
        return JsonResponse({"error": "payer_phone must be a string of at most 32 characters."}, status=400)
    transaction_time_value = data.get("transaction_time") or data.get("TransTime")
    if not isinstance(transaction_time_value, str):
        return JsonResponse({"error": "transaction_time is required."}, status=400)
    try:
        if re.fullmatch(r"\d{14}", transaction_time_value):
            transaction_time = datetime.strptime(
                transaction_time_value, "%Y%m%d%H%M%S"
            ).replace(tzinfo=ZoneInfo(policy.timezone))
        else:
            transaction_time = parse_datetime(transaction_time_value)
            if transaction_time is None or timezone.is_naive(transaction_time):
                raise ValueError
    except (ValueError, OverflowError):
        return JsonResponse(
            {"error": "transaction_time must be ISO 8601 with a timezone, or a Daraja YYYYMMDDHHMMSS timestamp."},
            status=400,
        )
    account_reference = data.get("account_reference", data.get("BillRefNumber", ""))
    if account_reference is None:
        account_reference = ""
    if not isinstance(account_reference, str) or len(account_reference) > 160:
        return JsonResponse({"error": "account_reference must be a string of at most 160 characters."}, status=400)
    source = data.get("source", "mpesa")
    if not isinstance(source, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", source):
        return JsonResponse({"error": "source contains invalid characters."}, status=400)

    transaction_record, created = RiskBotTransaction.objects.get_or_create(
        organization=organization,
        receipt_number=receipt.strip(),
        defaults={
            "amount": amount,
            "currency": currency,
            "payer_phone": payer_phone.strip(),
            "transaction_time": transaction_time,
            "account_reference": account_reference.strip(),
            "source": source.lower(),
        },
    )
    alerts = evaluate_bot_transaction(policy, transaction_record) if created else []
    return JsonResponse(
        {
            "accepted": True,
            "duplicate": not created,
            "transaction_id": transaction_record.pk,
            "alerts_created": len(alerts),
            "alerts": [
                {"id": alert.pk, "rule": alert.rule_code, "severity": alert.severity}
                for alert in alerts
            ],
        },
        status=201 if created else 200,
    )


@csrf_exempt
def api_bot_alerts(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    organization, error = _bot_api_organization(request)
    if error:
        return error
    alerts = RiskBotAlert.objects.filter(organization=organization).select_related(
        "risk", "transaction"
    )
    status_filter = request.GET.get("status")
    if status_filter:
        if status_filter not in RiskBotAlert.Status.values:
            return JsonResponse({"error": "Invalid alert status."}, status=400)
        alerts = alerts.filter(status=status_filter)
    try:
        limit = min(max(int(request.GET.get("limit", "50")), 1), 100)
    except ValueError:
        return JsonResponse({"error": "limit must be an integer."}, status=400)
    return JsonResponse(
        {
            "alerts": [
                {
                    "id": alert.pk,
                    "rule": alert.rule_code,
                    "severity": alert.severity,
                    "status": alert.status,
                    "message": alert.message,
                    "evidence": alert.evidence,
                    "risk": (
                        {"reference": alert.risk.reference, "title": alert.risk.title}
                        if alert.risk_id
                        else None
                    ),
                    "receipt_number": (
                        alert.transaction.receipt_number if alert.transaction_id else None
                    ),
                    "created_at": alert.created_at.isoformat(),
                }
                for alert in alerts[:limit]
            ]
        }
    )


@login_required
def acknowledge_alert(request, pk):
    organizations = user_organizations(request)
    alert = get_object_or_404(ExternalRiskAlert, pk=pk, organization__in=organizations)
    if request.method == "POST":
        alert.acknowledged = True; alert.acknowledged_by = request.user; alert.acknowledged_at = timezone.now(); alert.save(update_fields=["acknowledged", "acknowledged_by", "acknowledged_at"])
    return redirect("intelligence")


@login_required
def governance(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    frameworks = ComplianceFramework.objects.none()
    requirements = FrameworkRequirement.objects.none()
    mappings = ComplianceMapping.objects.none()
    committees = GovernanceCommittee.objects.none()
    policies = GovernancePolicy.objects.none()

    framework_form = FrameworkForm()
    requirement_form = FrameworkRequirementForm(organization=organization)
    mapping_form = ComplianceMappingForm(organization=organization)
    committee_form = GovernanceCommitteeForm()
    policy_form = GovernancePolicyForm()

    if organization:
        frameworks = organization.compliance_frameworks.all()
        requirements = FrameworkRequirement.objects.filter(framework__organization=organization)
        mappings = organization.compliance_mappings.all().select_related("requirement", "risk", "control")
        committees = organization.governance_committees.all()
        policies = organization.governance_policies.all()

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "create_framework":
                framework_form = FrameworkForm(request.POST)
                if framework_form.is_valid():
                    framework = framework_form.save(commit=False)
                    framework.organization = organization
                    framework.save()
                    return redirect(f"/governance/?organization={organization.pk}")
            elif action == "create_requirement":
                requirement_form = FrameworkRequirementForm(request.POST, organization=organization)
                if requirement_form.is_valid():
                    requirement_form.save()
                    return redirect(f"/governance/?organization={organization.pk}")
            elif action == "create_mapping":
                mapping_form = ComplianceMappingForm(request.POST, organization=organization)
                if mapping_form.is_valid():
                    mapping = mapping_form.save(commit=False)
                    mapping.organization = organization
                    mapping.save()
                    return redirect(f"/governance/?organization={organization.pk}")
            elif action == "create_committee":
                committee_form = GovernanceCommitteeForm(request.POST)
                if committee_form.is_valid():
                    committee = committee_form.save(commit=False)
                    committee.organization = organization
                    committee.save()
                    return redirect(f"/governance/?organization={organization.pk}")
            elif action == "create_policy":
                policy_form = GovernancePolicyForm(request.POST)
                if policy_form.is_valid():
                    policy = policy_form.save(commit=False)
                    policy.organization = organization
                    policy.save()
                    return redirect(f"/governance/?organization={organization.pk}")

    gap_count = requirements.filter(status__in=(FrameworkRequirement.Status.GAP, FrameworkRequirement.Status.EVIDENCE_REVIEW)).count()
    review_count = policies.filter(status=GovernancePolicy.Status.REVIEW_DUE).count()
    context = {"organizations": organizations, "organization": organization,
        "frameworks": frameworks, "requirements": requirements, "mappings": mappings,
        "committees": committees, "policies": policies,
        "framework_form": framework_form, "requirement_form": requirement_form,
        "mapping_form": mapping_form, "committee_form": committee_form, "policy_form": policy_form,
        "framework_count": frameworks.count(), "requirement_count": requirements.count(),
        "mapping_count": mappings.count(), "gap_count": gap_count, "review_count": review_count}
    return render(request, "governance.html", context)


def generate_board_report(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.POST.get("organization")).first() or organizations.first()
    if not organization:
        return redirect("reports")
    template_id = request.POST.get("template")
    template = ReportTemplate.objects.filter(pk=template_id, organization=organization).first()
    report_format = request.POST.get("format", "pdf")
    report = Report.objects.create(organization=organization, template=template, title=request.POST.get("title") or "Board Risk Report", report_format=report_format, created_by=request.user)
    url, mimetype = generate_report(report)
    if request.POST.get("download") == "1":
        return FileResponse(report.file.open("rb"), as_attachment=True, filename=report.file.name.split("/")[-1], content_type=mimetype)
    return redirect(f"/reports/?organization={organization.pk}")
