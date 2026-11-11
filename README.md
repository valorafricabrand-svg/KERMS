# KERMS.CO.KE — Kenya Enterprise Risk Management System

An organization-aware risk management and assessment system for Kenyan
entrepreneurs and small businesses. The Django application is the single source
of truth for business profiles, risk registers, treatments, incidents, bot
policies, transactions, and alerts. The standalone Flask M-Pesa prototype and
sample-only browser preview remain available under `riskbot/` and
`tools/preview.js` for demos; they are not the production backend.

## Local development

Requirements: Python 3.12+ (3.10+ for the standalone bot) and Windows, Linux,
or macOS.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a unique `DJANGO_SECRET_KEY` in `.env`, then run:

```powershell
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/ for the public KERMS product website and
http://127.0.0.1:8000/dashboard/ for the signed-in business workspace. Sign in
at `/login/`; workspace access is provisioned by an administrator. The `.co.ke`
name is the product identity; public DNS, TLS, hosting, and email still need to
be configured for a production deployment. The default local database is
`data/riskregister.sqlite3`. Never commit `.env`, database files, uploaded
files, or credentials.

### Render deployment

When deploying with the repository Dockerfile, configure the required Django
and PostgreSQL environment variables in Render. Connect to the database using
its internal connection details and set `DB_SSLMODE=require`. The container
startup applies database migrations, collects the static-file manifest, then
starts Gunicorn on Render's assigned `PORT` (falling back to port 10000).
Ensure Render is deploying the latest commit containing the Dockerfile change;
if the service uses Render's native Python runtime instead of Docker, configure
the equivalent build and start commands in the service settings.

Production deployments must configure a real email provider (`EMAIL_HOST`,
`DEFAULT_FROM_EMAIL`, and provider credentials as needed) and set
`DJANGO_PUBLIC_BASE_URL` to the canonical HTTPS origin used in email links.
Django refuses to start in production with the development console email
backend or without that HTTPS origin. Public workspace registration is
disabled outside development by default; enable it only after email delivery
and the policy notices have been reviewed:

```text
DJANGO_PUBLIC_SIGNUP_ENABLED=True
DJANGO_PUBLIC_BASE_URL=https://your-domain.example
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=your-provider-smtp-host
EMAIL_PORT=587
EMAIL_HOST_USER=your-provider-user
EMAIL_HOST_PASSWORD=your-provider-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=accounts@your-domain
```

## Secure account creation

When enabled, self-service registration creates an inactive account and a
workspace administrator membership, then sends a single-use email-verification
link that expires after three days. A database-backed limit allows five
registration or resend attempts per source IP and per email address per hour;
a honeypot field silently discards basic automated
submissions. Ensure the trusted ingress configures `REMOTE_ADDR` as the real
client address; KERMS intentionally does not trust a caller-supplied
`X-Forwarded-For` header. Passwords must be at least 12 characters and are
checked against Django's configured validators. Terms acceptance is required
and its version and timestamp are recorded with the account.

Production registration is invitation-only by default. Administrators can
provision users and organization memberships through Django admin. The signup
form and policies are an initial service notice, not a substitute for complete
operator contact details and legal review. Multi-factor authentication,
organization invitations, and advanced bot detection should be added before
enterprise onboarding.

## Plans, onboarding, and M-Pesa billing

New organization workspaces start on Starter in read-only mode. Members can
review the workspace and its billing page; an administrator or risk manager
must pay the one-time KES 500 onboarding fee with an M-Pesa STK prompt before
workspace changes are enabled. Starter includes 3 seats, 1 business location,
and 5 active risks. Premium is KES 500 monthly or KES 5,000 annually, with 5
seats, 5 locations, and unlimited active risks. Premium plan features and
quotas, the onboarding fee, and the default renewal grace period are editable
in Django admin. Premium renewals require a new customer-approved M-Pesa prompt
each term; they are not automatic recurring debits. After a Premium term and
its 7-day grace period, the workspace becomes read-only.

Existing organizations present when migration `0017` is applied are
grandfathered on Premium with the onboarding fee waived, preserving their
current access. Organizations created afterwards start on Starter with
onboarding due. Admins can also waive an organization's onboarding fee and
select its entitlements in the organization subscription record.

To enable Daraja STK Push, configure these values as environment secrets (for
local development, `.env` is ignored by git):

```text
DARAJA_ENVIRONMENT=sandbox
DARAJA_CONSUMER_KEY=
DARAJA_CONSUMER_SECRET=
DARAJA_SHORTCODE=
DARAJA_PASSKEY=
DARAJA_CALLBACK_URL=https://your-public-host/payments/daraja/callback/
DARAJA_TRANSACTION_TYPE=CustomerPayBillOnline
```

Use Safaricom sandbox credentials for testing. Live mode requires Safaricom
production credentials and a publicly reachable HTTPS callback URL. The
callback is treated as untrusted: KERMS checks its checkout ID, amount, phone,
and receipt, then confirms the STK result with Safaricom's server-side STK Query
endpoint before enabling access. Configure a public callback and complete
Safaricom sandbox and production verification before accepting live payments.

## Entrepreneur business profile

Signed-in members can open **Business profile** to record their sector, Kenyan
county, business size, customer and payment channels, supplier dependence, and
main concerns. Profile details are scoped to the selected
organization; administrators, risk managers, and analysts can update them,
while viewers have read-only access. Annual turnover is optional and collected
only as a broad range.

The profile is business context, not an assessment record or risk score.

## Business locations and site exposures

The **Business locations** workflow maps each shop, farm, market, workshop,
office, or other operating site to a map pin and records local conditions the
entrepreneur has observed or can verify. Approximate pins are acceptable.
Location data is limited to the member's organization; users with viewer access
cannot add or change sites. OpenStreetMap provides map tiles, so displaying the
map sends ordinary tile requests to that provider.

Site exposure checkboxes are discussion prompts, not official hazard data.
The application does not infer a flood, drought, heat, or other hazard from a
county or coordinate, and it does not calculate climate risk. Link each
confirmed exposure to a risk-register record for that site, assess its
likelihood and impact, record existing safeguards, and assign practical
treatment actions. Live or historical hazard overlays should be added only
after a suitable authoritative dataset, license, geographic coverage, update
frequency, and uncertainty communication have been verified.

Sector-specific prompts help owners consider common operational and
business-model dependencies. They are intentionally non-exhaustive and do not
replace local knowledge, a formal assessment, or professional advice. For
production map traffic, select a tile provider whose service terms and capacity
fit the deployment; the public OpenStreetMap tile service does not provide an
application-specific availability guarantee.

## Entrepreneur assessment registry

The **Entrepreneur assessments** registry stores repeatable assessment records
separately from both the business profile and risk register. Each record captures
dated responses across finances, customers and sales, operations, permits and
obligations, payment and information protection, and disruption recovery.
Answers can be saved as a draft or submitted for review. Reviewers can record
agreed follow-up and link existing risk-register items; assessments do not
automatically create risks.

Responses are categorical (“Yes, in place”, “Partly”, “Not yet”, or “Not sure”)
and are not combined into a single rating. The registry is a structured
conversation aid, not a credit decision, compliance certificate, or substitute
for professional advice. Assessment versions are recorded so the questionnaire
can evolve without conflating different question sets.

## A practical risk assessment

Use the business profile as context, then assess each material risk with the
people who understand the work. Start with a clear cause-event-impact statement,
for example: “Because we rely on one supplier, a delivery delay could stop
production and reduce this week's sales.” Consider risks across cash flow,
customers, suppliers, staff, permits, safety, equipment, operations, payments,
digital security, and weather or other local disruptions. The relevant topics
depend on the business.

For each risk:

1. Record the scenario, affected business activity, owner, and existing
   safeguards.
2. Rate likelihood and impact separately from 1 (low/rare) to 5 (high/severe).
   The system multiplies these values for a 1–25 prioritization band: 1–5 Low,
   6–11 Medium, 12–19 High, and 20–25 Critical.
3. Consider whether existing controls reduce likelihood, impact, or both, and
   record the residual ratings. Ratings support consistent discussion; they
   are not predictions or a substitute for business judgment.
4. Agree a practical treatment, responsible person, and due date. Track whether
   it is planned, in progress, complete, or blocked.
5. Set a useful early-warning indicator and review date where possible. Record
   incidents and near misses so assessments can be updated with real experience.

Reassess when the business changes, a control fails, or an incident occurs.
Prioritize actions that protect people, essential operations, cash flow, and
customer commitments. The system supports this conversation; it does not
automatically certify that a business is safe or compliant.

## Staging with PostgreSQL

The staging Compose stack runs Django behind Gunicorn and PostgreSQL. It is
for private testing on a trusted machine, not a public production deployment.
Install Docker Compose, copy `.env.example` to `.env`, generate a Django secret,
and set a strong random `DB_PASSWORD` before starting:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
docker compose up --build
```

