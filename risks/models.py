from django.db import models


class RiskCategory(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=80, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "risk categories"

    def __str__(self):
        return f"{self.code} - {self.name}"


class RiskTheme(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class EnterpriseFunction(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StrategicObjective(models.Model):
    name = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExternalStakeholder(models.Model):
    name = models.CharField(max_length=120, unique=True)
    accountable_party = models.CharField(max_length=255, blank=True)
    influence_mechanism = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RiskAppetite(models.Model):
    name = models.CharField(max_length=20, unique=True)
    tolerance_threshold = models.PositiveSmallIntegerField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["tolerance_threshold", "name"]

    def __str__(self):
        return f"{self.name} ({self.tolerance_threshold})"


class Organization(models.Model):
    name = models.CharField(max_length=160, unique=True)
    code = models.CharField(max_length=20, unique=True)
    def __str__(self): return self.name


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        RISK_MANAGER = "risk_manager", "Risk Manager"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="risk_memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    class Meta: unique_together = ("user", "organization")


class Location(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=160)
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    class Meta:
        unique_together = ("organization", "name", "country")
        ordering = ("country", "name")
    def __str__(self): return f"{self.name}, {self.country}"


class Risk(models.Model):
    class Status(models.TextChoices):
        IDENTIFIED = "identified", "Identified"
        ASSESSING = "assessing", "Assessing"
        TREATING = "treating", "Treating"
        MONITORING = "monitoring", "Monitoring"
        CLOSED = "closed", "Closed"
        ACCEPTED = "accepted", "Accepted"
    class RiskType(models.TextChoices):
        STRATEGIC = "strategic", "Strategic"
        FINANCIAL = "financial", "Financial"
        OPERATIONAL = "operational", "Operational"
        POLITICAL = "political", "Political & Geopolitical"
        CLIMATE = "climate", "Climate & Environmental"
        CYBER = "cyber", "Cybersecurity"
        COMPLIANCE = "compliance", "Compliance & Legal"
        THIRD_PARTY = "third_party", "Third Party"
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="risks")
    reference = models.CharField(max_length=30)
    title = models.CharField(max_length=220)
    description = models.TextField()
    risk_type = models.CharField(max_length=20, choices=RiskType.choices)
    category = models.ForeignKey(RiskCategory, on_delete=models.PROTECT, null=True, blank=True)
    theme = models.ForeignKey(RiskTheme, on_delete=models.PROTECT, null=True, blank=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="risks")
    enterprise_function = models.ForeignKey(EnterpriseFunction, on_delete=models.SET_NULL, null=True, blank=True)
    strategic_objective = models.ForeignKey(StrategicObjective, on_delete=models.SET_NULL, null=True, blank=True)
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_risks")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDENTIFIED)
    likelihood = models.PositiveSmallIntegerField(default=3)
    impact = models.PositiveSmallIntegerField(default=3)
    residual_likelihood = models.PositiveSmallIntegerField(default=2)
    residual_impact = models.PositiveSmallIntegerField(default=2)
    appetite = models.ForeignKey(RiskAppetite, on_delete=models.SET_NULL, null=True, blank=True)
    early_warning_indicator = models.CharField(max_length=255, blank=True)
    early_warning_threshold = models.CharField(max_length=255, blank=True)
    review_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("organization", "reference")
        ordering = ("-updated_at", "reference")
    @property
    def inherent_score(self): return self.likelihood * self.impact
    @property
    def residual_score(self): return self.residual_likelihood * self.residual_impact
    @property
    def rating(self):
        score = self.residual_score
        if score >= 20: return "Critical"
        if score >= 12: return "High"
        if score >= 6: return "Medium"
        return "Low"
    def __str__(self): return f"{self.reference} - {self.title}"


class RiskControl(models.Model):
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="controls")
    name = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    effective = models.BooleanField(default=True)
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)
    def __str__(self): return self.name


class RiskTreatment(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETE = "complete", "Complete"
        BLOCKED = "blocked", "Blocked"
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="treatments")
    action = models.CharField(max_length=255)
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    due_date = models.DateField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    class Meta: ordering = ("due_date", "-progress")


