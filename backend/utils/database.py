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
    
    # Use psycopg v3 driver (if psycopg is installed instead of psycopg2)
    # SQLAlchemy will auto-detect psycopg, but we can explicitly use it
    if database_url.startswith('postgresql://') and 'psycopg' not in database_url:
        # Try to use psycopg v3 if available (better Python 3.13 support)
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    
    # Set database configuration BEFORE initializing SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DATABASE_ENABLED'] = False  # Set to False initially
    
    # Initialize SQLAlchemy with the app (only when we have a valid URL)
    try:
        db.init_app(app)
        
        # Test the connection by creating tables
        with app.app_context():
            db.create_all()
            # Try a simple query to verify connection works
            db.session.execute(db.text('SELECT 1'))
            db.session.commit()
        
        app.config['DATABASE_ENABLED'] = True
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {str(e)}")
        print("   Continuing without database (extraction will still work)")
        app.config['DATABASE_ENABLED'] = False
        # Keep the URI but mark as disabled - this prevents bind key errors
        # The URI stays so we can retry later if needed