Set the generated value as `DJANGO_SECRET_KEY` in `.env`. The compose file
requires `DB_PASSWORD`; it does not expose the database port to the host. Open
http://127.0.0.1:8000/. Create the first administrator in a separate terminal:

```powershell
docker compose exec web python manage.py createsuperuser
```

Persistent Postgres data is stored in the Compose-managed volume. Back it up
and test a restore before relying on it. Do not mount production database
files into the application source directory.

The existing local SQLite records remain in `data/riskregister.sqlite3`.
Starting Compose creates a separate, initially empty PostgreSQL database; it
does not delete or automatically copy the SQLite records. To bring a reviewed
staging snapshot across, first protect a backup, export from the local SQLite
configuration, start the Compose stack, then import:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --output data/staging-fixture.json
docker compose up --build -d
docker compose cp data/staging-fixture.json web:/tmp/staging-fixture.json
docker compose exec web python manage.py loaddata /tmp/staging-fixture.json
```

The fixture contains business records and password hashes. Keep it private,
never commit or email it, and remove it securely after validating the staging
import. It does not contain uploaded media; copy those files to the staging
media volume using a separate protected transfer and verify their permissions.
This is a staging convenience; production migrations should use a reviewed,
tested database migration and backup/restore procedure.

## Risk bot API

Create an API credential for an organization in **Integrations & API**. The
credential is displayed once; store it securely and send it as a bearer token.
Configure that organization's `RiskBotPolicy` in Django administration.

- `GET /api/v1/bot/policy/` — this credential's organization policy.
- `POST /api/v1/bot/transactions/` — ingest one payment.
- `GET /api/v1/bot/alerts/` — list explainable, organization-scoped alerts.

Example:

```json
{
  "receipt_number": "PROVIDER-RECEIPT",
  "amount": "1250.00",
  "currency": "KES",
  "payer_phone": "254700000000",
  "transaction_time": "2026-11-08T12:00:00+03:00",
  "account_reference": "ORDER-123",
  "source": "mpesa"
}
```

Repeated receipt numbers are idempotent per organization. Rule breaches create
alerts linked to the configured risk; full payer phone numbers are not included
in alert messages. This transaction-monitoring API is separate from the KERMS
onboarding and subscription billing integration described above.

## Demo-only legacy preview

```powershell
node tools/preview.js
```

Open http://127.0.0.1:4173/. This separate frontend uses sample data only. It
does not connect to Django, receive payments, or send messages. Use the Django
application at port 8000 for integrated risk-register and bot data.

## Validation and operations

```powershell
python manage.py check
python manage.py test risks.tests
python -m unittest discover -s tests -v
python manage.py check --deploy
```

Before any real production deployment: use managed PostgreSQL, a supported
HTTPS ingress/reverse proxy, production secret management, configured hosts and
CSRF origins, a real email/WhatsApp delivery service, monitored background
workers, access/audit review, rate limits, privacy and retention policies,
tested backups and restores, and tenant-isolation/security testing. Configure
TLS termination before enabling secure redirects and HSTS. A passing test suite
or local Compose stack does not by itself certify production readiness.
