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


class BusinessProfile(models.Model):
    class Sector(models.TextChoices):
        AGRICULTURE = "agriculture", "Farming and agriculture"
        RETAIL = "retail", "Retail and shops"
        FOOD = "food", "Food, hospitality, and catering"
        TRANSPORT = "transport", "Transport and logistics"
        MANUFACTURING = "manufacturing", "Manufacturing and workshops"
        CONSTRUCTION = "construction", "Construction and trades"
        PROFESSIONAL = "professional", "Professional and business services"
        HEALTH = "health", "Health and care"
        EDUCATION = "education", "Education and training"
        DIGITAL = "digital", "Digital and technology"
        FINANCE = "finance", "Financial services"
        OTHER = "other", "Other"

    class LegalStructure(models.TextChoices):
        SOLE_PROPRIETOR = "sole_proprietor", "Sole proprietor"
        PARTNERSHIP = "partnership", "Partnership"
        LIMITED_COMPANY = "limited_company", "Limited company"
        COOPERATIVE = "cooperative", "Cooperative or group"
        COMMUNITY_ORGANIZATION = "community", "Community organization"
        OTHER = "other", "Other or not sure"

    class StaffBand(models.TextChoices):
        OWNER_ONLY = "owner_only", "Owner only"
        TWO_TO_FIVE = "2_5", "2–5 people"
        SIX_TO_TEN = "6_10", "6–10 people"
        ELEVEN_TO_TWENTY = "11_20", "11–20 people"
        TWENTY_ONE_TO_FIFTY = "21_50", "21–50 people"
        OVER_FIFTY = "over_50", "More than 50 people"

    class TurnoverBand(models.TextChoices):
        UNDER_500K = "under_500k", "Under KES 500,000"
        FROM_500K_TO_5M = "500k_5m", "KES 500,000–5 million"
        FROM_5M_TO_25M = "5m_25m", "KES 5–25 million"
        FROM_25M_TO_50M = "25m_50m", "KES 25–50 million"
        OVER_50M = "over_50m", "Over KES 50 million"
        PREFER_NOT_TO_SAY = "prefer_not", "Prefer not to say"

    class OperatingModel(models.TextChoices):
        BUSINESS_TO_CONSUMER = "b2c", "Selling to individuals"
        BUSINESS_TO_BUSINESS = "b2b", "Selling to other businesses"
        BOTH = "both", "Selling to both"
        OTHER = "other", "Other"

    class ConcentrationBand(models.TextChoices):
        UNDER_20 = "under_20", "No customer accounts for more than 20%"
        FROM_20_TO_50 = "20_50", "One customer accounts for 20–50%"
        OVER_50 = "over_50", "One customer accounts for more than 50%"
        NOT_SURE = "not_sure", "Not sure"

    class SupplierReliance(models.TextChoices):
        SINGLE_CRITICAL = "single_critical", "One supplier is hard to replace"
        FEW_OPTIONS = "few_options", "A few suppliers; switching is difficult"
        ALTERNATIVES = "alternatives", "I have alternative suppliers"
        NOT_SURE = "not_sure", "Not sure"

    class CheckStatus(models.TextChoices):
        IN_PLACE = "in_place", "Yes, in place"
        PARTLY = "partly", "Partly"
        NOT_IN_PLACE = "not_in_place", "Not yet"
        NOT_SURE = "not_sure", "Not sure"

    COUNTY_CHOICES = [
        ("Baringo", "Baringo"), ("Bomet", "Bomet"), ("Bungoma", "Bungoma"),
        ("Busia", "Busia"), ("Elgeyo-Marakwet", "Elgeyo-Marakwet"),
        ("Embu", "Embu"), ("Garissa", "Garissa"), ("Homa Bay", "Homa Bay"),
        ("Isiolo", "Isiolo"), ("Kajiado", "Kajiado"), ("Kakamega", "Kakamega"),
        ("Kericho", "Kericho"), ("Kiambu", "Kiambu"), ("Kilifi", "Kilifi"),
        ("Kirinyaga", "Kirinyaga"), ("Kisii", "Kisii"), ("Kisumu", "Kisumu"),
        ("Kitui", "Kitui"), ("Kwale", "Kwale"), ("Laikipia", "Laikipia"),
        ("Lamu", "Lamu"), ("Machakos", "Machakos"), ("Makueni", "Makueni"),
        ("Mandera", "Mandera"), ("Marsabit", "Marsabit"), ("Meru", "Meru"),
        ("Migori", "Migori"), ("Mombasa", "Mombasa"), ("Murang'a", "Murang'a"),
        ("Nairobi", "Nairobi"), ("Nakuru", "Nakuru"), ("Nandi", "Nandi"),
        ("Narok", "Narok"), ("Nyamira", "Nyamira"), ("Nyandarua", "Nyandarua"),
        ("Nyeri", "Nyeri"), ("Samburu", "Samburu"), ("Siaya", "Siaya"),
        ("Taita-Taveta", "Taita-Taveta"), ("Tana River", "Tana River"),
        ("Tharaka-Nithi", "Tharaka-Nithi"), ("Trans Nzoia", "Trans Nzoia"),
        ("Turkana", "Turkana"), ("Uasin Gishu", "Uasin Gishu"),
        ("Vihiga", "Vihiga"), ("Wajir", "Wajir"), ("West Pokot", "West Pokot"),
    ]

    CHANNEL_CHOICES = [
        ("physical", "Physical shop or market"),
        ("social", "Social media"),
        ("website", "Own website or online shop"),
        ("marketplace", "Online marketplace"),
        ("wholesale", "Wholesale or distributors"),
        ("field", "Direct or field sales"),
        ("other", "Other"),
    ]
    PAYMENT_CHOICES = [
        ("cash", "Cash"),
        ("mobile_money", "Mobile money (for example, M-Pesa)"),
        ("bank", "Bank transfer"),
        ("card", "Card"),
        ("online", "Online payment provider"),
        ("other", "Other"),
    ]

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="business_profile"
    )
    sector = models.CharField(max_length=24, choices=Sector.choices, blank=True)
    other_sector = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=32, choices=COUNTY_CHOICES, blank=True)
    legal_structure = models.CharField(
        max_length=24, choices=LegalStructure.choices, blank=True
    )
    year_started = models.PositiveSmallIntegerField(null=True, blank=True)
    staff_band = models.CharField(max_length=16, choices=StaffBand.choices, blank=True)
    annual_turnover_band = models.CharField(
        max_length=16, choices=TurnoverBand.choices, blank=True
    )
    operating_model = models.CharField(
        max_length=8, choices=OperatingModel.choices, blank=True
    )
    sales_channels = models.JSONField(default=list, blank=True)
    payment_methods = models.JSONField(default=list, blank=True)
    customer_concentration = models.CharField(
        max_length=12, choices=ConcentrationBand.choices, blank=True
    )
    supplier_reliance = models.CharField(
        max_length=20, choices=SupplierReliance.choices, blank=True
    )
    keeps_financial_records = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    separates_business_finances = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    permits_and_licences = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    has_supplier_alternatives = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    backs_up_important_records = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    has_business_continuity_plan = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    protects_digital_payments = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    has_relevant_insurance = models.CharField(
        max_length=16, choices=CheckStatus.choices, blank=True
    )
    top_concerns = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="updated_business_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def profile_completion(self):
        fields = (
            self.sector,
            self.county,
            self.legal_structure,
            self.staff_band,
            self.operating_model,
        )
        return round(sum(value not in (None, "") for value in fields) / len(fields) * 100)

    @property
    def assessment_completion(self):
        fields = (
            self.keeps_financial_records,
            self.separates_business_finances,
            self.permits_and_licences,
            self.has_supplier_alternatives,
            self.backs_up_important_records,
            self.has_business_continuity_plan,
            self.protects_digital_payments,
            self.has_relevant_insurance,
        )
        return round(sum(bool(value) for value in fields) / len(fields) * 100)

    def __str__(self):
        return f"Business profile - {self.organization}"


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
    management_transition = models.ForeignKey(
        "ManagementTransition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_assessments",
    )
    likelihood = models.PositiveSmallIntegerField()
    impact = models.PositiveSmallIntegerField()
    residual_likelihood = models.PositiveSmallIntegerField()
    residual_impact = models.PositiveSmallIntegerField()
    rationale = models.TextField(blank=True)
    assessed_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ("-assessed_at",)


