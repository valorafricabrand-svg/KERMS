from django import forms
from .models import (
    Asset,
    AssetDependency,
    BusinessUnit,
    LegalEntity,
    Location,
    Portfolio,
    Supplier,
)


class LocationForm(forms.ModelForm):
    exposure_factors = forms.MultipleChoiceField(
        choices=Location.EXPOSURE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Local conditions you have observed or know apply",
        help_text=(
            "These are your observations, not hazards detected by the map. "
            "Select only factors relevant to this site."
        ),
    )

    class Meta:
        model = Location
        fields = (
            "name",
            "site_type",
            "address",
            "region",
            "country",
            "latitude",
            "longitude",
            "exposure_factors",
            "exposure_notes",
        )
        labels = {
            "name": "Site name",
            "site_type": "Kind of business site",
            "address": "Street, market, village, or nearby landmark",
            "region": "County or area",
            "country": "Country",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "exposure_notes": "Other local conditions or context",
        }
        widgets = {
            "latitude": forms.NumberInput(
                attrs={"step": "0.000001", "min": "-90", "max": "90"}
            ),
            "longitude": forms.NumberInput(
                attrs={"step": "0.000001", "min": "-180", "max": "180"}
            ),
            "exposure_notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional: describe local conditions you have observed.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["latitude"].required = True
        self.fields["longitude"].required = True
        self.fields["latitude"].help_text = "Set this by clicking the map; an approximate point is okay."
        self.fields["longitude"].help_text = "Set this by clicking the map; an approximate point is okay."
        self.fields["latitude"].widget.attrs["placeholder"] = "-1.286389"
        self.fields["longitude"].widget.attrs["placeholder"] = "36.817223"
        if self.instance and self.instance.pk:
            self.initial["exposure_factors"] = self.instance.exposure_factors
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["exposure_factors"].widget.attrs["class"] = "location-exposure-options"

    def clean(self):
        cleaned = super().clean()
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if (latitude is None) != (longitude is None):
            raise forms.ValidationError(
                "Choose a point on the map or enter both coordinates."
            )
        if latitude is not None and not -90 <= latitude <= 90:
            self.add_error("latitude", "Latitude must be between -90 and 90.")
        if longitude is not None and not -180 <= longitude <= 180:
            self.add_error("longitude", "Longitude must be between -180 and 180.")
        return cleaned


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ("name", "location", "portfolio", "business_unit", "legal_entity", "asset_type", "criticality", "owner", "risks")


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("name", "country", "supplier_type", "criticality")


class DependencyForm(forms.ModelForm):
    class Meta:
        model = AssetDependency
        fields = ("source_asset", "target_asset", "supplier", "dependency_type", "criticality", "description")
