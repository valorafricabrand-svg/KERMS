from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.global_search, name="global_search"),
    path("risks/", views.risk_register, name="risk_register"),
    path("risks/new/", views.risk_create, name="risk_create"),
    path("risks/<int:pk>/", views.risk_detail, name="risk_detail"),
    path("reports/", views.reports, name="reports"),
    path("reports/generate/", views.generate_board_report, name="generate_board_report"),
    path("assets/", views.assets, name="assets"),
    path("scenarios/", views.scenarios, name="scenarios"),
    path("assurance/", views.assurance, name="assurance"),
    path("incidents/", views.incidents, name="incidents"),
    path("integrations/", views.integrations, name="integrations"),
    path("api/v1/health/", views.api_health, name="api_health"),
    path("api/v1/risks/", views.api_risk_summary, name="api_risk_summary"),
    path("governance/", views.governance, name="governance"),
    path("intelligence/", views.intelligence, name="intelligence"),
    path("intelligence/<int:pk>/acknowledge/", views.acknowledge_alert, name="acknowledge_alert"),
]
