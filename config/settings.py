from pathlib import Path
import os
PUMP_ENVIRONMENT = os.environ.get('PUMP_ENVIRONMENT', 'local')
ALLOW_SYNTHETIC_DATA = os.environ.get('PUMP_ALLOW_SYNTHETIC_DATA', '') == '1'
BASE_DIR = Path(__file__).resolve().parent.parent
# Local learning project only. Replace this and harden settings before deployment.
SECRET_KEY = os.environ.get('PUMP_SECRET_KEY', 'local-learning-only-hpcl-pump-do-not-deploy')
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]', '192.168.1.27']
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth',
    'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles', 'pump.apps.PumpConfig']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'pump.interface_language.InterfaceLocaleMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'pump' / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': [
    'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages', 'pump.context_processors.station']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.environ.get('PUMP_DB_PATH', BASE_DIR / 'db.sqlite3')}}
AUTH_PASSWORD_VALIDATORS = [
 {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
 {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'en'
LANGUAGES = [('en', 'English'), ('hi', 'हिन्दी')]
LANGUAGE_COOKIE_NAME = 'pump_language'
LOCALE_PATHS = [BASE_DIR / 'locale']
FORM_RENDERER = 'pump.interface_language.LocalizedFormRenderer'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'organisations'
LOGOUT_REDIRECT_URL = 'login'

# Each station runs against its own database and Docker volume.
STATION_NAME = os.environ.get('STATION_NAME', 'Pandey Petrol Pump')
STATION_CODE = os.environ.get('STATION_CODE', 'station1')
SESSION_COOKIE_NAME = 'pump_' + STATION_CODE + '_session'
CSRF_COOKIE_NAME = 'pump_' + STATION_CODE + '_csrf'
import json
STATION_LINKS = json.loads(os.environ.get('STATION_LINKS', '[]'))

OWNER_SUMMARY_PEER_URL = os.environ.get('OWNER_SUMMARY_PEER_URL', '')

PORTAL_URL = os.environ.get('PORTAL_URL', 'http://127.0.0.1:8000')
FORCE_SCRIPT_NAME = '/station2' if STATION_CODE == 'station2' else None
STATIC_URL = '/static/'
MIDDLEWARE += ['pump.organisations.PortalMiddleware']

MIDDLEWARE += ['pump.access.StationRoleMiddleware']

# AI is optional and restricted to the isolated local Docker service.
LOCAL_AI_URL = os.environ.get('LOCAL_AI_URL', '')
LOCAL_AI_MODEL = os.environ.get('LOCAL_AI_MODEL', 'qwen3:1.7b')
