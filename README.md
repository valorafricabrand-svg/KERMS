# CGS Enterprise Risk Register

CGS is an organization-aware enterprise risk-management and business intelligence platform built with Django. It supports risk registers, geopolitical and climate exposure mapping, governance, assurance, incident management, executive reporting, scenario analysis, integrations, and external risk intelligence.

## Key capabilities

### Core risk management
- Organization-specific risk registers
- Risk categories, themes, owners, enterprise functions, and strategic objectives
- Inherent and residual likelihood-and-impact scoring
- Critical, High, Medium, and Low risk ratings
- Risk lifecycle statuses and review dates
- Early-warning indicators and thresholds
- Risk treatments and action tracking

### Executive dashboard
- Open-risk, critical-risk, treatment, and geographic exposure metrics
- Residual-risk profile
- Interactive Leaflet geographic exposure map
- Organization selector and executive risk overview

### Assets and dependencies
- Business units, legal entities, and portfolios
- Assets, ownership, criticality, and risk relationships
- Suppliers and supplier concentration
- Locations and geographic information
- Asset dependencies and cascade relationships

### External risk intelligence
- RSS/feed-based intelligence ingestion
- Geopolitical, conflict, climate, cyber, supply-chain, regulatory, and financial categories
- Alert filtering and acknowledgement workflows
- Links between alerts, countries, locations, assets, portfolios, and risks
- Source status, confidence, publication, and ingestion information
- Demonstration content clearly separated from verified intelligence

### Scenario and stress testing
- Flooding, sanctions, currency, political, cyber, supplier-failure, and custom scenarios
- Scenario assumptions and expected exposure
- Direct and first-level dependency-cascade calculations
- Draft, assessed, approved, and archived workflows

### Controls and assurance
- Risk-control registration, ownership, review dates, and effectiveness
- Assurance-test creation and filtering
- Effective, partially effective, ineffective, and not-tested results
- Assurance testing history

### Incident and loss management
- Incident reference, category, lifecycle, and ownership
- Links to risks, assets, locations, and suppliers
- Gross loss, recovery, and net-loss calculations
- Root-cause analysis and lessons learned

### Governance and standards mapping
- Compliance frameworks and versions
- Regulatory framework requirements
- Risk and control-to-requirement mappings
- Compliance gaps and evidence-review tracking
- Governance committees and meeting schedules
- Policy lifecycle, ownership, approval, and review dates

### Executive and board reporting
- PDF, Word, and PowerPoint report generation
- Report templates, history, and scheduled delivery
- Board-ready narratives, trend content, action aging, and appetite reporting
- Provision for controlling the provenance of assessments, AI-generated summaries, external data, and approved management content

### Integrations and API
- REST API, webhook, file-transfer, and data-feed connection registry
- Organization-scoped API credentials
- SHA-256-hashed API token storage
- Bearer-token API access
- Webhook endpoints and event subscriptions
- Integration event audit trail
- Public API health endpoint and organization risk-summary API

### User experience and administration
- Responsive desktop and mobile navigation
- Global search with `Ctrl+K` or `Cmd+K`
- Guided forms, validation messages, empty states, and active navigation
- Organization membership and role isolation
- Django administration interface

## Local preview

### Requirements
- Python 3.12+
- Windows, Linux, or macOS
- Dependencies from `requirements.txt`

### Setup

```bash
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Configure the environment from `.env.example`, then create `.env` in the project root:

```text
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=replace_with_a_generated_secret_key
```

Initialize and start the application:

```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/. The Django administrator login and user-management interface are available at http://127.0.0.1:8000/admin/.

## Demonstration data

Representative reference and workspace data can be loaded with the included management commands. These are demonstration records, not verified external intelligence or production decisions.

```bash
python manage.py seed_reference_data
python manage.py seed_external_risk_sources
python manage.py seed_demo_external_alerts
python manage.py seed_governance_demo
python manage.py ingest_external_risk_feeds
```

## API

### Health endpoint

```text
GET /api/v1/health/
```

### Organization risk summary

```text
GET /api/v1/risks/?organization=<organization-id>
Authorization: Bearer <api-token>
```

The API credential can be generated from the **Integrations & API** workspace. Credential tokens are displayed once and are stored as a secure hash.

## Validation

Run the focused Django test suite:

```bash
python manage.py check
python manage.py test risks.tests
```

## Technology stack

- Django 5.2
- SQLite for local development
- Leaflet for geographic visualization
- ReportLab, python-docx, and python-pptx for report exports
- feedparser for external RSS intelligence
- Django authentication, membership, and administration

## Repository status

The platform is under incremental development. SQLite and console email delivery are suitable for local preview, while PostgreSQL, a persistent secret store, external authentication, production email, and hardened hosting configuration are required before operational deployment.
