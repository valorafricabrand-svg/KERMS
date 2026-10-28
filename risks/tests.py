from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Organization, OrganizationMembership, Risk


class RiskPlatformTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("analyst", "analyst@example.com", "test-password")
        self.organization = Organization.objects.create(name="Test Bank", code="TEST")
        OrganizationMembership.objects.create(
            user=self.user, organization=self.organization, role="risk_manager"
        )

    def test_residual_score_and_rating(self):
        risk = Risk.objects.create(
            organization=self.organization,
            reference="RISK-1",
            title="Currency exposure",
            description="Test risk",
            risk_type="financial",
            likelihood=4,
            impact=5,
            residual_likelihood=3,
            residual_impact=4,
        )
        self.assertEqual(risk.inherent_score, 20)
        self.assertEqual(risk.residual_score, 12)
        self.assertEqual(risk.rating, "High")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive overview")

    def test_reports_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive reporting")

    def test_intelligence_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("intelligence"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "External risk intelligence")

    def test_assurance_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("assurance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Controls & assurance")

    def test_scenarios_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("scenarios"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Scenarios & stress testing")

    def test_incidents_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("incidents"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Incident & loss management")

    def test_integrations_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("integrations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Integrations & API")

    def test_api_health_is_public(self):
        response = self.client.get(reverse("api_health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_governance_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("governance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Governance & compliance")

    def test_assets_workspace_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("assets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assets & dependencies")
