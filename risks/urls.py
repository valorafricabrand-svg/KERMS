from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("", views.public_home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="home"),
        name="logout",
    ),
    path(
        "password-reset/",
        views.RateLimitedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            token_generator=views.password_reset_token_generator,
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("signup/", views.signup, name="signup"),
    path(
        "verify-email/<uidb64>/<token>/",
        views.verify_email,
        name="verify_email",
    ),
    path(
        "resend-verification/",
        views.resend_verification,
        name="resend_verification",
    ),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "ai-onboarding-demo/",
        views.ai_onboarding_demo,
        name="ai_onboarding_demo",
    ),
    path("billing/", views.billing, name="billing"),
    path("payments/daraja/callback/", views.daraja_callback, name="daraja_callback"),
    path("risk-bot/", views.risk_bot_dashboard, name="risk_bot_dashboard"),
    path("business-profile/", views.business_profile, name="business_profile"),
    path("quick-risk-check/", views.quick_risk_check, name="quick_risk_check"),
    path("locations/", views.business_locations, name="business_locations"),
    path("assessments/", views.entrepreneur_assessments, name="entrepreneur_assessments"),
    path("assessments/new/", views.entrepreneur_assessment_create, name="entrepreneur_assessment_create"),
    path("assessments/<int:pk>/", views.entrepreneur_assessment_detail, name="entrepreneur_assessment_detail"),
    path("search/", views.global_search, name="global_search"),
    path("risks/", views.risk_register, name="risk_register"),
    path("risks/new/", views.risk_create, name="risk_create"),
    path("risks/<int:pk>/", views.risk_detail, name="risk_detail"),
    path("reports/", views.reports, name="reports"),
    path("reports/generate/", views.generate_board_report, name="generate_board_report"),
    path("assets/", views.assets, name="assets"),
    path("scenarios/", views.scenarios, name="scenarios"),
    path("management/", views.management, name="management"),
    path("assurance/", views.assurance, name="assurance"),
    path("incidents/", views.incidents, name="incidents"),
    path("integrations/", views.integrations, name="integrations"),
    path("api/v1/health/", views.api_health, name="api_health"),
    path("api/v1/risks/", views.api_risk_summary, name="api_risk_summary"),
    path("api/v1/bot/policy/", views.api_bot_policy, name="api_bot_policy"),
    path("api/v1/bot/transactions/", views.api_bot_transactions, name="api_bot_transactions"),
    path("api/v1/bot/alerts/", views.api_bot_alerts, name="api_bot_alerts"),
    path("governance/", views.governance, name="governance"),
    path("intelligence/", views.intelligence, name="intelligence"),
    path("intelligence/<int:pk>/acknowledge/", views.acknowledge_alert, name="acknowledge_alert"),
]
