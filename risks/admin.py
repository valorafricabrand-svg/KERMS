from django.contrib import admin

from .models import (
    EnterpriseFunction, ExternalStakeholder, Location, Organization,
    OrganizationMembership, Risk, RiskAppetite, RiskAssessment, RiskCategory,
    RiskControl, RiskTheme, RiskTreatment, StrategicObjective,
    EntrepreneurAssessment,
    ReportTemplate, Report, ReportSchedule, AssuranceTest,
    ManagementTransition, ManagementTransitionRiskReview,
    ExternalRiskSource, ExternalRiskAlert, Asset, Portfolio,
    BusinessUnit, LegalEntity, Supplier, AssetDependency, StressScenario, ScenarioImpact, LossIncident,
    ComplianceFramework, FrameworkRequirement, ComplianceMapping, GovernanceCommittee, GovernancePolicy,
    IntegrationConnection, ApiCredential, IntegrationEvent, WebhookEndpoint,
    RiskBotPolicy, RiskBotTransaction, RiskBotAlert,
    BillingConfiguration, KermsPayment, OrganizationSubscription,
    SubscriptionPlan,
)


@admin.register(RiskCategory)
class RiskCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("code", "name")
    ordering = ("display_order", "name")


@admin.register(RiskTheme)
class RiskThemeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(EnterpriseFunction)
class EnterpriseFunctionAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(StrategicObjective)
class StrategicObjectiveAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(ExternalStakeholder)
class ExternalStakeholderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "accountable_party",
        "influence_mechanism",
    )
    search_fields = (
        "name",
        "accountable_party",
        "influence_mechanism",
    )
    ordering = ("name",)


@admin.register(RiskAppetite)
class RiskAppetiteAdmin(admin.ModelAdmin):
    list_display = ("name", "tolerance_threshold")
    search_fields = ("name", "description")
    ordering = ("tolerance_threshold", "name")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "site_type", "country", "region")
    list_filter = ("organization", "site_type", "country")
    search_fields = ("name", "address", "region")


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "risk_type", "status", "owner", "residual_score")
    list_filter = ("risk_type", "status", "location__country")
    search_fields = ("reference", "title", "description")


admin.site.register(RiskControl)
admin.site.register(RiskTreatment)
admin.site.register(RiskAssessment)
admin.site.register(ManagementTransition)
admin.site.register(ManagementTransitionRiskReview)
admin.site.register(OrganizationMembership)
admin.site.register(EntrepreneurAssessment)
admin.site.register(ReportTemplate)
admin.site.register(Report)
admin.site.register(ReportSchedule)
admin.site.register(AssuranceTest)
admin.site.register(ExternalRiskSource)
admin.site.register(ExternalRiskAlert)
admin.site.register(Asset)
admin.site.register(Portfolio)
admin.site.register(BusinessUnit)
admin.site.register(LegalEntity)
admin.site.register(Supplier)
admin.site.register(AssetDependency)
admin.site.register(StressScenario)
admin.site.register(ScenarioImpact)
admin.site.register(LossIncident)
admin.site.register(ComplianceFramework)
admin.site.register(FrameworkRequirement)
admin.site.register(ComplianceMapping)
admin.site.register(GovernanceCommittee)
admin.site.register(GovernancePolicy)
admin.site.register(IntegrationConnection)
admin.site.register(ApiCredential)
admin.site.register(IntegrationEvent)
admin.site.register(WebhookEndpoint)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "is_premium",
        "monthly_price",
        "annual_price",
        "seat_limit",
        "location_limit",
        "active_risk_limit",
    )
    list_filter = ("is_active", "is_premium")
    search_fields = ("name", "code")
    fieldsets = (
        (None, {"fields": ("code", "name", "description", "is_active", "is_premium")}),
        ("Pricing", {"fields": ("monthly_price", "annual_price")}),
        (
            "Usage limits (0 means unlimited)",
            {"fields": ("seat_limit", "location_limit", "active_risk_limit")},
        ),
        (
            "Features",
            {
                "fields": (
                    "business_profile_enabled",
                    "locations_enabled",
                    "assessments_enabled",
                    "risk_register_enabled",
                    "incidents_enabled",
                    "reports_enabled",
                    "assets_enabled",
                    "scenarios_enabled",
                    "management_enabled",
                    "assurance_enabled",
                    "governance_enabled",
                    "intelligence_enabled",
                    "integrations_enabled",
                    "risk_bot_enabled",
                )
            },
        ),
    )
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrganizationSubscription)
class OrganizationSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "plan",
        "status",
        "billing_cycle",
        "onboarding_paid",
        "current_period_end",
    )
    list_filter = ("plan", "status", "billing_cycle")
    search_fields = ("organization__name", "organization__code")
    autocomplete_fields = ("organization", "plan", "onboarding_fee_waived_by")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(KermsPayment)
class KermsPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "purpose",
        "amount",
        "status",
        "mpesa_receipt_number",
        "created_at",
    )
    list_filter = ("purpose", "status", "billing_cycle")
    search_fields = (
        "organization__name",
        "organization__code",
        "phone_number",
        "mpesa_receipt_number",
        "checkout_request_id",
    )
    readonly_fields = tuple(field.name for field in KermsPayment._meta.fields)
    autocomplete_fields = ("organization", "subscription", "plan", "initiated_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BillingConfiguration)
class BillingConfigurationAdmin(admin.ModelAdmin):
    list_display = ("onboarding_fee", "default_grace_period_days", "updated_at")
    readonly_fields = ("updated_by", "updated_at")

    def has_add_permission(self, request):
        return not BillingConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RiskBotPolicy)
class RiskBotPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "enabled",
        "currency",
        "timezone",
        "max_single_transaction",
        "max_daily_payer_total",
        "max_daily_payer_transactions",
    )
    list_filter = ("enabled", "currency")
    search_fields = ("organization__name", "organization__code")


@admin.register(RiskBotTransaction)
class RiskBotTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "receipt_number",
        "amount",
        "currency",
        "payer_phone",
        "transaction_time",
        "source",
    )
    list_filter = ("organization", "currency", "source")
    search_fields = ("receipt_number", "payer_phone", "account_reference")
    readonly_fields = ("received_at",)


@admin.register(RiskBotAlert)
class RiskBotAlertAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "rule_code",
        "severity",
        "status",
        "risk",
        "created_at",
    )
    list_filter = ("organization", "severity", "status", "rule_code")
    search_fields = ("message", "event_key", "risk__reference", "risk__title")
    readonly_fields = ("created_at", "updated_at")