class ManagementTransition(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="management_transitions"
    )
    role = models.CharField(max_length=120)
    outgoing_manager = models.CharField(max_length=160, blank=True)
    incoming_manager = models.CharField(max_length=160, blank=True)
    effective_date = models.DateField()
    context = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-effective_date", "-created_at")

    def __str__(self):
        return f"{self.role} handover - {self.organization.name}"


class ManagementTransitionRiskReview(models.Model):
    transition = models.ForeignKey(
        ManagementTransition, on_delete=models.CASCADE, related_name="reviews"
    )
    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="handover_reviews")
    assessment = models.ForeignKey(
        RiskAssessment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_reviews",
    )
    reviewed_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("assessment", "risk__reference")
        constraints = [
            models.UniqueConstraint(
                fields=("transition", "risk"),
                name="unique_risk_review_per_management_transition",
            )
        ]

    @property
    def is_complete(self):
        return self.assessment_id is not None


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
        CLIMATE = "climate", "Climate or water stress"
        SANCTIONS = "sanctions", "Sanctions"
        CURRENCY = "currency", "Currency movement"
        POLITICAL = "political", "Political disruption"
        CYBER = "cyber", "Cyber outage"
        SUPPLIER = "supplier", "Supplier failure"
        MARKET = "market", "Market or input-price shock"
        PAYMENT = "payment", "Payment or connectivity outage"
        PEOPLE = "people", "Key-person or succession change"
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


