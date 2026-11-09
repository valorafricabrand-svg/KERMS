# CGS Risk Management

Organization-aware enterprise risk management with a payment-risk monitoring
bot. The Django application is the single source of truth for organizations,
users, risk registers, bot policies, transactions, and alerts. The standalone
Flask M-Pesa prototype and sample-only browser preview remain available under
`riskbot/` and `tools/preview.js` for backwards-compatible demos; they are not
the production backend.

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

Open http://127.0.0.1:8000/. The default local database is
`data/riskregister.sqlite3`. Never commit `.env`, database files, uploaded
files, or credentials.

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
in alert messages. The API accepts Daraja transaction field names, but a public
Daraja callback is deliberately not enabled: callbacks do not provide a
verifiable signature, so use a separately secured, trusted relay and reconcile
payments against provider records.

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
