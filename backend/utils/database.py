"""
Database connection and initialization
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def init_db(app: Flask):
    """Initialize database connection (optional)"""
    save_to_db = os.getenv('SAVE_TO_DB', 'false').lower() == 'true'
    database_url = os.getenv('DATABASE_URL')
    
    print(f"🔍 Database initialization check:")
    print(f"   SAVE_TO_DB: {save_to_db}")
    print(f"   DATABASE_URL: {'SET' if database_url else 'NOT SET'}")
    if database_url:
        # Mask password in URL for security
        masked_url = database_url.split('@')[1] if '@' in database_url else database_url
        print(f"   DATABASE_URL (masked): ...@{masked_url}")
    
    # Skip database if SAVE_TO_DB is false or no DATABASE_URL
    if not save_to_db:
        app.config['DATABASE_ENABLED'] = False
        print("⚠️  Database disabled: SAVE_TO_DB is not 'true'")
        return
    
    if not database_url:
        app.config['DATABASE_ENABLED'] = False
        print("⚠️  Database disabled: DATABASE_URL environment variable not set")
        print("   💡 On Render.io: Link the Postgres database to this service, or set DATABASE_URL manually")
        return
    
    # Render.io Postgres URLs start with postgres://, need to convert to postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Set database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DATABASE_ENABLED'] = True
    
    # Initialize SQLAlchemy with the app
    db.init_app(app)
    
    # Create tables (with error handling)
    try:
        with app.app_context():
            db.create_all()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {str(e)}")
        print("   Continuing without database (extraction will still work)")
        app.config['DATABASE_ENABLED'] = False
        # Don't set SQLALCHEMY_DATABASE_URI to None - just leave it unset
        # This prevents the bind key error

