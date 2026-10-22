from django.contrib import admin

from .models import (
    EnterpriseFunction,
    ExternalStakeholder,
    RiskAppetite,
    RiskCategory,
    RiskTheme,
    StrategicObjective,
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