class RiskAssessment(models.Model):
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="assessments")
    assessor = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    likelihood = models.PositiveSmallIntegerField()
    impact = models.PositiveSmallIntegerField()
    residual_likelihood = models.PositiveSmallIntegerField()
    residual_impact = models.PositiveSmallIntegerField()
    rationale = models.TextField(blank=True)
    assessed_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ("-assessed_at",)


class ReportTemplate(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="report_templates")
    name = models.CharField(max_length=160)
    include_heatmap = models.BooleanField(default=True)
    include_geography = models.BooleanField(default=True)
    include_appetite_breaches = models.BooleanField(default=True)
    include_controls_assurance = models.BooleanField(default=True)
    include_action_aging = models.BooleanField(default=True)
    include_ai_narrative = models.BooleanField(default=False)
    management_commentary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Report(models.Model):
    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        DOCX = "docx", "Word"
        PPTX = "pptx", "PowerPoint"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="reports")
    template = models.ForeignKey(ReportTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    title = models.CharField(max_length=220)
    report_format = models.CharField(max_length=10, choices=Format.choices, default=Format.PDF)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to="reports/%Y/%m/", blank=True)
    executive_summary = models.TextField(blank=True)
    content_source = models.CharField(max_length=255, default="Verified organizational risk register")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ReportSchedule(models.Model):
    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        ANNUAL = "annual", "Annual"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="report_schedules")
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name="schedules")
    name = models.CharField(max_length=160)
    frequency = models.CharField(max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY)
    recipients = models.TextField(help_text="Comma-separated email addresses")
    report_format = models.CharField(max_length=10, choices=Report.Format.choices, default=Report.Format.PDF)
    active = models.BooleanField(default=True)
    last_generated_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Portfolio(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="portfolios")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name


class BusinessUnit(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="business_units")
    name = models.CharField(max_length=160)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name


class LegalEntity(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="legal_entities")
    name = models.CharField(max_length=160)
    country = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("country", "name")

    def __str__(self):
        return self.name


class Asset(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="assets")
    name = models.CharField(max_length=160)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    portfolio = models.ForeignKey(Portfolio, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    asset_type = models.CharField(max_length=80, default="Business asset")
    criticality = models.PositiveSmallIntegerField(default=3)
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_assets")
    risks = models.ManyToManyField("Risk", blank=True, related_name="assets")

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=160)
    country = models.CharField(max_length=100, blank=True)
    supplier_type = models.CharField(max_length=100, default="Third party")
    criticality = models.PositiveSmallIntegerField(default=3)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("criticality", "name")

    def __str__(self):
        return self.name


class AssetDependency(models.Model):
    class DependencyType(models.TextChoices):
        SUPPLIED_BY = "supplied_by", "Supplied by"
        DEPENDS_ON = "depends_on", "Depends on"
        HOSTED_IN = "hosted_in", "Hosted in"
        SERVES = "serves", "Serves"

    source_asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="outgoing_dependencies")
    target_asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True, related_name="incoming_dependencies")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, null=True, blank=True, related_name="dependencies")
    dependency_type = models.CharField(max_length=20, choices=DependencyType.choices, default=DependencyType.DEPENDS_ON)
    criticality = models.PositiveSmallIntegerField(default=3)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-criticality", "source_asset__name")


class ExternalRiskSource(models.Model):
    class Category(models.TextChoices):
        GEOPOLITICAL = "geopolitical", "Geopolitical and conflict"
        CLIMATE = "climate", "Climate and catastrophe"
        CYBER = "cyber", "Cyber threats and vulnerabilities"
        SUPPLY_CHAIN = "supply_chain", "Supply chain and country disruption"
        REGULATORY = "regulatory", "Regulatory and legal"
        FINANCIAL = "financial", "Credit, market, and currency"
        OTHER = "other", "Other"

    name = models.CharField(max_length=160)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="intelligence_sources", null=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    feed_url = models.URLField(max_length=500)
    provider_type = models.CharField(max_length=30, default="rss")
    active = models.BooleanField(default=True)
    verified_source = models.BooleanField(default=False)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ("category", "name")

    def __str__(self):
        return self.name


