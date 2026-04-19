import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')

    db_url = os.environ.get('DATABASE_URL', '')
    db_url = db_url.strip().lstrip('=').strip()

    if not db_url:
        raise ValueError("DATABASE_URL not set in environment")
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_PER_PAGE = 10

    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600 * 24 * 7

    USE_SESSION_FOR_NEXT = True

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')

    _anon = os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('SUPABASE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')
    _service = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

    SUPABASE_ANON_KEY = _anon
    SUPABASE_SERVICE_ROLE_KEY = _service
