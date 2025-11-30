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
    
    # Skip database if SAVE_TO_DB is false or no DATABASE_URL
    if not save_to_db or not database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = None
        app.config['DATABASE_ENABLED'] = False
        print("⚠️  Database disabled (SAVE_TO_DB=false or no DATABASE_URL)")
        return
    
    # Render.io Postgres URLs start with postgres://, need to convert to postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DATABASE_ENABLED'] = True
    
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

