from django.contrib import admin

from .models import RiskCategory, RiskTheme


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