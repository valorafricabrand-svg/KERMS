from django import forms
from .models import Asset, Supplier, Portfolio, BusinessUnit, LegalEntity, AssetDependency


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
