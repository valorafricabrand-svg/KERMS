from django.contrib import admin

from .models import RiskCategory


@admin.register(RiskCategory)
class RiskCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("code", "name")
    ordering = ("display_order", "name")