import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')
    
    db_url = os.environ.get('DATABASE_URL', '')
    db_url = db_url.strip().lstrip('=').strip()
    print(f"[CONFIG] DATABASE_URL length: {len(db_url)}, starts: '{db_url[:20] if db_url else 'EMPTY'}'")
    
    if not db_url:
        raise ValueError("DATABASE_URL not set in environment")
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_PER_PAGE = 10
