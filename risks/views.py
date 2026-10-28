from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
import hashlib
import secrets
from decimal import Decimal

from .forms import RiskForm, ScenarioForm, RiskControlForm, AssuranceTestForm, LossIncidentForm, FrameworkForm, FrameworkRequirementForm, ComplianceMappingForm, GovernanceCommitteeForm, GovernancePolicyForm, IntegrationConnectionForm, WebhookEndpointForm
from .models import Organization, Risk, RiskTreatment, RiskControl, ExternalRiskSource, ExternalRiskAlert, Asset, Supplier, Portfolio, BusinessUnit, LegalEntity, AssetDependency, Location, StressScenario, ScenarioImpact, LossIncident, ComplianceFramework, FrameworkRequirement, ComplianceMapping, GovernanceCommittee, GovernancePolicy, IntegrationConnection, ApiCredential, IntegrationEvent, WebhookEndpoint
from .asset_forms import AssetForm, SupplierForm, DependencyForm


def user_organizations(request):
    if request.user.is_superuser:
        return Organization.objects.all()
    return Organization.objects.filter(memberships__user=request.user)


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
def dashboard(request):
    organizations = user_organizations(request)
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    risks = Risk.objects.filter(organization=organization) if organization else Risk.objects.none()
    map_risks = risks.exclude(location__isnull=True)
    ratings = {name: risks.filter(residual_likelihood__gt=0).filter(residual_impact__gt=0).count() for name in ()}

    type_counts = list(risks.values("risk_type").annotate(count=Count("id")))
    rating_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for risk in risks:
        rating_counts[risk.rating] += 1

    context = {
        "organizations": organizations,
        "organization": organization,
        "risks": risks[:8],
        "risk_count": risks.count(),
        "open_treatments": RiskTreatment.objects.filter(risk__in=risks).exclude(status="complete").count(),
        "critical_count": rating_counts["Critical"],
        "rating_counts": rating_counts,
        "type_counts": type_counts,
        "map_risks": map_risks,
    }
    return render(request, "dashboard.html", context)


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
    if request.method == "POST":
        form = RiskForm(request.POST)
        if form.is_valid():
            risk = form.save(commit=False)
            risk.organization = organizations.filter(pk=request.POST.get("organization")).first() or organizations.first()
            if risk.organization:
                risk.save()
                return redirect("risk_detail", pk=risk.pk)
    else:
        form = RiskForm()
    return render(request, "risk_form.html", {"form": form, "organizations": organizations})


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
    organization = organizations.filter(pk=request.GET.get("organization")).first() or organizations.first()
    scenario_rows = StressScenario.objects.none()
    form = ScenarioForm(organization=organization)
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
                direct_risk_ids.update(Risk.objects.filter(assets__in=selected.assets.all()).values_list("pk", flat=True))
                for risk in Risk.objects.filter(pk__in=direct_risk_ids):
                    exposure = selected.expected_exposure * severity_factor * (Decimal(risk.residual_score) / Decimal("25"))
                    ScenarioImpact.objects.create(scenario=selected, risk=risk, cascade_level=0,
                        exposure=exposure.quantize(Decimal("0.01")),
                        narrative="Directly affected by the scenario or linked through a selected asset.")
                direct_assets = set(selected.assets.all())
                for asset in direct_assets:
                    exposure = selected.expected_exposure * severity_factor * (Decimal(asset.criticality) / Decimal("5"))
                    ScenarioImpact.objects.create(scenario=selected, asset=asset, cascade_level=0,
                        exposure=exposure.quantize(Decimal("0.01")), narrative="Directly selected asset impact.")
                cascade_assets = set()
                cascade_suppliers = set(selected.suppliers.all())
                for asset in direct_assets:
                    for dependency in AssetDependency.objects.filter(source_asset=asset).select_related("target_asset", "supplier"):
                        if dependency.target_asset:
                            cascade_assets.add(dependency.target_asset)
                        if dependency.supplier:
                            cascade_suppliers.add(dependency.supplier)
                for asset in cascade_assets:
                    exposure = selected.expected_exposure * severity_factor * (Decimal(asset.criticality) / Decimal("5")) * Decimal("0.75")
                    ScenarioImpact.objects.create(scenario=selected, asset=asset, cascade_level=1,
                        exposure=exposure.quantize(Decimal("0.01")), narrative="First-level dependency cascade.")
                    for risk in asset.risks.all():
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
        "scenarios": scenario_rows, "selected": selected, "form": form})


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
                token = "cgs_" + secrets.token_urlsafe(32)
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
    return JsonResponse({"status": "ok", "service": "CGS Risk API", "version": "v1"})


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
