import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from datetime import date
from collections import OrderedDict

from .assessment_questions import ASSESSMENT_QUESTION_KEYS, ASSESSMENT_SECTIONS, RESPONSE_CHOICES
from .models import BusinessProfile, EntrepreneurAssessment, Location, Risk, StressScenario, RiskControl, AssuranceTest, LossIncident, ComplianceFramework, FrameworkRequirement, ComplianceMapping, GovernanceCommittee, GovernancePolicy, IntegrationConnection, WebhookEndpoint, ManagementTransition, Organization


class SignUpForm(forms.Form):
    first_name = forms.CharField(
        max_length=30,
        required=False,
        label="First name",
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        label="Last name",
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        label="Password",
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        label="Confirm password",
    )
    organization_name = forms.CharField(max_length=160, label="Business workspace name")
    organization_code = forms.CharField(max_length=20, label="Workspace code")
    terms_accepted = forms.BooleanField(required=True)
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(
            attrs={"tabindex": "-1", "autocomplete": "off", "class": "signup-honeypot"}
        ),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username:
            raise forms.ValidationError("Choose a username.")
        if username.lower() == "admin":
            raise forms.ValidationError("This username is reserved.")
        return username

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_organization_code(self):
        code = self.cleaned_data["organization_code"].strip()
        if not code:
            raise forms.ValidationError("Enter a short workspace code.")
        normalized = re.sub(r"[^A-Za-z0-9_-]", "", code).upper()
        if normalized != code.upper():
            raise forms.ValidationError("Use letters, numbers, hyphens, or underscores only.")
        if Organization.objects.filter(code__iexact=normalized).exists():
            raise forms.ValidationError("This workspace code is already in use.")
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")

        username = cleaned_data.get("username")
        email = cleaned_data.get("email")
        if username and email and password1:
            User = get_user_model()
            user = User(
                username=username,
                email=email,
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password1, user=user)
            except ValidationError as error:
                self.add_error("password1", error)

        organization_name = cleaned_data.get("organization_name")
        if organization_name and Organization.objects.filter(name__iexact=organization_name.strip()).exists():
            self.add_error("organization_name", "This workspace name is already in use.")

        return cleaned_data


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(label="Email address")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class BusinessProfileForm(forms.ModelForm):
    sales_channels = forms.MultipleChoiceField(
        choices=BusinessProfile.CHANNEL_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Where do you reach or sell to customers?",
    )
    payment_methods = forms.MultipleChoiceField(
        choices=BusinessProfile.PAYMENT_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="How do customers pay you?",
    )

    class Meta:
        model = BusinessProfile
        fields = (
            "sector",
            "other_sector",
            "county",
            "legal_structure",
            "year_started",
            "staff_band",
            "annual_turnover_band",
            "operating_model",
            "sales_channels",
            "payment_methods",
            "customer_concentration",
            "supplier_reliance",
            "top_concerns",
        )
        widgets = {
            "year_started": forms.NumberInput(attrs={"min": 1800}),
            "top_concerns": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "What is the one thing most likely to disrupt your business?",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial.setdefault("sales_channels", self.instance.sales_channels)
            self.initial.setdefault("payment_methods", self.instance.payment_methods)
        self.fields["other_sector"].required = False
        self.fields["other_sector"].label = "Your business sector"
        self.fields["other_sector"].help_text = "Fill this in if you selected Other."
        self.fields["year_started"].required = False
        self.fields["year_started"].help_text = "Optional. Use the year trading began."
        self.fields["annual_turnover_band"].required = False
        self.fields["annual_turnover_band"].help_text = (
            "Optional estimate only. No exact figures are collected."
        )
        self.fields["top_concerns"].required = False
        self.fields["top_concerns"].label = "What worries you most?"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        for name in ("sales_channels", "payment_methods"):
            self.fields[name].widget.attrs["class"] = "profile-checkboxes"

    def clean_year_started(self):
        year_started = self.cleaned_data.get("year_started")
        if year_started and year_started > date.today().year:
            raise forms.ValidationError("The year trading began cannot be in the future.")
        return year_started

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("sector") == BusinessProfile.Sector.OTHER and not cleaned.get(
            "other_sector"
        ):
            self.add_error("other_sector", "Tell us what kind of business you run.")
        return cleaned


class EntrepreneurAssessmentForm(forms.ModelForm):
    class Meta:
        model = EntrepreneurAssessment
        fields = ("assessment_date", "business_context", "priority_actions")
        widgets = {
            "assessment_date": forms.DateInput(attrs={"type": "date"}),
            "business_context": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "What has changed, or what should the reviewer know?",
                }
            ),
            "priority_actions": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "What is the first practical step you want to take?",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        question_fields = OrderedDict()
        for section in ASSESSMENT_SECTIONS:
            for question_key, question_text in section["questions"]:
                question_fields[question_key] = forms.ChoiceField(
                    label=question_text,
                    choices=RESPONSE_CHOICES,
                    required=False,
                    widget=forms.RadioSelect(attrs={"class": "assessment-radio-list"}),
                )
                if self.instance and self.instance.pk:
                    question_fields[question_key].initial = self.instance.responses.get(
                        question_key, ""
                    )

        ordered_fields = OrderedDict()
        ordered_fields["assessment_date"] = self.fields["assessment_date"]
        ordered_fields.update(question_fields)
        ordered_fields["business_context"] = self.fields["business_context"]
        ordered_fields["priority_actions"] = self.fields["priority_actions"]
        self.fields = ordered_fields

    def clean_assessment_date(self):
        assessment_date = self.cleaned_data["assessment_date"]
        if assessment_date > date.today():
            raise forms.ValidationError("The assessment date cannot be in the future.")
        return assessment_date

    def unanswered_questions(self):
        return [
            key
            for key in ASSESSMENT_QUESTION_KEYS
            if not self.cleaned_data.get(key)
        ]

    def assessment_responses(self):
        return {
            key: self.cleaned_data.get(key, "")
            for key in ASSESSMENT_QUESTION_KEYS
            if self.cleaned_data.get(key)
        }


