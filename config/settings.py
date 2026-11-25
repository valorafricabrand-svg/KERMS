import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured.")

DEBUG = env_bool("DJANGO_DEBUG", False)
DB_HOST = os.getenv("DB_HOST", "").strip()
if not DEBUG and not DB_HOST:
    raise ImproperlyConfigured(
        "Production requires PostgreSQL. Set DB_HOST, DB_NAME, DB_USER, "
        "DB_PASSWORD, and DB_SSLMODE=require; SQLite is for local development only."
    )
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost" if DEBUG else "",
    ).split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]


INSTALLED_APPS = [
    "risks.apps.RisksConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "risks.billing_middleware.BillingAccessMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "risks.context_processors.feature_flags",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": (
        {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "kerms_risk_register"),
            "USER": os.getenv("DB_USER", ""),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "OPTIONS": (
                {"sslmode": os.environ["DB_SSLMODE"]}
                if os.getenv("DB_SSLMODE")
                else {}
            ),
        }
        if DB_HOST
        else {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(
                os.getenv(
                    "SQLITE_PATH",
                    str(BASE_DIR / "data" / "riskregister.sqlite3"),
                )
            ),
        }
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_STORAGE_BUCKET = os.getenv("MEDIA_STORAGE_BUCKET", "").strip()
STORAGES = {
    "default": (
        {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": MEDIA_STORAGE_BUCKET,
                "endpoint_url": os.getenv("MEDIA_STORAGE_ENDPOINT_URL") or None,
                "region_name": os.getenv("MEDIA_STORAGE_REGION") or None,
                "access_key": os.getenv("MEDIA_STORAGE_ACCESS_KEY_ID", ""),
                "secret_key": os.getenv("MEDIA_STORAGE_SECRET_ACCESS_KEY", ""),
                "default_acl": None,
                "querystring_auth": True,
                "file_overwrite": False,
            },
        }
        if MEDIA_STORAGE_BUCKET
        else {"BACKEND": "django.core.files.storage.FileSystemStorage"}
    ),
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
PUBLIC_SIGNUP_ENABLED = env_bool("DJANGO_PUBLIC_SIGNUP_ENABLED", DEBUG)

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_ADAPTER = "risks.social_adapter.SocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "risks.forms.GoogleWorkspaceSignupForm"}
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_STORE_TOKENS = False
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
GOOGLE_SIGN_IN_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
    }
}
PUBLIC_BASE_URL = os.getenv("DJANGO_PUBLIC_BASE_URL", "").rstrip("/")
AI_ONBOARDING_DEMO_ENABLED = env_bool(
    "DJANGO_AI_ONBOARDING_DEMO_ENABLED", DEBUG
)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").strip().lower()
if AI_PROVIDER not in {"gemini", "claude"}:
    raise ImproperlyConfigured(
        "AI_PROVIDER must be either 'gemini' or 'claude'."
    )
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
if AI_ONBOARDING_DEMO_ENABLED and not DEBUG:
    raise ImproperlyConfigured(
        "The synthetic AI onboarding demo must not be enabled outside development."
    )
AI_RISK_ANALYSIS_ENABLED = env_bool("DJANGO_AI_RISK_ANALYSIS_ENABLED", True)

DARAJA_ENVIRONMENT = os.getenv("DARAJA_ENVIRONMENT", "sandbox").strip().lower()
DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY", "")
DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET", "")
DARAJA_SHORTCODE = os.getenv("DARAJA_SHORTCODE", "")
DARAJA_PASSKEY = os.getenv("DARAJA_PASSKEY", "")
DARAJA_CALLBACK_URL = os.getenv("DARAJA_CALLBACK_URL", "")
DARAJA_TRANSACTION_TYPE = os.getenv(
    "DARAJA_TRANSACTION_TYPE", "CustomerPayBillOnline"
)

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND") or (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "risk-platform@localhost" if DEBUG else ""
)
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise ImproperlyConfigured(
        "Production email verification requires a real email backend."
    )
if not DEBUG and not DEFAULT_FROM_EMAIL:
    raise ImproperlyConfigured(
        "DEFAULT_FROM_EMAIL must be configured outside development."
    )
if not DEBUG and not PUBLIC_BASE_URL.startswith("https://"):
    raise ImproperlyConfigured(
        "DJANGO_PUBLIC_BASE_URL must be the public HTTPS origin outside development."
    )
if (
    not DEBUG
    and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
    and not EMAIL_HOST
):
    raise ImproperlyConfigured(
        "EMAIL_HOST must be configured for the production SMTP backend."
    )
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 3

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(
    os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}


SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", "development" if DEBUG else "production"),
        release=os.getenv("RENDER_GIT_COMMIT") or None,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=False,
        max_request_body_size="never",
    )