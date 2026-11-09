import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    ApiCredential,
    BusinessProfile,
    LossIncident,
    ManagementTransition,
    ManagementTransitionRiskReview,
    Organization,
    OrganizationMembership,
    Risk,
    RiskBotAlert,
    RiskBotPolicy,
    RiskBotTransaction,
    RiskAssessment,
    RiskTreatment,
    StressScenario,
)


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

    def test_business_profile_requires_login(self):
        response = self.client.get(reverse("business_profile"))
        self.assertEqual(response.status_code, 302)

    def test_business_profile_is_a_guided_scoped_self_assessment(self):
        self.client.force_login(self.user)
        url = f"{reverse('business_profile')}?organization={self.organization.pk}"

        page = self.client.get(url)

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Business basics")
        self.assertContains(page, "How prepared do you feel?")
        self.assertContains(page, "Mobile money")
        self.assertEqual(page.context["profile_completion"], 0)
        self.assertEqual(page.context["assessment_completion"], 0)
        self.assertFalse(BusinessProfile.objects.exists())

        response = self.client.post(
            url,
            {
                "sector": BusinessProfile.Sector.RETAIL,
                "county": "Nairobi",
                "legal_structure": BusinessProfile.LegalStructure.SOLE_PROPRIETOR,
                "year_started": "2022",
                "staff_band": BusinessProfile.StaffBand.TWO_TO_FIVE,
                "annual_turnover_band": BusinessProfile.TurnoverBand.PREFER_NOT_TO_SAY,
                "operating_model": BusinessProfile.OperatingModel.BUSINESS_TO_CONSUMER,
                "sales_channels": ["physical", "social"],
                "payment_methods": ["cash", "mobile_money"],
                "customer_concentration": BusinessProfile.ConcentrationBand.NOT_SURE,
                "supplier_reliance": BusinessProfile.SupplierReliance.FEW_OPTIONS,
                "keeps_financial_records": BusinessProfile.CheckStatus.PARTLY,
                "separates_business_finances": BusinessProfile.CheckStatus.IN_PLACE,
                "permits_and_licences": BusinessProfile.CheckStatus.NOT_SURE,
                "has_supplier_alternatives": BusinessProfile.CheckStatus.PARTLY,
                "backs_up_important_records": BusinessProfile.CheckStatus.NOT_IN_PLACE,
                "has_business_continuity_plan": BusinessProfile.CheckStatus.NOT_SURE,
                "protects_digital_payments": BusinessProfile.CheckStatus.IN_PLACE,
                "has_relevant_insurance": BusinessProfile.CheckStatus.NOT_SURE,
                "top_concerns": "Keeping the shop open during a power outage.",
            },
        )

        self.assertRedirects(response, url)
        profile = BusinessProfile.objects.get(organization=self.organization)
        self.assertEqual(profile.updated_by, self.user)
        self.assertEqual(profile.sales_channels, ["physical", "social"])
        self.assertEqual(profile.payment_methods, ["cash", "mobile_money"])
        self.assertEqual(profile.profile_completion, 100)
        self.assertEqual(profile.assessment_completion, 100)

    def test_business_profile_viewer_can_read_but_not_change_profile(self):
        profile = BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.AGRICULTURE,
            county="Nakuru",
        )
        viewer = get_user_model().objects.create_user(
            "profile_viewer", "profile-viewer@example.com", "test-password"
        )
        OrganizationMembership.objects.create(
            user=viewer,
            organization=self.organization,
            role=OrganizationMembership.Role.VIEWER,
        )
        self.client.force_login(viewer)
        url = f"{reverse('business_profile')}?organization={self.organization.pk}"

        page = self.client.get(url)

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "View only")
        self.assertTrue(page.context["form"].fields["sector"].disabled)
        response = self.client.post(
            url,
            {"sector": BusinessProfile.Sector.FINANCE, "county": "Nairobi"},
        )
        self.assertEqual(response.status_code, 403)
        profile.refresh_from_db()
        self.assertEqual(profile.sector, BusinessProfile.Sector.AGRICULTURE)

    def test_business_profile_does_not_expose_another_organization(self):
        other_organization = Organization.objects.create(
            name="Other Business", code="OTHER"
        )
        BusinessProfile.objects.create(
            organization=other_organization,
            sector=BusinessProfile.Sector.FINANCE,
            county="Mombasa",
            top_concerns="Private details for another business",
        )
        BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.RETAIL,
            county="Nairobi",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('business_profile')}?organization={other_organization.pk}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["organization"], self.organization)
        self.assertEqual(response.context["profile"].sector, BusinessProfile.Sector.RETAIL)
        self.assertNotContains(response, "Private details for another business")

    def test_business_profile_rejects_future_year_and_requires_other_sector_detail(self):
        self.client.force_login(self.user)
        url = f"{reverse('business_profile')}?organization={self.organization.pk}"
        response = self.client.post(
            url,
            {
                "sector": BusinessProfile.Sector.OTHER,
                "county": "Nairobi",
                "legal_structure": BusinessProfile.LegalStructure.OTHER,
                "year_started": "2999",
                "staff_band": BusinessProfile.StaffBand.OWNER_ONLY,
                "operating_model": BusinessProfile.OperatingModel.OTHER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot be in the future")
        self.assertContains(response, "Tell us what kind of business you run")
        self.assertFalse(BusinessProfile.objects.exists())

    def test_dashboard_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business health")
        self.assertContains(response, "Your daily check-in")
        self.assertContains(response, "Make this dashboard yours")

    def test_owner_dashboard_summarizes_only_current_business_actions(self):
        urgent_risk = Risk.objects.create(
            organization=self.organization,
            reference="OWNER-1",
            title="Key supplier disruption",
            description="A key supplier may stop deliveries.",
            risk_type=Risk.RiskType.OPERATIONAL,
            residual_likelihood=4,
            residual_impact=4,
        )
        Risk.objects.create(
            organization=self.organization,
            reference="OWNER-CLOSED",
            title="Resolved issue",
            description="No longer active.",
            risk_type=Risk.RiskType.OPERATIONAL,
            status=Risk.Status.CLOSED,
        )
        overdue_risk = Risk.objects.create(
            organization=self.organization,
            reference="OWNER-2",
            title="Payment reconciliation",
            description="Reconcile payment records.",
            risk_type=Risk.RiskType.FINANCIAL,
        )
        RiskTreatment.objects.create(
            risk=overdue_risk,
            action="Check yesterday's payment settlements",
            status=RiskTreatment.Status.IN_PROGRESS,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        RiskBotAlert.objects.create(
            organization=self.organization,
            risk=urgent_risk,
            event_key="owner-dashboard-payment-alert",
            rule_code="single_transaction_limit",
            severity=RiskBotAlert.Severity.HIGH,
            message="A payment exceeded the configured limit.",
            evidence={"amount": "50000.00"},
        )
        LossIncident.objects.create(
            organization=self.organization,
            reference="INC-OWNER-1",
            title="Supplier delivery interruption",
            description="A scheduled delivery was missed.",
            occurred_at=timezone.now(),
        )
        other_organization = Organization.objects.create(
            name="Unrelated Business", code="UNRELATED"
        )
        Risk.objects.create(
            organization=other_organization,
            reference="PRIVATE-OWNER",
            title="Private business risk",
            description="Must not leak into dashboard.",
            risk_type=Risk.RiskType.FINANCIAL,
            residual_likelihood=5,
            residual_impact=5,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_risk_count"], 2)
        self.assertEqual(response.context["priority_risk_count"], 1)
        self.assertEqual(response.context["overdue_action_count"], 1)
        self.assertEqual(response.context["new_bot_alert_count"], 1)
        self.assertEqual(response.context["open_incident_count"], 1)
        self.assertContains(response, "Key supplier disruption")
        self.assertContains(response, "Check yesterday&#x27;s payment settlements")
        self.assertContains(response, "Supplier delivery interruption")
        self.assertNotContains(response, "Private business risk")

    def test_owner_dashboard_shows_business_profile_and_preparedness_without_scoring(self):
        BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.RETAIL,
            county="Nairobi",
            legal_structure=BusinessProfile.LegalStructure.SOLE_PROPRIETOR,
            year_started=2021,
            staff_band=BusinessProfile.StaffBand.TWO_TO_FIVE,
            annual_turnover_band=BusinessProfile.TurnoverBand.PREFER_NOT_TO_SAY,
            operating_model=BusinessProfile.OperatingModel.BUSINESS_TO_CONSUMER,
            sales_channels=["physical", "social"],
            payment_methods=["cash", "mobile_money"],
            customer_concentration=BusinessProfile.ConcentrationBand.NOT_SURE,
            supplier_reliance=BusinessProfile.SupplierReliance.FEW_OPTIONS,
            keeps_financial_records=BusinessProfile.CheckStatus.PARTLY,
            protects_digital_payments=BusinessProfile.CheckStatus.IN_PLACE,
            top_concerns="Keeping the shop open during a power outage.",
        )
        other_organization = Organization.objects.create(
            name="Private Profile Business", code="PRIVATEPROFILE"
        )
        BusinessProfile.objects.create(
            organization=other_organization,
            sector=BusinessProfile.Sector.FINANCE,
            top_concerns="Private organization information",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business snapshot")
        self.assertContains(response, "Retail and shops")
        self.assertContains(response, "Nairobi")
        self.assertContains(response, "Mobile money")
        self.assertContains(response, "Partly")
        self.assertContains(response, "Keeping the shop open")
        self.assertContains(response, "not an automated risk score")
        self.assertNotContains(response, "Private organization information")

    def test_risk_bot_dashboard_is_login_protected(self):
        response = self.client.get(reverse("risk_bot_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_risk_bot_dashboard_shows_only_member_organization_data(self):
        other_organization = Organization.objects.create(
            name="Other Bot Workspace", code="BOTSECOND"
        )
        RiskBotPolicy.objects.create(
            organization=self.organization,
            max_single_transaction="1200.00",
            linked_risk=Risk.objects.create(
                organization=self.organization,
                reference="PAYMENT-1",
                title="Payment monitoring risk",
                description="Monitor unusual payments.",
                risk_type=Risk.RiskType.FINANCIAL,
            ),
        )
        RiskBotPolicy.objects.create(
            organization=other_organization,
            max_single_transaction="999999.00",
        )
        RiskBotTransaction.objects.create(
            organization=self.organization,
            receipt_number="PREVIEW-1",
            amount="250.00",
            payer_phone="254712345678",
            transaction_time="2026-11-08T12:00:00+03:00",
        )
        RiskBotTransaction.objects.create(
            organization=other_organization,
            receipt_number="PRIVATE-1",
            amount="800.00",
            transaction_time="2026-11-08T12:00:00+03:00",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("risk_bot_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Risk monitoring bot")
        self.assertContains(response, "PAYMENT-1")
        self.assertContains(response, "PREVIEW-1")
        self.assertContains(response, "5678")
        self.assertNotContains(response, "254712345678")
        self.assertNotContains(response, "PRIVATE-1")

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
        self.assertEqual(response.json()["service"], "Kenya ERM API")

    def test_risk_form_explains_small_business_risk_assessment(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("risk_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cause, what might happen")
        self.assertContains(response, "If our only supplier is delayed")
        self.assertContains(response, "Likelihood × impact")
        self.assertContains(response, "RISK-2026-001")

    def create_api_credential(self, organization, token):
        return ApiCredential.objects.create(
            organization=organization,
            name="Bot integration",
            token_prefix=token[:12],
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
        )

    def test_risk_bot_ingestion_creates_explainable_organization_alert(self):
        token = "test-risk-bot-token"
        self.create_api_credential(self.organization, token)
        risk = Risk.objects.create(
            organization=self.organization,
            reference="PAY-1",
            title="Unusual payment activity",
            description="Monitor unusual payer totals.",
            risk_type=Risk.RiskType.FINANCIAL,
        )
        RiskBotPolicy.objects.create(
            organization=self.organization,
            max_single_transaction="10000.00",
            max_daily_payer_total="100.00",
            max_daily_payer_transactions=10,
            linked_risk=risk,
        )
        response = self.client.post(
            reverse("api_bot_transactions"),
            data={
                "receipt_number": "RISKBOT-1",
                "amount": "150.00",
                "currency": "KES",
                "payer_phone": "254712345678",
                "transaction_time": "2026-11-08T12:00:00+03:00",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["alerts_created"], 1)
        alert = RiskBotAlert.objects.get()
        self.assertEqual(alert.organization, self.organization)
        self.assertEqual(alert.risk, risk)
        self.assertEqual(alert.rule_code, "daily_payer_total_limit")
        self.assertEqual(alert.evidence["daily_total"], "150.00")
        self.assertNotIn("254712345678", alert.message)
        self.assertEqual(RiskBotTransaction.objects.count(), 1)

    def test_risk_bot_ingestion_is_idempotent_and_requires_a_token(self):
        token = "another-risk-bot-token"
        self.create_api_credential(self.organization, token)
        body = {
            "receipt_number": "DUP-1",
            "amount": "20.00",
            "transaction_time": "2026-11-08T12:00:00+03:00",
        }
        endpoint = reverse("api_bot_transactions")
        self.assertEqual(
            self.client.post(endpoint, body, content_type="application/json").status_code,
            401,
        )
        first = self.client.post(
            endpoint,
            body,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        duplicate = self.client.post(
            endpoint,
            {**body, "amount": "999.00"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(RiskBotTransaction.objects.get().amount, 20)

    def test_risk_bot_credentials_are_scoped_to_their_organization(self):
        other_organization = Organization.objects.create(
            name="Other Bot Tenant", code="BOTOTHER"
        )
        own_token = "organization-a-token"
        other_token = "organization-b-token"
        self.create_api_credential(self.organization, own_token)
        self.create_api_credential(other_organization, other_token)
        endpoint = reverse("api_bot_transactions")
        for token, receipt in (
            (own_token, "ORG-A-1"),
            (other_token, "ORG-B-1"),
        ):
            response = self.client.post(
                endpoint,
                {
                    "receipt_number": receipt,
                    "amount": "10",
                    "transaction_time": "2026-11-08T12:00:00+03:00",
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(
                RiskBotTransaction.objects.values_list(
                    "organization__code", flat=True
                )
            ),
            {"TEST", "BOTOTHER"},
        )

    def test_risk_bot_rejects_naive_transaction_timestamps(self):
        token = "timezone-required-token"
        self.create_api_credential(self.organization, token)
        response = self.client.post(
            reverse("api_bot_transactions"),
            {
                "receipt_number": "NO-TZ",
                "amount": "10",
                "transaction_time": "2026-11-08T12:00:00",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(RiskBotTransaction.objects.exists())

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

    def test_management_handover_queues_and_records_open_risk_reviews(self):
        open_risk = Risk.objects.create(
            organization=self.organization,
            reference="RISK-OPEN",
            title="Seasonal supply disruption",
            description="A current risk that needs reassessment.",
            risk_type="operational",
        )
        Risk.objects.create(
            organization=self.organization,
            reference="RISK-CLOSED",
            title="Resolved exposure",
            description="A closed risk is not queued.",
            risk_type="operational",
            status=Risk.Status.CLOSED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"{reverse('management')}?organization={self.organization.pk}",
            {
                "action": "create_transition",
                "role": "Operations manager",
                "outgoing_manager": "Previous manager",
                "incoming_manager": "New manager",
                "effective_date": "2026-11-01",
                "context": "Review suppliers and continuity plans.",
            },
        )
        self.assertEqual(response.status_code, 302)
        transition = ManagementTransition.objects.get(organization=self.organization)
        review = ManagementTransitionRiskReview.objects.get(transition=transition)
        self.assertEqual(review.risk, open_risk)
        self.assertFalse(review.is_complete)
        self.assertEqual(ManagementTransitionRiskReview.objects.filter(transition=transition).count(), 1)

        response = self.client.post(
            f"{reverse('management')}?organization={self.organization.pk}&transition={transition.pk}",
            {
                "action": "complete_review",
                "transition": str(transition.pk),
                "review": str(review.pk),
                "likelihood": "4",
                "impact": "4",
                "residual_likelihood": "3",
                "residual_impact": "4",
                "rationale": "The successor confirmed the supplier concentration remains.",
            },
        )
        self.assertEqual(response.status_code, 302)
        review.refresh_from_db()
        open_risk.refresh_from_db()
        self.assertTrue(review.is_complete)
        self.assertEqual(review.assessment.management_transition, transition)
        self.assertEqual(open_risk.residual_score, 12)
        self.assertEqual(RiskAssessment.objects.filter(risk=open_risk).count(), 1)

    def test_management_review_cannot_select_another_organizations_risk(self):
        other_organization = Organization.objects.create(
            name="Other Enterprise", code="OTHER"
        )
        other_risk = Risk.objects.create(
            organization=other_organization,
            reference="OTHER-1",
            title="Private risk",
            description="Must remain outside the member workspace.",
            risk_type="financial",
        )
        other_transition = ManagementTransition.objects.create(
            organization=other_organization,
            role="Owner",
            effective_date="2026-11-01",
        )
        other_review = ManagementTransitionRiskReview.objects.create(
            transition=other_transition, risk=other_risk
        )
        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('management')}?organization={self.organization.pk}"
            f"&transition={other_transition.pk}&review={other_review.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Private risk")
        self.assertIsNone(response.context["selected_review"])

    def test_viewer_cannot_create_management_transition(self):
        viewer = get_user_model().objects.create_user(
            "viewer", "viewer@example.com", "test-password"
        )
        OrganizationMembership.objects.create(
            user=viewer, organization=self.organization, role="viewer"
        )
        self.client.force_login(viewer)

        response = self.client.post(
            f"{reverse('management')}?organization={self.organization.pk}",
            {
                "action": "create_transition",
                "role": "Owner",
                "effective_date": "2026-11-01",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ManagementTransition.objects.filter(organization=self.organization).exists()
        )

    def test_scenario_library_prefills_a_draft_without_saving_it(self):
        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('scenarios')}?organization={self.organization.pk}"
            "&template=dry-season"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not forecasts")
        self.assertContains(response, "Extended dry spell or water shortage")
        self.assertEqual(response.context["form"].initial["scenario_type"], "climate")
        self.assertFalse(StressScenario.objects.filter(organization=self.organization).exists())

    def test_scenario_creation_keeps_selected_organization(self):
        other_organization = Organization.objects.create(
            name="Second Enterprise", code="SECOND"
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=other_organization, role="risk_manager"
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"{reverse('scenarios')}?organization={other_organization.pk}",
            {
                "action": "create",
                "name": "Mobile money outage",
                "scenario_type": "payment",
                "description": "Payments are unavailable for a work day.",
                "assumptions": "Use local sales history.",
                "severity": "3",
                "expected_exposure": "25000.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        scenario = StressScenario.objects.get(name="Mobile money outage")
        self.assertEqual(scenario.organization, other_organization)
