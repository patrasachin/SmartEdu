import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Tiny .env reader (KEY=value per line) so VS Code users can keep their API key in a file."""
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))


_load_dotenv(BASE_DIR / '.env')

# --- Core -------------------------------------------------------------------
# For a real deployment set these as environment variables.
SECRET_KEY = os.environ.get('SMARTEDU_SECRET_KEY', 'django-insecure-smartedu-dev-key-change-in-prod')
DEBUG = os.environ.get('SMARTEDU_DEBUG', '1') == '1'
ALLOWED_HOSTS = ['*'] if DEBUG else os.environ.get('SMARTEDU_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # SmartEdu apps
    'apps.accounts',
    'apps.admin_portal',
    'apps.teacher',
    'apps.student',
    'apps.exams',
    'apps.attendance',
    'apps.performance',
    'apps.notifications',
    'apps.proctoring',
    'apps.materials',
    'apps.assignments',
    'apps.reattempt',
]
X_FRAME_OPTIONS = 'SAMEORIGIN'
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.notifications.context_processors.notifications',
                'apps.accounts.context_processors.departments',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # non-file form data

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Bootstrap alert class names
from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {message_constants.ERROR: 'danger'}

# --- SmartEdu settings -----------------------------------------------------------
AI_THRESHOLD_FAIL = 70               # students below this % are highlighted
AI_PROCTORING_MAX_VIOLATIONS = 3     # third violation cancels the exam
PROCTORING_FACE_CHECK = True         # needs opencv-python-headless; skipped quietly if missing
PROCTORING_FRAME_INTERVAL = 10       # seconds between webcam snapshots
PROCTORING_FACE_MISS_LIMIT = 3       # consecutive snapshots without a face = 1 violation
PROCTORING_ALLOW_NO_CAMERA = False   # camera access is required for every exam
MATERIAL_MAX_MB = 25                 # biggest study-material upload
DEFAULT_PASSWORD = 'SmartEdu@123'
TEACHER_LIMIT_TO_OWN_DEPARTMENT = False   # True: teachers can only send work to the department they were registered in
ASSIGNMENT_MAX_MB = 15               # biggest assignment upload
PROOF_MAX_MB = 10                    # biggest proof file for a re-attempt request

# --- Email to guardians (exam results and attendance) -----------------------------
# Without SMARTEDU_EMAIL_HOST the emails are printed in the terminal (and logged in Admin > Guardian emails).
# To really send them, copy .env.example to .env and fill in your SMTP details.
EMAIL_HOST = os.environ.get('SMARTEDU_EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('SMARTEDU_EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('SMARTEDU_EMAIL_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('SMARTEDU_EMAIL_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('SMARTEDU_EMAIL_TLS', '1') == '1'
EMAIL_TIMEOUT = 10
EMAIL_BACKEND = ('django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST
                 else 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('SMARTEDU_FROM_EMAIL', 'SmartEdu <no-reply@smartedu.local>')
