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