class RiskBotPolicy(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="risk_bot_policy"
    )
    enabled = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, default="KES")
    timezone = models.CharField(max_length=64, default="Africa/Nairobi")
    max_single_transaction = models.DecimalField(
        max_digits=14, decimal_places=2, default=100000
    )
    max_daily_payer_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=250000
    )
    max_daily_payer_transactions = models.PositiveIntegerField(default=20)
    linked_risk = models.ForeignKey(
        Risk, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bot_policies",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        from django.core.exceptions import ValidationError

        if self.linked_risk_id and self.linked_risk.organization_id != self.organization_id:
            raise ValidationError({"linked_risk": "The linked risk must belong to this organization."})
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError({"timezone": "Enter a valid IANA timezone."}) from exc

    def __str__(self):
        return f"Risk bot policy - {self.organization}"


class RiskBotTransaction(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="bot_transactions"
    )
    receipt_number = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    payer_phone = models.CharField(max_length=32, blank=True)
    transaction_time = models.DateTimeField()
    account_reference = models.CharField(max_length=160, blank=True)
    source = models.CharField(max_length=40, default="mpesa")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-transaction_time",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "receipt_number"),
                name="unique_bot_receipt_per_organization",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="bot_transaction_amount_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "transaction_time")),
            models.Index(fields=("organization", "payer_phone", "transaction_time")),
        ]

    def __str__(self):
        return f"{self.receipt_number} - {self.amount} {self.currency}"


class RiskBotAlert(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    class Severity(models.TextChoices):
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="bot_alerts"
    )
    transaction = models.ForeignKey(
        RiskBotTransaction, on_delete=models.CASCADE, null=True, blank=True,
        related_name="alerts",
    )
    risk = models.ForeignKey(
        Risk, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bot_alerts",
    )
    event_key = models.CharField(max_length=160)
    rule_code = models.CharField(max_length=48)
    severity = models.CharField(max_length=12, choices=Severity.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    message = models.CharField(max_length=500)
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "event_key"),
                name="unique_bot_alert_event_per_organization",
            )
        ]

    def __str__(self):
        return f"{self.rule_code} - {self.organization}"


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