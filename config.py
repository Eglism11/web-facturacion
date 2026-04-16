import os
from dotenv import load_dotenv
from importlib.util import find_spec

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Admin Login Configuration
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')

    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        # Fix for SQLAlchemy (requires postgresql:// not postgres://)
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    # Python 3.14 is commonly paired with psycopg3.
    # If the URL does not declare a driver, prefer psycopg when available.
    if DATABASE_URL and DATABASE_URL.startswith('postgresql://') and '+psycopg' not in DATABASE_URL:
        if find_spec('psycopg') is not None:
            DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///facturacion.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # For pagination
    ITEMS_PER_PAGE = 10
