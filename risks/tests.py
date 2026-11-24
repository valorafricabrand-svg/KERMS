import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from smtplib import SMTPException
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress
from allauth.account.utils import user_email, user_username
from allauth.core import context as allauth_context
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialLogin

from .ai_onboarding_demo import (
    AIOnboardingDemoError,
    fetch_demo_climate_context,
    generate_demo_analysis,
)
from .ai_risk_analysis import AIRiskAnalysisError, generate_business_risk_analysis
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
    SignupConsent,
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

    def test_unpaid_workspace_allows_writes_during_free_trial(self):
        organization = Organization.objects.create(
            name="Trial Workspace", code="TRIAL"
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=organization, role="risk_manager"
        )
        self.client.force_login(self.user)
        url = f"{reverse('business_profile')}?organization={organization.pk}"

        write_response = self.client.post(
            url,
            {"organization": organization.pk, "sector": "retail"},
        )

        self.assertRedirects(write_response, url)
        self.assertTrue(BusinessProfile.objects.filter(organization=organization).exists())
        self.assertFalse(organization.subscription.onboarding_paid)
        self.assertTrue(organization.subscription.in_trial_period)

    def test_unpaid_workspace_is_read_only_after_trial_expires(self):
        organization = Organization.objects.create(
            name="Unpaid Workspace", code="UNPAID"
        )
        OrganizationMembership.objects.create(
            user=self.user, organization=organization, role="risk_manager"
        )
        self.client.force_login(self.user)
        url = f"{reverse('business_profile')}?organization={organization.pk}"

        read_response = self.client.get(url)
        OrganizationSubscription.objects.filter(organization=organization).update(
            created_at=timezone.now() - timedelta(days=31)
        )
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

    @override_settings(PUBLIC_SIGNUP_ENABLED=True)
    def test_public_home_introduces_kerms_without_exposing_workspace_data(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KERMS.CO.KE")
        self.assertContains(response, "Kenya Enterprise Risk Management System")
        self.assertNotContains(response, "Sign in")
        self.assertContains(response, "Create account")
        self.assertContains(response, reverse("signup"))
        self.assertNotContains(response, f"{reverse('login')}?next={reverse('dashboard')}")
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
        self.assertNotContains(self.client.get(reverse("home")), "Sign in")

    def test_authenticated_public_home_links_to_platform_workspace(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open your workspace")
        self.assertContains(response, reverse("dashboard"))

    def test_business_profile_requires_login(self):
        response = self.client.get(reverse("business_profile"))
        self.assertEqual(response.status_code, 302)

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_signup_requires_email_verification_before_account_access(self):
        signup_page = self.client.get(reverse("signup"))
        self.assertContains(signup_page, "verify your email address")

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
                "terms_accepted": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/verification_pending.html")
        user = get_user_model().objects.get(username="ada")
        organization = Organization.objects.get(code="ADA-RETAIL")
        membership = OrganizationMembership.objects.get(user=user, organization=organization)
        self.assertEqual(membership.role, OrganizationMembership.Role.ADMIN)
        self.assertTrue(user.check_password("StrongPass!123"))
        self.assertFalse(user.is_active)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(organization.name, "Ada Retail Group")
        self.assertEqual(user.signup_consent.terms_version, "2026-11-11-v1")
        self.assertEqual(user.signup_consent.privacy_version, "2026-11-11-v1")
        self.assertEqual(len(mail.outbox), 1)

        login_attempt = self.client.post(
            reverse("login"),
            {"username": "ada", "password": "StrongPass!123"},
        )
        self.assertEqual(login_attempt.status_code, 200)
        self.assertFalse(login_attempt.wsgi_request.user.is_authenticated)

        verify_url = next(
            line.strip()
            for line in mail.outbox[0].body.splitlines()
            if "/verify-email/" in line
        )
        verify_path = urlsplit(verify_url).path
        confirmation = self.client.get(verify_path)
        self.assertEqual(confirmation.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        verified = self.client.post(verify_path)

        self.assertRedirects(verified, reverse("dashboard"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.signup_consent.verified_at)
        self.assertTrue(verified.wsgi_request.user.is_authenticated)
        reused_link = self.client.post(verify_path)
        self.assertEqual(reused_link.status_code, 400)

    @override_settings(DEBUG=True, PUBLIC_SIGNUP_ENABLED=True)
    def test_local_signup_skips_email_verification_and_logs_in(self):
        signup_page = self.client.get(reverse("signup"))
        self.assertContains(signup_page, "signed in as soon as your workspace is created")

        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "Ada",
                "last_name": "Mwangi",
                "username": "ada-local",
                "email": "ada-local@example.com",
                "password1": "StrongPass!123",
                "password2": "StrongPass!123",
                "organization_name": "Ada Local Group",
                "organization_code": "ADA-LOCAL",
                "terms_accepted": "on",
            },
        )

        user = get_user_model().objects.get(username="ada-local")
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.signup_consent.verified_at)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(mail.outbox, [])

    def test_signup_requires_terms_and_a_validated_password(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "weak-password-user",
                "email": "weak@example.com",
                "password1": "password",
                "password2": "password",
                "organization_name": "Weak Password Workspace",
                "organization_code": "WEAK-PASSWORD",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="weak-password-user").exists())
        self.assertContains(response, "This password is too common")
        self.assertContains(response, "This field is required")

    def test_signup_honeypot_discards_automated_submission(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "robot",
                "email": "robot@example.com",
                "password1": "StrongPass!123",
                "password2": "StrongPass!123",
                "organization_name": "Robot Workspace",
                "organization_code": "ROBOT",
                "terms_accepted": "on",
                "website": "filled by bot",
            },
        )

        self.assertTemplateUsed(response, "registration/verification_pending.html")
        self.assertFalse(get_user_model().objects.filter(username="robot").exists())

    def test_signup_limits_attempts_per_client_address(self):
        for _ in range(5):
            self.client.post(reverse("signup"), {}, REMOTE_ADDR="192.0.2.18")

        response = self.client.post(
            reverse("signup"), {}, REMOTE_ADDR="192.0.2.18"
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many attempts", status_code=429)

    def test_signup_limits_verification_resends_per_email(self):
        for index in range(5):
            self.client.post(
                reverse("resend_verification"),
                {"email": "target@example.com"},
                REMOTE_ADDR=f"192.0.2.{index + 1}",
            )

        response = self.client.post(
            reverse("resend_verification"),
            {"email": "target@example.com"},
            REMOTE_ADDR="192.0.2.20",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many attempts", status_code=429)

    @override_settings(PUBLIC_SIGNUP_ENABLED=False)
    def test_public_signup_can_be_disabled_for_invitation_only_deployments(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registration is by invitation")

    def test_login_page_hides_google_button_when_not_configured(self):
        response = self.client.get(reverse("login"))

        self.assertNotContains(response, "Continue with Google")

    @override_settings(GOOGLE_SIGN_IN_ENABLED=True)
    def test_login_and_signup_pages_show_google_button_when_configured(self):
        login_response = self.client.get(reverse("login"))
        signup_response = self.client.get(reverse("signup"))

        self.assertContains(login_response, "Continue with Google")
        self.assertContains(signup_response, "Continue with Google")

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APP": {"client_id": "test-client-id", "secret": "test-secret", "key": ""},
                "SCOPE": ["profile", "email"],
                "AUTH_PARAMS": {"access_type": "online"},
                "OAUTH_PKCE_ENABLED": True,
            }
        },
    )
    def test_google_login_redirects_to_google_oauth(self):
        response = self.client.get(reverse("google_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.url)

    def _complete_social_login(self, sociallogin):
        request = RequestFactory().get("/accounts/google/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.user = AnonymousUser()
        with allauth_context.request_context(request):
            response = complete_social_login(request, sociallogin)
        request.session.save()
        session = self.client.session
        for key, value in request.session.items():
            session[key] = value
        session.save()
        return response

    @override_settings(PUBLIC_SIGNUP_ENABLED=True)
    def test_google_signup_creates_workspace_for_new_user(self):
        account = SocialAccount(provider="google", uid="google-uid-new")
        user = get_user_model()()
        user_username(user, "new-google-user")
        user_email(user, "new-google-user@example.com")
        sociallogin = SocialLogin(
            user=user,
            account=account,
            email_addresses=[
                EmailAddress(email="new-google-user@example.com", verified=True, primary=True)
            ],
        )

        redirect = self._complete_social_login(sociallogin)
        self.assertEqual(redirect.status_code, 302)
        self.assertIn("signup", redirect.url)

        response = self.client.post(
            redirect.url,
            {
                "username": "new-google-user",
                "email": "new-google-user@example.com",
                "organization_name": "Google Signup Workspace",
                "organization_code": "GOOGLE-WS",
                "terms_accepted": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username="new-google-user")
        self.assertTrue(user.is_active)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        organization = Organization.objects.get(code="GOOGLE-WS")
        self.assertEqual(organization.name, "Google Signup Workspace")
        membership = OrganizationMembership.objects.get(user=user, organization=organization)
        self.assertEqual(membership.role, OrganizationMembership.Role.ADMIN)
        consent = SignupConsent.objects.get(user=user)
        self.assertIsNotNone(consent.verified_at)

    @override_settings(PUBLIC_SIGNUP_ENABLED=True)
    def test_google_login_links_to_existing_account_with_matching_email(self):
        existing_user = get_user_model().objects.create_user(
            username="existing-user",
            email="existing@example.com",
            password="StrongPass!123",
        )
        account = SocialAccount(provider="google", uid="google-uid-existing")
        user = get_user_model()()
        user_username(user, "existing-user-google")
        user_email(user, "existing@example.com")
        sociallogin = SocialLogin(
            user=user,
            account=account,
            email_addresses=[
                EmailAddress(email="existing@example.com", verified=True, primary=True)
            ],
        )

        self._complete_social_login(sociallogin)

        self.assertEqual(self.client.session.get("_auth_user_id"), str(existing_user.pk))
        self.assertTrue(
            SocialAccount.objects.filter(
                uid="google-uid-existing", user=existing_user
            ).exists()
        )
        self.assertFalse(
            get_user_model().objects.filter(username="existing-user-google").exists()
        )

    @override_settings(
        DEBUG=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    @patch("risks.views.send_mail", side_effect=SMTPException("mail unavailable"))
    def test_signup_rolls_back_account_when_verification_email_fails(self, send_mail_mock):
        with self.assertLogs("risks.views", level="ERROR"):
            response = self.client.post(
                reverse("signup"),
                {
                    "username": "mail-failure",
                    "email": "mail-failure@example.com",
                    "password1": "StrongPass!123",
                    "password2": "StrongPass!123",
                    "organization_name": "Mail Failure Workspace",
                    "organization_code": "MAIL-FAILURE",
                    "terms_accepted": "on",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "could not send a verification email")
        self.assertFalse(get_user_model().objects.filter(username="mail-failure").exists())
        self.assertFalse(Organization.objects.filter(code="MAIL-FAILURE").exists())
        send_mail_mock.assert_called_once()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_resend_verification_uses_generic_response_for_unknown_email(self):
        pending_user = get_user_model().objects.create_user(
            username="pending-user",
            email="pending@example.com",
            password="StrongPass!123",
            is_active=False,
        )
        SignupConsent.objects.create(
            user=pending_user,
            terms_version="2026-11-11-v1",
            privacy_version="2026-11-11-v1",
        )

        pending_response = self.client.post(
            reverse("resend_verification"), {"email": "pending@example.com"}
        )
        unknown_response = self.client.post(
            reverse("resend_verification"), {"email": "unknown@example.com"}
        )

        self.assertTemplateUsed(
            pending_response, "registration/verification_pending.html"
        )
        self.assertTemplateUsed(
            unknown_response, "registration/verification_pending.html"
        )
        self.assertEqual(len(mail.outbox), 1)

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
                "revenue_model": BusinessProfile.RevenueModel.ONE_OFF_SALES,
                "main_cost_drivers": ["stock_materials", "rent_premises"],
                "top_concerns": "Keeping the shop open during a power outage.",
            },
        )

        self.assertRedirects(response, url)
        profile = BusinessProfile.objects.get(organization=self.organization)
        self.assertEqual(profile.updated_by, self.user)
        self.assertEqual(profile.sales_channels, ["physical", "social"])
        self.assertEqual(profile.payment_methods, ["cash", "mobile_money"])
        self.assertEqual(profile.revenue_model, BusinessProfile.RevenueModel.ONE_OFF_SALES)
        self.assertEqual(profile.main_cost_drivers, ["stock_materials", "rent_premises"])
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
        self.assertEqual(response.context["journey_step_count"], 5)
        self.assertEqual(response.context["completed_journey_steps"], 0)
        self.assertEqual(response.context["journey_progress"], 0)
        self.assertEqual(
            response.context["next_journey_step"]["title"], "Try a quick risk check"
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
            response.context["journey_steps"][3]["url"],
            f"/assessments/?organization={self.organization.pk}",
        )
        self.assertEqual(response.context["journey_steps"][4]["url"], "/risks/")

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
        Risk.objects.create(
            organization=self.organization,
            reference="JOURNEY-AI-1",
            title="AI-suggested risk",
            description="Suggested by the quick risk check.",
            risk_type=Risk.RiskType.OPERATIONAL,
            ai_generated=True,
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
            [True, True, False, True, True],
        )
        self.assertEqual(response.context["journey_progress"], 80)
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

    @override_settings(
        DEBUG=True,
        AI_ONBOARDING_DEMO_ENABLED=True,
        GEMINI_API_KEY="demo-key",
    )
    @patch("risks.views.generate_demo_analysis")
    @patch("risks.views.fetch_demo_climate_context")
    def test_ai_onboarding_demo_uses_fictional_context_and_rate_limits(
        self, fetch_climate, generate_analysis
    ):
        self.client.force_login(self.user)
        BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.FINANCE,
            top_concerns="PRIVATE ACTUAL BUSINESS DETAILS",
        )
        climate_context = {
            "location": "Nyeri County, Kenya",
            "elevation_m": 2100,
            "period": "2001-2025",
            "months": [
                {
                    "month": "JAN",
                    "mean_temperature_c": 16.8,
                    "mean_daily_precipitation_mm": 1.5,
                }
            ],
            "source": "NASA POWER Climatology API",
        }
        analysis = {
            "business_model_summary": "A fictional sample farm.",
            "geographic_context": "Historical climate context only.",
            "scenarios": [
                {
                    "title": "Water interruption",
                    "business_impact": "Production could be delayed.",
                    "early_warning_signs": ["Water source level falls."],
                    "risk_reduction_actions": ["Track water use."],
                    "response_actions": ["Prioritize essential crops."],
                }
            ],
            "priority_actions": ["Review water storage."],
            "uncertainties": ["Local hazard exposure needs verification."],
        }
        fetch_climate.return_value = climate_context
        generate_analysis.return_value = analysis

        response = self.client.post(
            reverse("ai_onboarding_demo"), {"confirm_demo": "on"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Water interruption")
        self.assertNotContains(response, "PRIVATE ACTUAL BUSINESS DETAILS")
        fetch_climate.assert_called_once_with()
        generate_analysis.assert_called_once_with(climate_context)
        self.assertFalse(Risk.objects.filter(organization=self.organization).exists())

        limited_response = self.client.post(
            reverse("ai_onboarding_demo"), {"confirm_demo": "on"}
        )
        self.assertEqual(limited_response.status_code, 429)
        self.assertContains(limited_response, "Please wait", status_code=429)
        self.assertEqual(generate_analysis.call_count, 1)

    @override_settings(
        DEBUG=True,
        AI_ONBOARDING_DEMO_ENABLED=True,
        GEMINI_API_KEY="",
    )
    @patch("risks.views.generate_demo_analysis")
    @patch("risks.views.fetch_demo_climate_context")
    def test_ai_onboarding_demo_requires_acknowledgement_and_api_key(
        self, fetch_climate, generate_analysis
    ):
        self.client.force_login(self.user)

        response = self.client.post(reverse("ai_onboarding_demo"), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm that you understand")
        fetch_climate.assert_not_called()
        generate_analysis.assert_not_called()

        acknowledged = self.client.post(
            reverse("ai_onboarding_demo"), {"confirm_demo": "on"}
        )
        self.assertContains(acknowledged, "Set GEMINI_API_KEY")
        fetch_climate.assert_not_called()

    @override_settings(
        DEBUG=True,
        AI_ONBOARDING_DEMO_ENABLED=True,
        AI_PROVIDER="claude",
        ANTHROPIC_API_KEY="claude-test-key",
        CLAUDE_MODEL="claude-test-model",
    )
    @patch("risks.views.generate_demo_analysis")
    @patch("risks.views.fetch_demo_climate_context")
    def test_ai_onboarding_demo_uses_claude_configuration(
        self, fetch_climate, generate_analysis
    ):
        self.client.force_login(self.user)
        fetch_climate.return_value = {"location": "Nyeri County, Kenya"}
        generate_analysis.return_value = {
            "business_model_summary": "A fictional sample farm.",
            "geographic_context": "Historical climate context only.",
            "scenarios": [],
            "priority_actions": [],
            "uncertainties": [],
        }

        page = self.client.get(reverse("ai_onboarding_demo"))

        self.assertContains(page, "Anthropic commercial terms", status_code=200)
        self.assertTrue(page.context["api_key_configured"])
        self.assertEqual(page.context["model"], "claude-test-model")

        response = self.client.post(
            reverse("ai_onboarding_demo"), {"confirm_demo": "on"}
        )

        self.assertEqual(response.status_code, 200)
        fetch_climate.assert_called_once_with()
        generate_analysis.assert_called_once_with(fetch_climate.return_value)

    @override_settings(DEBUG=False, AI_ONBOARDING_DEMO_ENABLED=True)
    def test_ai_onboarding_demo_is_unavailable_outside_development(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("ai_onboarding_demo"))

        self.assertEqual(response.status_code, 404)

    @override_settings(ANTHROPIC_API_KEY="test-anthropic-key")
    @patch("risks.views.generate_business_risk_analysis")
    def test_quick_risk_check_creates_draft_risks_from_real_profile(
        self, generate_analysis
    ):
        self.client.force_login(self.user)
        generate_analysis.return_value = {
            "summary": "This retail business faces theft and supplier risks.",
            "risks": [
                {
                    "title": "Inventory theft at point of sale",
                    "description": "Small high-value stock is easy to pocket.",
                    "risk_type": "operational",
                    "likelihood": 4,
                    "impact": 3,
                    "early_warning_indicator": "Rising stock discrepancies",
                    "business_model_link": "Sector: retail",
                    "mitigations": ["Install basic CCTV", "Reconcile stock weekly"],
                }
            ],
        }

        response = self.client.post(
            reverse("quick_risk_check"),
            {
                "organization": self.organization.pk,
                "business_name": "Test Bank",
                "sector": BusinessProfile.Sector.RETAIL,
                "other_sector": "",
                "county": "Nairobi",
                "top_concerns": "Sells electronics, 3 staff.",
                "confirm_ai": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory theft at point of sale")
        generate_analysis.assert_called_once()
        business_context = generate_analysis.call_args.args[0]
        self.assertEqual(business_context["business_name"], "Test Bank")
        self.assertEqual(business_context["location"], "Nairobi County, Kenya")

        risk = Risk.objects.get(organization=self.organization)
        self.assertTrue(risk.ai_generated)
        self.assertEqual(risk.owner, self.user)
        self.assertEqual(risk.risk_type, "operational")
        self.assertEqual(risk.business_model_link, "Sector: retail")
        self.assertEqual(risk.treatments.count(), 2)

        profile = BusinessProfile.objects.get(organization=self.organization)
        self.assertEqual(profile.sector, BusinessProfile.Sector.RETAIL)
        self.assertEqual(profile.county, "Nairobi")

    @override_settings(ANTHROPIC_API_KEY="test-anthropic-key")
    @patch("risks.views.generate_business_risk_analysis")
    def test_quick_risk_check_enriches_context_from_existing_business_model(
        self, generate_analysis
    ):
        BusinessProfile.objects.create(
            organization=self.organization,
            sector=BusinessProfile.Sector.RETAIL,
            county="Nairobi",
            operating_model=BusinessProfile.OperatingModel.BUSINESS_TO_CONSUMER,
            revenue_model=BusinessProfile.RevenueModel.ONE_OFF_SALES,
            sales_channels=["physical", "social"],
            payment_methods=["mobile_money"],
            customer_concentration=BusinessProfile.ConcentrationBand.OVER_50,
            supplier_reliance=BusinessProfile.SupplierReliance.SINGLE_CRITICAL,
            main_cost_drivers=["stock_materials", "rent_premises"],
        )
        self.client.force_login(self.user)
        generate_analysis.return_value = {
            "summary": "Concentration and single-supplier risk stand out.",
            "risks": [
                {
                    "title": "Loss of the largest customer",
                    "description": "Over half of revenue depends on one customer.",
                    "risk_type": "financial",
                    "likelihood": 3,
                    "impact": 4,
                    "early_warning_indicator": "Order volume drops",
                    "business_model_link": "Customer concentration",
                    "mitigations": ["Diversify the customer base"],
                }
            ],
        }

        self.client.post(
            reverse("quick_risk_check"),
            {
                "organization": self.organization.pk,
                "business_name": "Test Bank",
                "sector": BusinessProfile.Sector.RETAIL,
                "other_sector": "",
                "county": "Nairobi",
                "top_concerns": "",
                "confirm_ai": "on",
            },
        )

        generate_analysis.assert_called_once()
        business_context = generate_analysis.call_args.args[0]
        business_model = business_context["business_model"]
        self.assertEqual(business_model["revenue_model"], "One-off product or goods sales")
        self.assertEqual(
            business_model["customer_concentration"],
            "One customer accounts for more than 50%",
        )
        self.assertEqual(
            business_model["supplier_reliance"], "One supplier is hard to replace"
        )
        self.assertIn("Rent or premises", business_model["main_cost_drivers"])
        self.assertIn("Social media", business_model["sales_channels"])

        risk = Risk.objects.get(organization=self.organization)
        self.assertEqual(risk.business_model_link, "Customer concentration")

    def test_quick_risk_check_requires_editor_role(self):
        viewer = get_user_model().objects.create_user("viewer-user", "viewer@example.com", "test-password")
        OrganizationMembership.objects.create(
            user=viewer, organization=self.organization, role="viewer"
        )
        self.client.force_login(viewer)

        response = self.client.get(
            f"{reverse('quick_risk_check')}?organization={self.organization.pk}"
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_quick_risk_check_reports_missing_api_key_without_crashing(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("quick_risk_check"),
            {
                "organization": self.organization.pk,
                "business_name": "Test Bank",
                "sector": BusinessProfile.Sector.RETAIL,
                "other_sector": "",
                "county": "Nairobi",
                "top_concerns": "",
                "confirm_ai": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not configured")
        self.assertFalse(Risk.objects.filter(organization=self.organization).exists())


class AIOnboardingDemoServiceTests(SimpleTestCase):
    @patch("risks.ai_onboarding_demo.urlopen")
    def test_climate_request_uses_fixed_demo_coordinates(self, urlopen_mock):
        parameters = {
            "T2M": {month: 16.0 for month in (
                "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
            )},
            "PRECTOTCORR": {month: 2.0 for month in (
                "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
            )},
        }
        response_payload = {
            "properties": {"parameter": parameters},
            "geometry": {"coordinates": [36.95, -0.42, 2100]},
            "header": {"range": "2001-2025"},
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            response_payload
        ).encode("utf-8")
        urlopen_mock.return_value = response

        result = fetch_demo_climate_context()

        request = urlopen_mock.call_args.args[0]
        query = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(query["latitude"], ["-0.42"])
        self.assertEqual(query["longitude"], ["36.95"])
        self.assertEqual(len(result["months"]), 12)
        self.assertEqual(result["elevation_m"], 2100.0)

    @override_settings(GEMINI_API_KEY="test-api-key")
    @patch("risks.ai_onboarding_demo.urlopen")
    def test_gemini_request_contains_only_the_fixed_sample_and_climate_data(
        self, urlopen_mock
    ):
        response_analysis = {
            "business_model_summary": "A fictional sample farm.",
            "geographic_context": "Historical climate averages only.",
            "scenarios": [
                {
                    "title": "Water interruption",
                    "business_impact": "Production could be delayed.",
                    "early_warning_signs": ["Water availability falls."],
                    "risk_reduction_actions": ["Track water use."],
                    "response_actions": ["Prioritize essential crops."],
                }
            ],
            "priority_actions": ["Review water storage."],
            "uncertainties": ["Local hazard exposure needs verification."],
        }
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(response_analysis)}]
                    }
                }
            ]
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            api_response
        ).encode("utf-8")
        urlopen_mock.return_value = response
        climate_context = {
            "location": "Nyeri County, Kenya",
            "months": [{"month": "JAN", "mean_temperature_c": 16.0}],
        }

        result = generate_demo_analysis(climate_context)

        request = urlopen_mock.call_args.args[0]
        request_headers = {
            name.lower(): value for name, value in request.header_items()
        }
        request_body = json.loads(request.data)
        prompt = json.loads(request_body["contents"][0]["parts"][0]["text"])
        self.assertEqual(request_headers["x-goog-api-key"], "test-api-key")
        self.assertNotIn("test-api-key", request.full_url)
        self.assertEqual(prompt["location"], "Nyeri County, Kenya")
        self.assertEqual(prompt["historical_climate_context"], climate_context)
        self.assertEqual(
            prompt["fictional_business"]["type"],
            "fictional small mixed vegetable farm",
        )
        self.assertEqual(result["scenarios"][0]["title"], "Water interruption")

    @override_settings(
        AI_PROVIDER="claude",
        ANTHROPIC_API_KEY="test-anthropic-key",
        CLAUDE_MODEL="claude-test-model",
    )
    @patch("risks.ai_onboarding_demo.anthropic.Anthropic")
    def test_claude_request_uses_fixed_sample_and_validates_json(
        self, anthropic_client
    ):
        response_analysis = {
            "business_model_summary": "A fictional sample farm.",
            "geographic_context": "Historical climate averages only.",
            "scenarios": [
                {
                    "title": "Water interruption",
                    "business_impact": "Production could be delayed.",
                    "early_warning_signs": ["Water availability falls."],
                    "risk_reduction_actions": ["Track water use."],
                    "response_actions": ["Prioritize essential crops."],
                }
            ],
            "priority_actions": ["Review water storage."],
            "uncertainties": ["Local hazard exposure needs verification."],
        }
        client = anthropic_client.return_value
        client.messages.create.return_value.content = [
            MagicMock(type="text", text=json.dumps(response_analysis))
        ]
        climate_context = {
            "location": "Nyeri County, Kenya",
            "months": [{"month": "JAN", "mean_temperature_c": 16.0}],
        }

        result = generate_demo_analysis(climate_context)

        anthropic_client.assert_called_once_with(
            api_key="test-anthropic-key", timeout=30
        )
        request = client.messages.create.call_args.kwargs
        self.assertEqual(request["model"], "claude-test-model")
        prompt = json.loads(request["messages"][0]["content"])
        self.assertEqual(prompt["location"], "Nyeri County, Kenya")
        self.assertEqual(prompt["historical_climate_context"], climate_context)
        self.assertEqual(result["scenarios"][0]["title"], "Water interruption")

    @override_settings(
        AI_PROVIDER="claude",
        ANTHROPIC_API_KEY="",
    )
    def test_claude_requires_its_api_key(self):
        with self.assertRaisesRegex(
            AIOnboardingDemoError, "Set ANTHROPIC_API_KEY"
        ):
            generate_demo_analysis({})


class AIRiskAnalysisServiceTests(SimpleTestCase):
    @override_settings(ANTHROPIC_API_KEY="test-anthropic-key", CLAUDE_MODEL="claude-test-model")
    @patch("risks.ai_risk_analysis.anthropic.Anthropic")
    def test_generate_business_risk_analysis_validates_and_returns_risks(
        self, anthropic_client
    ):
        response_analysis = {
            "summary": "A short retail business risk overview.",
            "risks": [
                {
                    "title": "Inventory theft",
                    "description": "Small valuable stock is easy to pocket.",
                    "risk_type": "operational",
                    "likelihood": 4,
                    "impact": 3,
                    "early_warning_indicator": "Stock discrepancies rise",
                    "business_model_link": "Revenue model: one-off sales",
                    "mitigations": ["Install CCTV", "Reconcile stock weekly"],
                }
            ],
        }
        client = anthropic_client.return_value
        client.messages.create.return_value.content = [
            MagicMock(type="text", text=json.dumps(response_analysis))
        ]
        business_context = {
            "business_name": "Test Bank",
            "business_type": "Retail and shops",
            "location": "Nairobi County, Kenya",
            "key_details": "Sells electronics, 3 staff.",
            "business_model": {
                "revenue_model": "One-off product or goods sales",
                "customer_concentration": "One customer accounts for more than 50%",
            },
        }

        result = generate_business_risk_analysis(business_context)

        anthropic_client.assert_called_once_with(
            api_key="test-anthropic-key", timeout=30
        )
        request = client.messages.create.call_args.kwargs
        self.assertEqual(request["model"], "claude-test-model")
        prompt = json.loads(request["messages"][0]["content"])
        self.assertEqual(prompt["business"], business_context)
        self.assertEqual(result["risks"][0]["title"], "Inventory theft")
        self.assertEqual(result["risks"][0]["likelihood"], 4)
        self.assertEqual(
            result["risks"][0]["business_model_link"], "Revenue model: one-off sales"
        )

    @override_settings(ANTHROPIC_API_KEY="")
    def test_generate_business_risk_analysis_requires_api_key(self):
        with self.assertRaisesRegex(
            AIRiskAnalysisError, "not configured"
        ):
            generate_business_risk_analysis({})

    @override_settings(ANTHROPIC_API_KEY="test-anthropic-key", AI_RISK_ANALYSIS_ENABLED=False)
    def test_generate_business_risk_analysis_respects_disabled_flag(self):
        with self.assertRaisesRegex(AIRiskAnalysisError, "disabled"):
            generate_business_risk_analysis({})

    @override_settings(ANTHROPIC_API_KEY="test-anthropic-key")
    @patch("risks.ai_risk_analysis.anthropic.Anthropic")
    def test_generate_business_risk_analysis_rejects_unknown_risk_type(
        self, anthropic_client
    ):
        response_analysis = {
            "summary": "Overview.",
            "risks": [
                {
                    "title": "Bad risk type",
                    "description": "Has an unsupported risk_type value.",
                    "risk_type": "not_a_real_type",
                    "likelihood": 2,
                    "impact": 2,
                    "early_warning_indicator": "",
                    "mitigations": ["Do something"],
                }
            ],
        }
        client = anthropic_client.return_value
        client.messages.create.return_value.content = [
            MagicMock(type="text", text=json.dumps(response_analysis))
        ]

        with self.assertRaisesRegex(AIRiskAnalysisError, "risk type"):
            generate_business_risk_analysis({})