class EntrepreneurAssessmentReviewForm(forms.ModelForm):
    risk_links = forms.ModelMultipleChoiceField(
        queryset=Risk.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Link existing risk-register items",
        help_text="Link relevant existing risks; assessment answers remain separate.",
    )

    class Meta:
        model = EntrepreneurAssessment
        fields = ("review_notes", "risk_links")
        widgets = {
            "review_notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Summarize what was agreed, what needs clarification, and who will follow up.",
                }
            )
        }


class RiskForm(forms.ModelForm):
    class Meta:
        model = Risk
        exclude = ("organization", "created_at", "updated_at")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "review_date": forms.DateInput(attrs={"type": "date"}),
            "next_review_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["location"].queryset = organization.locations.all()
        else:
            self.fields["location"].queryset = Location.objects.none()
        placeholders = {
            "reference": "e.g. RISK-2026-001",
            "title": "A concise, specific risk statement",
            "early_warning_indicator": "e.g. Exchange-rate movement exceeds limit",
            "early_warning_threshold": "e.g. USD/GBP moves beyond 1.20",
        }
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs["placeholder"] = placeholder
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "")
            field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " form-control").strip()
        self.fields["description"].help_text = (
            "Describe the cause, what might happen, and its effect on money, "
            "people, customers, or operations."
        )
        self.fields["likelihood"].help_text = "Chance: 1 = rare, 5 = almost certain"
        self.fields["impact"].help_text = "Consequence: 1 = minor, 5 = severe"
        self.fields["residual_likelihood"].help_text = (
            "Likelihood after considering existing safeguards."
        )
        self.fields["residual_impact"].help_text = (
            "Impact after considering existing safeguards."
        )

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


class ManagementTransitionForm(forms.ModelForm):
    class Meta:
        model = ManagementTransition
        fields = (
            "role",
            "outgoing_manager",
            "incoming_manager",
            "effective_date",
            "context",
        )
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "context": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Handover context, key changes, or decisions to revisit",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ManagementRiskAssessmentForm(forms.Form):
    likelihood = forms.IntegerField(min_value=1, max_value=5)
    impact = forms.IntegerField(min_value=1, max_value=5)
    residual_likelihood = forms.IntegerField(min_value=1, max_value=5)
    residual_impact = forms.IntegerField(min_value=1, max_value=5)
    rationale = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "What changed, what evidence was reviewed, and why?",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rating_choices = [(value, str(value)) for value in range(1, 6)]
        for name in (
            "likelihood",
            "impact",
            "residual_likelihood",
            "residual_impact",
        ):
            self.fields[name].widget = forms.Select(choices=rating_choices)
            self.fields[name].widget.attrs["class"] = "form-control"
        self.fields["rationale"].widget.attrs["class"] = "form-control"
