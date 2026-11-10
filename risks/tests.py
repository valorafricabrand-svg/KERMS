import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .assessment_questions import ASSESSMENT_QUESTION_KEYS
from .models import (
    ApiCredential,
    BusinessProfile,
    EntrepreneurAssessment,
    LossIncident,
    Location,
    ManagementTransition,
    ManagementTransitionRiskReview,
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
    Risk,
    RiskBotAlert,
    RiskBotPolicy,
    RiskBotTransaction,
    RiskAssessment,
    RiskTreatment,
    StressScenario,
    SubscriptionPlan,
    KermsPayment,
)


class RiskPlatformTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("analyst", "analyst@example.com", "test-password")
        self.organization = Organization.objects.create(name="Test Bank", code="TEST")
        OrganizationMembership.objects.create(
            user=self.user, organization=self.organization, role="risk_manager"
        )
        subscription = self.organization.subscription
        subscription.plan = SubscriptionPlan.objects.get(code="premium")
        subscription.status = OrganizationSubscription.Status.ACTIVE
        subscription.onboarding_fee_waived_at = timezone.now()
        subscription.onboarding_fee_waived_reason = "Test fixture"
        subscription.save()

    def assessment_answers(self, value="not_sure"):
        return {key: value for key in ASSESSMENT_QUESTION_KEYS}

    def test_billing_page_shows_onboarding_and_premium_prices(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("billing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KES 500")
        self.assertContains(response, "KES 5000")
        self.assertContains(response, "no automatic M-Pesa deductions")

    def test_unpaid_workspace_is_read_only_but_remains_visible(self):
        organization = Organization.objects.create(
            name="Unpaid Workspace", code="UNPAID"
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=organization, role="risk_manager"
        )
        self.client.force_login(self.user)
        url = f"{reverse('business_profile')}?organization={organization.pk}"

        read_response = self.client.get(url)
        write_response = self.client.post(
            url,
            {"organization": organization.pk, "sector": "retail"},
        )

        self.assertEqual(read_response.status_code, 200)
        self.assertRedirects(
            write_response, f"{reverse('billing')}?organization={organization.pk}"
        )
        self.assertFalse(BusinessProfile.objects.filter(organization=organization).exists())

    def test_starter_plan_cannot_open_premium_tools(self):
        subscription = self.organization.subscription
        subscription.plan = SubscriptionPlan.objects.get(code="starter")
        subscription.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("reports"))

        self.assertRedirects(
            response, f"{reverse('billing')}?organization={self.organization.pk}"
        )

    def test_starter_quotas_block_extra_location_and_active_risk(self):
        subscription = self.organization.subscription
        subscription.plan = SubscriptionPlan.objects.get(code="starter")
        subscription.save()
        Location.objects.create(
            organization=self.organization, name="Main shop", country="Kenya"
        )
        for index in range(5):
            Risk.objects.create(
                organization=self.organization,
                reference=f"STARTER-{index}",
                title=f"Starter risk {index}",
                description="Existing active risk.",
                risk_type=Risk.RiskType.OPERATIONAL,
            )
        self.client.force_login(self.user)

        location_response = self.client.post(
            reverse("business_locations"),
            {
                "organization": self.organization.pk,
                "action": "create",
                "name": "Second shop",
                "country": "Kenya",
                "site_type": Location.SiteType.SHOP,
            },
        )
        risk_response = self.client.post(
            reverse("risk_create"),
            {"organization": self.organization.pk},
        )

        self.assertRedirects(
            location_response, f"{reverse('billing')}?organization={self.organization.pk}"
        )
        self.assertRedirects(
            risk_response, f"{reverse('billing')}?organization={self.organization.pk}"
        )

    def test_expired_premium_is_read_only_after_grace_period(self):
        subscription = self.organization.subscription
        subscription.current_period_end = timezone.now() - timedelta(days=8)
        subscription.save()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("business_profile"),
            {"organization": self.organization.pk},
        )

        self.assertRedirects(
            response, f"{reverse('billing')}?organization={self.organization.pk}"
        )
        self.assertEqual(
            subscription.effective_status_label, "Expired — read-only"
        )

    @override_settings(
        DARAJA_CONSUMER_KEY="",
        DARAJA_CONSUMER_SECRET="",
        DARAJA_SHORTCODE="",
        DARAJA_PASSKEY="",
        DARAJA_CALLBACK_URL="",
    )
    def test_billing_uses_configured_plan_price_and_reports_missing_credentials(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("billing"),
            {
                "organization": self.organization.pk,
                "payment_type": KermsPayment.Purpose.SUBSCRIPTION,
                "plan": SubscriptionPlan.objects.get(code="premium").pk,
                "billing_cycle": OrganizationSubscription.BillingCycle.MONTHLY,
                "phone_number": "0712345678",
            },
        )

        payment = KermsPayment.objects.get(organization=self.organization)
        self.assertEqual(payment.amount, Decimal("500.00"))
        self.assertEqual(payment.status, KermsPayment.Status.FAILED)
        self.assertContains(response, "Daraja credentials and callback URL are not configured")

    def test_successful_daraja_callback_verifies_and_applies_onboarding_once(self):
        organization = Organization.objects.create(
            name="Callback Workspace", code="CALLBACK"
        )
        subscription = organization.subscription
        payment = KermsPayment.objects.create(
            organization=organization,
            subscription=subscription,
            purpose=KermsPayment.Purpose.ONBOARDING,
            amount="500.00",
            phone_number="254712345678",
            checkout_request_id="ws_CO_CALLBACK_1",
        )
        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": payment.checkout_request_id,
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 500},
                            {"Name": "MpesaReceiptNumber", "Value": "KERMS12345"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        with patch("risks.views.query_stk_push", return_value={"ResultCode": "0"}):
            response = self.client.post(
                reverse("daraja_callback"),
                data=json.dumps(callback),
                content_type="application/json",
            )
            duplicate_response = self.client.post(
                reverse("daraja_callback"),
                data=json.dumps(callback),
                content_type="application/json",
            )

        payment.refresh_from_db()
        subscription.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(payment.status, KermsPayment.Status.COMPLETED)
        self.assertEqual(payment.mpesa_receipt_number, "KERMS12345")
        self.assertTrue(subscription.onboarding_paid)
        self.assertEqual(subscription.status, OrganizationSubscription.Status.ACTIVE)

    def test_successful_annual_payment_activates_premium_for_twelve_months(self):
        organization = Organization.objects.create(
            name="Premium Workspace", code="PREMIUM"
        )
        subscription = organization.subscription
        subscription.onboarding_fee_paid_at = timezone.now()
        subscription.status = OrganizationSubscription.Status.ACTIVE
        subscription.save()
        payment = KermsPayment.objects.create(
            organization=organization,
            subscription=subscription,
            purpose=KermsPayment.Purpose.SUBSCRIPTION,
            plan=SubscriptionPlan.objects.get(code="premium"),
            billing_cycle=OrganizationSubscription.BillingCycle.ANNUAL,
            amount="5000.00",
            phone_number="254712345678",
            checkout_request_id="ws_CO_PREMIUM_1",
        )
        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": payment.checkout_request_id,
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 5000},
                            {"Name": "MpesaReceiptNumber", "Value": "KERMSA12345"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        with patch("risks.views.query_stk_push", return_value={"ResultCode": "0"}):
            response = self.client.post(
                reverse("daraja_callback"),
                data=json.dumps(callback),
                content_type="application/json",
            )

        subscription.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(subscription.plan.code, "premium")
        self.assertEqual(
            subscription.billing_cycle,
            OrganizationSubscription.BillingCycle.ANNUAL,
        )
        self.assertEqual(
            (subscription.current_period_end.year - subscription.current_period_start.year)
            * 12
            + subscription.current_period_end.month
            - subscription.current_period_start.month,
            12,
        )

    def test_daraja_callback_does_not_activate_when_server_verification_fails(self):
        organization = Organization.objects.create(
            name="Unverified Workspace", code="UNVERIFIED"
        )
        payment = KermsPayment.objects.create(
            organization=organization,
            subscription=organization.subscription,
            purpose=KermsPayment.Purpose.ONBOARDING,
            amount="500.00",
            phone_number="254712345678",
            checkout_request_id="ws_CO_CALLBACK_2",
        )
        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": payment.checkout_request_id,
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 500},
                            {"Name": "MpesaReceiptNumber", "Value": "KERMS54321"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        with patch(
            "risks.views.query_stk_push",
            return_value={"ResultCode": "1032", "ResultDesc": "Not confirmed."},
        ):
            response = self.client.post(
                reverse("daraja_callback"),
                data=json.dumps(callback),
                content_type="application/json",
            )

        organization.subscription.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(response.status_code, 503)
        self.assertFalse(organization.subscription.onboarding_paid)
        self.assertEqual(payment.status, KermsPayment.Status.PENDING)

    def test_risk_bot_api_requires_the_premium_entitlement(self):
        token = "starter-risk-bot-token"
        self.create_api_credential(self.organization, token)
        subscription = self.organization.subscription
        subscription.plan = SubscriptionPlan.objects.get(code="starter")
        subscription.save()

        response = self.client.post(
            reverse("api_bot_transactions"),
            data=json.dumps({"receipt_number": "STARTER-API"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("not included", response.json()["error"])

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
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('dashboard')}"
        )

    def test_public_home_introduces_kerms_without_exposing_workspace_data(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KERMS.CO.KE")
        self.assertContains(response, "Kenya Enterprise Risk Management System")
        self.assertContains(response, "Sign in to KERMS")
        self.assertContains(response, f"{reverse('login')}?next={reverse('dashboard')}")
        self.assertContains(response, "Show next workflow steps")
        self.assertContains(response, "Use the arrows to follow each step")
        self.assertNotContains(response, "CGS Financial Services")

    def test_branded_login_authenticates_and_returns_to_dashboard(self):
        login_url = f"{reverse('login')}?next={reverse('dashboard')}"
        page = self.client.get(login_url)

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Welcome back.")
        self.assertContains(page, "KERMS.CO.KE")

        response = self.client.post(
            login_url,
            {"username": "analyst", "password": "test-password"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_platform_logout_returns_to_public_home(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertContains(self.client.get(reverse("home")), "Sign in to KERMS")

    def test_authenticated_public_home_links_to_platform_workspace(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open your workspace")
        self.assertContains(response, reverse("dashboard"))

    def test_business_profile_requires_login(self):
        response = self.client.get(reverse("business_profile"))
        self.assertEqual(response.status_code, 302)

    def test_signup_creates_workspace_and_admin_membership(self):
        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "Ada",
                "last_name": "Mwangi",
                "username": "ada",
                "email": "ada@example.com",
                "password1": "StrongPass!123",
                "password2": "StrongPass!123",
                "organization_name": "Ada Retail Group",
                "organization_code": "ADA-RETAIL",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = get_user_model().objects.get(username="ada")
        organization = Organization.objects.get(code="ADA-RETAIL")
        membership = OrganizationMembership.objects.get(user=user, organization=organization)
        self.assertEqual(membership.role, OrganizationMembership.Role.ADMIN)
        self.assertTrue(user.check_password("StrongPass!123"))
        self.assertEqual(organization.name, "Ada Retail Group")

    def test_business_profile_is_a_guided_scoped_self_assessment(self):
        self.client.force_login(self.user)
        url = f"{reverse('business_profile')}?organization={self.organization.pk}"

        page = self.client.get(url)

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Business basics")
        self.assertContains(page, "Mobile money")
        self.assertEqual(page.context["profile_completion"], 0)
        self.assertContains(page, "Open assessment registry")
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
                "top_concerns": "Keeping the shop open during a power outage.",
            },
        )

        self.assertRedirects(response, url)
        profile = BusinessProfile.objects.get(organization=self.organization)
        self.assertEqual(profile.updated_by, self.user)
        self.assertEqual(profile.sales_channels, ["physical", "social"])
        self.assertEqual(profile.payment_methods, ["cash", "mobile_money"])
        self.assertEqual(profile.profile_completion, 100)
        self.assertFalse(EntrepreneurAssessment.objects.filter(organization=self.organization).exists())

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

    def test_assessment_registry_saves_drafts_and_submits_complete_assessments(self):
        self.client.force_login(self.user)
        url = reverse("entrepreneur_assessment_create")
        base_data = {
            "organization": self.organization.pk,
            "assessment_date": timezone.localdate().isoformat(),
            "business_context": "We are planning for the busy season.",
            "priority_actions": "Review cash needs every Friday.",
        }

        draft_response = self.client.post(
            url,
            {**base_data, "action": "save_draft"},
        )

        self.assertEqual(draft_response.status_code, 302)
        assessment = EntrepreneurAssessment.objects.get(organization=self.organization)
        self.assertEqual(assessment.status, EntrepreneurAssessment.Status.DRAFT)
        self.assertEqual(assessment.answered_count, 0)
        self.assertEqual(assessment.priority_actions, "Review cash needs every Friday.")
        self.assertEqual(assessment.created_by, self.user)

        submit_response = self.client.post(
            reverse("entrepreneur_assessment_detail", args=[assessment.pk]),
            {**base_data, **self.assessment_answers("partly"), "action": "submit"},
        )

        self.assertRedirects(
            submit_response,
            reverse("entrepreneur_assessment_detail", args=[assessment.pk]),
        )
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, EntrepreneurAssessment.Status.SUBMITTED)
        self.assertIsNotNone(assessment.submitted_at)
        self.assertEqual(assessment.answered_count, len(ASSESSMENT_QUESTION_KEYS))
        self.assertEqual(assessment.completion_percentage, 100)

    def test_assessment_submit_requires_answers_and_accepts_not_sure_as_answer(self):
        self.client.force_login(self.user)
        url = reverse("entrepreneur_assessment_create")
        data = {
            "organization": self.organization.pk,
            "assessment_date": timezone.localdate().isoformat(),
            "action": "submit",
            "financial_records": "not_sure",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Answer this question, or choose Not sure.")
        self.assertFalse(EntrepreneurAssessment.objects.exists())

    def test_assessment_registry_is_login_protected_and_viewer_is_read_only(self):
        assessment = EntrepreneurAssessment.objects.create(
            organization=self.organization,
            responses={"financial_records": "partly"},
        )
        registry_url = reverse("entrepreneur_assessments")
        detail_url = reverse("entrepreneur_assessment_detail", args=[assessment.pk])
        self.assertEqual(self.client.get(registry_url).status_code, 302)

        viewer = get_user_model().objects.create_user(
            "assessment_viewer", "assessment-viewer@example.com", "test-password"
        )
        OrganizationMembership.objects.create(
            user=viewer,
            organization=self.organization,
            role=OrganizationMembership.Role.VIEWER,
        )
        self.client.force_login(viewer)

        self.assertEqual(self.client.get(registry_url).status_code, 200)
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(
            self.client.get(
                f"{reverse('entrepreneur_assessment_create')}?organization={self.organization.pk}"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                detail_url,
                {"action": "save_draft"},
            ).status_code,
            403,
        )

    def test_assessment_review_can_link_only_risks_in_its_organization(self):
        assessment = EntrepreneurAssessment.objects.create(
            organization=self.organization,
            status=EntrepreneurAssessment.Status.SUBMITTED,
            responses=self.assessment_answers(),
        )
        own_risk = Risk.objects.create(
            organization=self.organization,
            reference="OWN-RISK",
            title="Cash shortfall",
            description="Cash may be insufficient for bills.",
            risk_type=Risk.RiskType.FINANCIAL,
        )
        other_organization = Organization.objects.create(
            name="Other Assessment Business", code="OTHERASSESS"
        )
        other_risk = Risk.objects.create(
            organization=other_organization,
            reference="OTHER-RISK",
            title="Private risk",
            description="Must not be linked across organizations.",
            risk_type=Risk.RiskType.OPERATIONAL,
        )
        self.client.force_login(self.user)
        detail_url = reverse("entrepreneur_assessment_detail", args=[assessment.pk])

        invalid_response = self.client.post(
            detail_url,
            {
                "action": "review",
                "review_notes": "Follow up next week.",
                "risk_links": [own_risk.pk, other_risk.pk],
            },
        )

        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Select a valid choice")
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, EntrepreneurAssessment.Status.SUBMITTED)
        self.assertFalse(assessment.risks.exists())

        response = self.client.post(
            detail_url,
            {
                "action": "review",
                "review_notes": "Follow up next week.",
                "risk_links": [own_risk.pk],
            },
        )

        self.assertRedirects(response, detail_url)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, EntrepreneurAssessment.Status.REVIEWED)
        self.assertEqual(assessment.reviewed_by, self.user)
        self.assertEqual(list(assessment.risks.all()), [own_risk])

    def test_assessment_records_are_organization_scoped(self):
        other_organization = Organization.objects.create(
            name="Other Assessment Workspace", code="OTHERWORK"
        )
        assessment = EntrepreneurAssessment.objects.create(
            organization=other_organization,
            responses=self.assessment_answers(),
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("entrepreneur_assessment_detail", args=[assessment.pk])
        )

        self.assertEqual(response.status_code, 404)
        registry = self.client.get(reverse("entrepreneur_assessments"))
        self.assertNotContains(registry, f"Assessment #{assessment.pk}")

    def test_dashboard_is_visible_to_member(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business risk overview")
        self.assertContains(response, "Your risk management journey")
        self.assertContains(response, "not a safety rating")
        self.assertEqual(response.context["journey_step_count"], 4)
        self.assertEqual(response.context["completed_journey_steps"], 0)
        self.assertEqual(response.context["journey_progress"], 0)
        self.assertEqual(
            response.context["next_journey_step"]["title"], "Describe your business"
        )

    def test_dashboard_journey_uses_read_only_links_for_viewers(self):
        OrganizationMembership.objects.filter(
            user=self.user, organization=self.organization
        ).update(role=OrganizationMembership.Role.VIEWER)
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_edit"])
        self.assertEqual(
            response.context["journey_steps"][2]["url"],
            f"/assessments/?organization={self.organization.pk}",
        )
        self.assertEqual(response.context["journey_steps"][3]["url"], "/risks/")

    def test_dashboard_explains_when_user_has_no_business_workspace(self):
        OrganizationMembership.objects.filter(
            user=self.user, organization=self.organization
        ).delete()
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["organization"])
        self.assertContains(response, "No business workspace yet")
        self.assertEqual(response.context["journey_step_count"], 0)

    def test_dashboard_journey_uses_business_records_not_risk_scores(self):
        BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.RETAIL,
            county="Nairobi",
            legal_structure=BusinessProfile.LegalStructure.SOLE_PROPRIETOR,
            staff_band=BusinessProfile.StaffBand.TWO_TO_FIVE,
            operating_model=BusinessProfile.OperatingModel.BUSINESS_TO_CONSUMER,
        )
        Location.objects.create(
            organization=self.organization,
            name="Nairobi shop",
            country="Kenya",
            latitude="-1.286389",
            longitude="36.817223",
        )
        Location.objects.create(
            organization=self.organization,
            name="Market stall",
            country="Kenya",
        )
        EntrepreneurAssessment.objects.create(
            organization=self.organization,
            status=EntrepreneurAssessment.Status.SUBMITTED,
            responses=self.assessment_answers(),
        )
        risk = Risk.objects.create(
            organization=self.organization,
            reference="JOURNEY-1",
            title="Supplier disruption",
            description="A supplier may not deliver on time.",
            risk_type=Risk.RiskType.OPERATIONAL,
        )
        RiskTreatment.objects.create(
            risk=risk,
            action="Identify an alternative supplier",
        )
        other_organization = Organization.objects.create(
            name="Other journey business", code="JOURNEYOTHER"
        )
        Location.objects.create(
            organization=other_organization,
            name="Other business site",
            country="Kenya",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["location_count"], 2)
        self.assertEqual(response.context["mapped_location_count"], 1)
        self.assertEqual(response.context["action_plan_count"], 1)
        self.assertEqual(
            [step["complete"] for step in response.context["journey_steps"]],
            [True, False, True, True],
        )
        self.assertEqual(response.context["journey_progress"], 75)
        self.assertEqual(
            response.context["next_journey_step"]["title"], "Map your operating sites"
        )
        self.assertContains(response, "1 mapped of 2 sites")
        self.assertNotContains(response, "Business score")

        second_site = Location.objects.get(name="Market stall")
        second_site.latitude = "-1.310000"
        second_site.longitude = "36.820000"
        second_site.save(update_fields=["latitude", "longitude"])

        complete_response = self.client.get(reverse("dashboard"))
        self.assertEqual(complete_response.context["journey_progress"], 100)
        self.assertIsNone(complete_response.context["next_journey_step"])

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

    def test_owner_dashboard_shows_business_profile_and_separate_assessment(self):
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
        assessment = EntrepreneurAssessment.objects.create(
            organization=self.organization,
            assessment_date=timezone.localdate(),
            status=EntrepreneurAssessment.Status.SUBMITTED,
            responses={
                "financial_records": "partly",
                "payment_security": "in_place",
                "customer_needs": "not_sure",
            },
            priority_actions="Keep a weekly cash-flow forecast.",
            created_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business snapshot")
        self.assertContains(response, "Assessment registry")
        self.assertContains(response, "Submitted for review")
        self.assertContains(response, "3 of 17 topics answered")
        self.assertContains(response, "Retail and shops")
        self.assertContains(response, "Nairobi")
        self.assertContains(response, "Mobile money")
        self.assertContains(response, "Partly")
        self.assertContains(response, "Keeping the shop open")
        self.assertContains(response, f"/assessments/{assessment.pk}/")
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
        other_subscription = other_organization.subscription
        other_subscription.plan = SubscriptionPlan.objects.get(code="premium")
        other_subscription.status = OrganizationSubscription.Status.ACTIVE
        other_subscription.onboarding_fee_waived_at = timezone.now()
        other_subscription.onboarding_fee_waived_reason = "Test fixture"
        other_subscription.save()
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

    def test_business_location_can_be_mapped_with_confirmed_local_factors(self):
        BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.AGRICULTURE,
        )
        self.client.force_login(self.user)
        url = f"{reverse('business_locations')}?organization={self.organization.pk}"

        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "The map only shows the pins you provide")
        self.assertContains(page, "No business sites have been mapped yet")
        self.assertContains(page, "Considerations for farming and agriculture")
        self.assertContains(page, "Water availability, dry spells, and heavy rainfall")

        response = self.client.post(
            url,
            {
                "organization": self.organization.pk,
                "name": "Kibera Market Shop",
                "site_type": Location.SiteType.SHOP,
                "address": "Near the market",
                "region": "Nairobi",
                "country": "Kenya",
                "latitude": "-1.313000",
                "longitude": "36.787000",
                "exposure_factors": ["flooding", "power_connectivity"],
                "exposure_notes": "Water entered the lane during heavy rain.",
            },
        )

        self.assertRedirects(
            response, f"{reverse('business_locations')}?organization={self.organization.pk}"
        )
        location = Location.objects.get(organization=self.organization)
        self.assertEqual(location.exposure_factors, ["flooding", "power_connectivity"])
        self.assertEqual(location.region, "Nairobi")
        self.assertEqual(str(location.latitude), "-1.313000")

        invalid_response = self.client.post(
            url,
            {
                "organization": self.organization.pk,
                "name": "Invalid coordinate site",
                "site_type": Location.SiteType.SHOP,
                "country": "Kenya",
                "latitude": "91",
                "longitude": "36",
            },
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "Latitude must be between -90 and 90")
        self.assertFalse(
            Location.objects.filter(name="Invalid coordinate site").exists()
        )

    def test_business_location_editor_is_organization_scoped_and_role_protected(self):
        other_organization = Organization.objects.create(
            name="Other Business Locations", code="OTHER-LOC"
        )
        private_location = Location.objects.create(
            organization=other_organization,
            name="Private location",
            country="Kenya",
            latitude="-1.000000",
            longitude="36.000000",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('business_locations')}?organization={other_organization.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["organization"], self.organization)
        self.assertNotContains(response, private_location.name)

        response = self.client.post(
            f"{reverse('business_locations')}?organization={self.organization.pk}",
            {
                "organization": self.organization.pk,
                "location_id": private_location.pk,
                "name": "Tampered site",
                "site_type": Location.SiteType.SHOP,
                "country": "Kenya",
                "latitude": "-1.000000",
                "longitude": "36.000000",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Location.objects.filter(name="Tampered site").exists())

    def test_business_location_viewer_cannot_add_site(self):
        viewer = get_user_model().objects.create_user(
            "location_viewer", "location-viewer@example.com", "test-password"
        )
        OrganizationMembership.objects.create(
            user=viewer,
            organization=self.organization,
            role=OrganizationMembership.Role.VIEWER,
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("business_locations"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "view-only access")
        response = self.client.post(
            reverse("business_locations"),
            {
                "organization": self.organization.pk,
                "name": "Viewer cannot add",
                "site_type": Location.SiteType.SHOP,
                "country": "Kenya",
                "latitude": "-1.000000",
                "longitude": "36.000000",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Location.objects.filter(name="Viewer cannot add").exists())

    def test_business_location_viewer_cannot_create_risk(self):
        viewer = get_user_model().objects.create_user(
            "risk_viewer", "risk-viewer@example.com", "test-password"
        )
        OrganizationMembership.objects.create(
            user=viewer,
            organization=self.organization,
            role=OrganizationMembership.Role.VIEWER,
        )
        self.client.force_login(viewer)

        response = self.client.get(
            f"{reverse('risk_create')}?organization={self.organization.pk}"
        )
        self.assertEqual(response.status_code, 403)

    def test_site_risk_link_stays_with_its_organization(self):
        location = Location.objects.create(
            organization=self.organization,
            name="Nairobi Shop",
            country="Kenya",
            region="Nairobi",
            latitude="-1.286389",
            longitude="36.817223",
        )
        other_organization = Organization.objects.create(
            name="Another Site Business", code="ANOTHER-SITE"
        )
        other_location = Location.objects.create(
            organization=other_organization,
            name="Other business site",
            country="Kenya",
            latitude="-1.200000",
            longitude="36.800000",
        )
        self.client.force_login(self.user)
        url = (
            f"{reverse('risk_create')}?organization={self.organization.pk}"
            f"&location={location.pk}"
        )

        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(
            page.context["form"].fields["location"].queryset.get(), location
        )

        response = self.client.post(
            f"{reverse('risk_create')}?organization={self.organization.pk}",
            {
                "organization": self.organization.pk,
                "reference": "SITE-RISK-1",
                "title": "Heavy rain could interrupt shop access",
                "description": "If heavy rain blocks the access road, customers may not reach the shop.",
                "risk_type": Risk.RiskType.CLIMATE,
                "location": location.pk,
                "status": Risk.Status.IDENTIFIED,
                "likelihood": 3,
                "impact": 3,
                "residual_likelihood": 2,
                "residual_impact": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        risk = Risk.objects.get(reference="SITE-RISK-1")
        self.assertEqual(risk.location, location)
        self.assertNotEqual(risk.location, other_location)

        response = self.client.post(
            f"{reverse('risk_create')}?organization={self.organization.pk}",
            {
                "organization": self.organization.pk,
                "reference": "SITE-RISK-2",
                "title": "Cross-business location attempt",
                "description": "A member must not link a site from another organization.",
                "risk_type": Risk.RiskType.OPERATIONAL,
                "location": other_location.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Risk.objects.filter(reference="SITE-RISK-2").exists())
        self.assertTrue(response.context["form"].has_error("location"))

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
        other_subscription = other_organization.subscription
        other_subscription.plan = SubscriptionPlan.objects.get(code="premium")
        other_subscription.status = OrganizationSubscription.Status.ACTIVE
        other_subscription.onboarding_fee_waived_at = timezone.now()
        other_subscription.onboarding_fee_waived_reason = "Test fixture"
        other_subscription.save()
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
