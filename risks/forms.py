from django import forms
from .models import Risk, StressScenario, RiskControl, AssuranceTest, LossIncident, ComplianceFramework, FrameworkRequirement, ComplianceMapping, GovernanceCommittee, GovernancePolicy, IntegrationConnection, WebhookEndpoint


class RiskForm(forms.ModelForm):
    class Meta:
        model = Risk
        exclude = ("organization", "created_at", "updated_at")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "review_date": forms.DateInput(attrs={"type": "date"}),
            "next_review_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "reference": "e.g. CRS-2026-001",
            "title": "A concise, specific risk statement",
            "early_warning_indicator": "e.g. Exchange-rate movement exceeds limit",
            "early_warning_threshold": "e.g. USD/GBP moves beyond 1.20",
        }
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "")
            field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " form-control").strip()
        self.fields["likelihood"].help_text = "1 = rare, 5 = almost certain"
        self.fields["impact"].help_text = "1 = minor, 5 = severe"
        self.fields["residual_likelihood"].help_text = "Likelihood after controls"
        self.fields["residual_impact"].help_text = "Impact after controls"

    def clean(self):
        cleaned = super().clean()
        for field in ("likelihood", "impact", "residual_likelihood", "residual_impact"):
            value = cleaned.get(field)
            if value is not None and not 1 <= value <= 5:
                self.add_error(field, "Use a rating from 1 to 5.")
        return cleaned


class ScenarioForm(forms.ModelForm):
    class Meta:
        model = StressScenario
        fields = ("name", "scenario_type", "description", "assumptions", "severity", "expected_exposure",
                  "risks", "assets", "suppliers", "locations", "portfolios")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "assumptions": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["risks"].queryset = organization.risks.all()
            self.fields["assets"].queryset = organization.assets.all()
            self.fields["suppliers"].queryset = organization.suppliers.all()
            self.fields["locations"].queryset = organization.locations.all()
            self.fields["portfolios"].queryset = organization.portfolios.all()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class RiskControlForm(forms.ModelForm):
    class Meta:
        model = RiskControl
        fields = ("risk", "name", "description", "effective", "owner", "review_date")
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "review_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["risk"].queryset = organization.risks.all()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AssuranceTestForm(forms.ModelForm):
    class Meta:
        model = AssuranceTest
        fields = ("risk", "control", "name", "result", "tested_by", "tested_at", "notes")
        widgets = {"tested_at": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["risk"].queryset = organization.risks.all()
            self.fields["control"].queryset = RiskControl.objects.filter(risk__organization=organization)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LossIncidentForm(forms.ModelForm):
    class Meta:
        model = LossIncident
        fields = ("reference", "title", "description", "category", "status", "risk", "asset", "location",
                  "supplier", "owner", "occurred_at", "detected_at", "resolved_at", "gross_loss",
                  "recovered_amount", "root_cause", "lessons_learned")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "root_cause": forms.Textarea(attrs={"rows": 3}),
            "lessons_learned": forms.Textarea(attrs={"rows": 3}),
            "occurred_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "detected_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "resolved_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["risk"].queryset = organization.risks.all()
            self.fields["asset"].queryset = organization.assets.all()
            self.fields["location"].queryset = organization.locations.all()
            self.fields["supplier"].queryset = organization.suppliers.all()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class FrameworkForm(forms.ModelForm):
    class Meta:
        model = ComplianceFramework
        fields = ("name", "code", "version", "regulator", "description", "active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class FrameworkRequirementForm(forms.ModelForm):
    class Meta:
        model = FrameworkRequirement
        fields = ("framework", "reference", "title", "guidance", "status", "owner", "target_date")
        widgets = {"guidance": forms.Textarea(attrs={"rows": 3}), "target_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["framework"].queryset = organization.compliance_frameworks.all()


class ComplianceMappingForm(forms.ModelForm):
    class Meta:
        model = ComplianceMapping
        fields = ("requirement", "risk", "control", "mapping_type", "rationale")
        widgets = {"rationale": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["requirement"].queryset = FrameworkRequirement.objects.filter(framework__organization=organization)
            self.fields["risk"].queryset = organization.risks.all()
            self.fields["control"].queryset = RiskControl.objects.filter(risk__organization=organization)


class GovernanceCommitteeForm(forms.ModelForm):
    class Meta:
        model = GovernanceCommittee
        fields = ("name", "purpose", "chair", "meeting_frequency", "next_meeting", "active")
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3}), "next_meeting": forms.DateInput(attrs={"type": "date"})}


class GovernancePolicyForm(forms.ModelForm):
    class Meta:
        model = GovernancePolicy
        fields = ("reference", "title", "summary", "owner", "status", "approved_at", "review_date")
        widgets = {"summary": forms.Textarea(attrs={"rows": 3}), "approved_at": forms.DateInput(attrs={"type": "date"}), "review_date": forms.DateInput(attrs={"type": "date"})}


class IntegrationConnectionForm(forms.ModelForm):
    class Meta:
        model = IntegrationConnection
        fields = ("name", "connection_type", "provider", "endpoint_url", "active")


class WebhookEndpointForm(forms.ModelForm):
    class Meta:
        model = WebhookEndpoint
        fields = ("name", "target_url", "event_types", "active")