class ExternalRiskAlert(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="external_alerts")
    source = models.ForeignKey(ExternalRiskSource, on_delete=models.CASCADE, related_name="alerts")
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=ExternalRiskSource.Category.choices, default=ExternalRiskSource.Category.OTHER)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    country = models.CharField(max_length=100, blank=True)
    locations = models.ManyToManyField(Location, blank=True, related_name="external_alerts")
    assets = models.ManyToManyField(Asset, blank=True, related_name="external_alerts")
    portfolios = models.ManyToManyField(Portfolio, blank=True, related_name="external_alerts")
    risks = models.ManyToManyField(Risk, blank=True, related_name="external_alerts")
    source_url = models.URLField(max_length=500, blank=True)
    source_published_at = models.DateTimeField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    confidence = models.PositiveSmallIntegerField(default=70)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="acknowledged_alerts")
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "source", "external_id")
        ordering = ("-source_published_at", "-ingested_at")

    def __str__(self):
        return self.title


class StressScenario(models.Model):
    class ScenarioType(models.TextChoices):
        FLOODING = "flooding", "Flooding"
        SANCTIONS = "sanctions", "Sanctions"
        CURRENCY = "currency", "Currency movement"
        POLITICAL = "political", "Political disruption"
        CYBER = "cyber", "Cyber outage"
        SUPPLIER = "supplier", "Supplier failure"
        CUSTOM = "custom", "Custom scenario"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ASSESSED = "assessed", "Assessed"
        APPROVED = "approved", "Approved"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="stress_scenarios")
    name = models.CharField(max_length=220)
    scenario_type = models.CharField(max_length=20, choices=ScenarioType.choices, default=ScenarioType.CUSTOM)
    description = models.TextField()
    assumptions = models.TextField(blank=True)
    severity = models.PositiveSmallIntegerField(default=3)
    expected_exposure = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    risks = models.ManyToManyField(Risk, blank=True, related_name="stress_scenarios")
    assets = models.ManyToManyField(Asset, blank=True, related_name="stress_scenarios")
    suppliers = models.ManyToManyField(Supplier, blank=True, related_name="stress_scenarios")
    locations = models.ManyToManyField(Location, blank=True, related_name="stress_scenarios")
    portfolios = models.ManyToManyField(Portfolio, blank=True, related_name="stress_scenarios")
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_scenarios")
    approved_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_scenarios")
    approved_at = models.DateTimeField(null=True, blank=True)
    assessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "name")

    def __str__(self):
        return self.name


class ScenarioImpact(models.Model):
    scenario = models.ForeignKey(StressScenario, on_delete=models.CASCADE, related_name="impacts")
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, null=True, blank=True, related_name="scenario_impacts")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True, related_name="scenario_impacts")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, null=True, blank=True, related_name="scenario_impacts")
    cascade_level = models.PositiveSmallIntegerField(default=0)
    exposure = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    narrative = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("cascade_level", "-exposure")


class LossIncident(models.Model):
    class Category(models.TextChoices):
        OPERATIONAL = "operational", "Operational disruption"
        CYBER = "cyber", "Cyber incident"
        FRAUD = "fraud", "Fraud"
        LEGAL = "legal", "Legal or regulatory"
        THIRD_PARTY = "third_party", "Third party"
        CLIMATE = "climate", "Climate or natural hazard"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        REPORTED = "reported", "Reported"
        INVESTIGATING = "investigating", "Investigating"
        CONTAINED = "contained", "Contained"
        RECOVERING = "recovering", "Recovering"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="loss_incidents")
    reference = models.CharField(max_length=30)
    title = models.CharField(max_length=220)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OPERATIONAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED)
    risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="loss_incidents")
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="loss_incidents")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="loss_incidents")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="loss_incidents")
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_loss_incidents")
    occurred_at = models.DateTimeField()
    detected_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    gross_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    recovered_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    root_cause = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("organization", "reference")
        ordering = ("-occurred_at", "-created_at")

    @property
    def net_loss(self):
        return max(self.gross_loss - self.recovered_amount, 0)

    def __str__(self):
        return f"{self.reference} - {self.title}"


