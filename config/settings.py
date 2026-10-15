"""
Réglages Django du projet TRC (إرث النخيل).

Les valeurs secrètes ou propres à chaque machine (clé secrète, base de données,
mode debug) sont lues dans le fichier `.env` (voir `.env.example`).
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# Applications

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Bibliothèques
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    # Applications TRC
    "core",
    "accounts",
    "oases",
    "farms",
    "finance",
    "inventory",
    "customers",
    "orders",
    "invoices",
    "market",
    "audit",
    "dashboard",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Fichiers de l'administration (CSS, JS) servis par le serveur lui-même en production.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Seul le site TRC (Cloudflare Pages) peut appeler l'API depuis un navigateur.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Langue de chaque requête : en-tête Accept-Language envoyé par le site (ar ou fr).
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "audit.recorder.AuditMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Base de données : PostgreSQL, adresse lue dans DATABASE_URL

DATABASES = {"default": env.db("DATABASE_URL")}


# Mots de passe

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("phone", "full_name")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# API (Django REST Framework)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.ApprovedUserJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    # Limitation des tentatives (par adresse IP)
    "DEFAULT_THROTTLE_RATES": {
        "login": env("THROTTLE_LOGIN", default="5/minute"),
        "register": env("THROTTLE_REGISTER", default="10/hour"),
    },
}


# Jetons de connexion (JWT)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    # Décision du 15/10/2026 : on reste connecté 30 jours sans retaper son mot de passe.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=30)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # last_login est mis à jour par le signal user_logged_in (voir accounts/serializers.py).
    "UPDATE_LAST_LOGIN": False,
}


# Langues : arabe par défaut, français disponible. Les messages de l'API suivent la langue
# choisie par l'utilisateur (en-tête Accept-Language) ; traductions dans locale/ar/.

LANGUAGE_CODE = "ar"
LANGUAGES = [
    ("ar", "العربية"),
    ("fr", "Français"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Nouakchott"
USE_I18N = True
USE_TZ = True


# Fichiers statiques (administration) : rassemblés par « collectstatic », servis par WhiteNoise

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Photos envoyées (oasis, variétés, profils, annonces).
# - Avec CLOUDINARY_URL (production) : stockées chez Cloudinary (offre gratuite).
# - Sans (machine locale, tests) : dossier media/.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
USE_CLOUDINARY = bool(env("CLOUDINARY_URL", default=""))
STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if USE_CLOUDINARY
            else "django.core.files.storage.FileSystemStorage"
        )
    },
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
CLOUDINARY_STORAGE = {"PREFIX": "trc"}  # dossier « trc/ » chez Cloudinary
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Site web (frontend) autorisé à appeler l'API : adresse Cloudflare Pages, puis le domaine.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")


# Documentation de l'API (Swagger) : /api/docs/
SPECTACULAR_SETTINGS = {
    "TITLE": "API TRC – إرث النخيل",
    "DESCRIPTION": (
        "API de la plateforme TRC : oasis et variétés de dattes de l'Adrar, espaces agriculteur, "
        "vendeur et agent de terrain, marché, tableau de bord. Connexion : POST /api/auth/login/ "
        "puis bouton « Authorize » avec le jeton « access »."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "OrderStatusEnum": "orders.models.OrderStatus",
        "LanguageEnum": "accounts.models.Language",
        "RoleEnum": "accounts.models.Role",
        "AccountStatusEnum": "accounts.models.AccountStatus",
        "ListingStatusEnum": "market.models.ListingStatus",
        "SelfSignupRoleEnum": [("farmer", "Agriculteur"), ("seller", "Vendeur")],
    },
}


# Production (DEBUG=False) : HTTPS obligatoire, cookies sécurisés.
if not DEBUG:  # pragma: no cover – vérifié par « manage.py check --deploy »
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Les sous-domaines de onrender.com ne sont pas à nous : pas de HSTS « includeSubDomains ».
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
