from django import forms
from .models import ReportTemplate, ReportSchedule


class ReportTemplateForm(forms.ModelForm):
    class Meta:
        model = ReportTemplate
        fields = ("name", "include_heatmap", "include_geography", "include_appetite_breaches", "include_controls_assurance", "include_action_aging", "include_ai_narrative", "management_commentary")
        widgets = {"management_commentary": forms.Textarea(attrs={"rows": 4})}


class ReportScheduleForm(forms.ModelForm):
    class Meta:
        model = ReportSchedule
        fields = ("name", "template", "frequency", "recipients", "report_format", "active", "next_run_at")
        widgets = {"recipients": forms.Textarea(attrs={"rows": 2}), "next_run_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}