class ComplianceFramework(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="compliance_frameworks")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    version = models.CharField(max_length=40, blank=True)
    regulator = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "code", "version")
        ordering = ("name", "version")

    def __str__(self):
        return f"{self.code} {self.version}".strip()


class FrameworkRequirement(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        IMPLEMENTED = "implemented", "Implemented"
        EVIDENCE_REVIEW = "evidence_review", "Evidence review"
        COMPLIANT = "compliant", "Compliant"
        GAP = "gap", "Gap identified"

    framework = models.ForeignKey(ComplianceFramework, on_delete=models.CASCADE, related_name="requirements")
    reference = models.CharField(max_length=50)
    title = models.CharField(max_length=220)
    guidance = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_framework_requirements")
    target_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("framework", "reference")
        ordering = ("reference",)

    def __str__(self):
        return f"{self.framework.code} {self.reference}"


class ComplianceMapping(models.Model):
    class MappingType(models.TextChoices):
        SUPPORTS = "supports", "Supports requirement"
        PARTIAL = "partial", "Partially satisfies"
        GAP = "gap", "Identified gap"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="compliance_mappings")
    requirement = models.ForeignKey(FrameworkRequirement, on_delete=models.CASCADE, related_name="mappings")
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, null=True, blank=True, related_name="compliance_mappings")
    control = models.ForeignKey(RiskControl, on_delete=models.CASCADE, null=True, blank=True, related_name="compliance_mappings")
    mapping_type = models.CharField(max_length=20, choices=MappingType.choices, default=MappingType.SUPPORTS)
    rationale = models.TextField(blank=True)


class GovernanceCommittee(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="governance_committees")
    name = models.CharField(max_length=160)
    purpose = models.TextField(blank=True)
    chair = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="chaired_committees")
    meeting_frequency = models.CharField(max_length=80, blank=True)
    next_meeting = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name


class GovernancePolicy(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        REVIEW_DUE = "review_due", "Review due"
        RETIRED = "retired", "Retired"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="governance_policies")
    reference = models.CharField(max_length=30)
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True)
    owner = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_policies")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_at = models.DateField(null=True, blank=True)
    review_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("organization", "reference")
        ordering = ("reference",)

    def __str__(self):
        return f"{self.reference} - {self.title}"


class AssuranceTest(models.Model):
    class Result(models.TextChoices):
        EFFECTIVE = "effective", "Effective"
        PARTIALLY_EFFECTIVE = "partially_effective", "Partially effective"
        INEFFECTIVE = "ineffective", "Ineffective"
        NOT_TESTED = "not_tested", "Not tested"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="assurance_tests")
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="assurance_tests", null=True, blank=True)
    control = models.ForeignKey(RiskControl, on_delete=models.CASCADE, related_name="assurance_tests", null=True, blank=True)
    name = models.CharField(max_length=220)
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.NOT_TESTED)
    tested_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    tested_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    class Meta:
        ordering = ("-tested_at", "name")


class IntegrationConnection(models.Model):
    class ConnectionType(models.TextChoices):
        REST_API = "rest_api", "REST API"
        WEBHOOK = "webhook", "Webhook"
        FILE_TRANSFER = "file_transfer", "File transfer"
        DATA_FEED = "data_feed", "Data feed"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="integration_connections")
    name = models.CharField(max_length=160)
    connection_type = models.CharField(max_length=20, choices=ConnectionType.choices, default=ConnectionType.REST_API)
    provider = models.CharField(max_length=160, blank=True)
    endpoint_url = models.URLField(max_length=500, blank=True)
    active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name


class ApiCredential(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="api_credentials")
    name = models.CharField(max_length=160)
    token_prefix = models.CharField(max_length=12)
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "name")

    def __str__(self):
        return f"{self.name} ({self.token_prefix}...)"


class IntegrationEvent(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        WARNING = "warning", "Warning"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="integration_events")
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    event_type = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUCCESS)
    message = models.TextField(blank=True)
    actor = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.event_type} - {self.status}"


class WebhookEndpoint(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="webhook_endpoints")
    name = models.CharField(max_length=160)
    target_url = models.URLField(max_length=500)
    event_types = models.CharField(max_length=255, default="risk.updated,alert.created,incident.created")
    secret = models.CharField(max_length=128, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name