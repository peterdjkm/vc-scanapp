"""
Configuration settings
"""
import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE_URL = os.getenv('DATABASE_URL')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Confidence thresholds
    MIN_FIELD_CONFIDENCE = 0.70
    
    # LLM settings (Gemini)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    USE_LLM_FALLBACK = os.getenv('USE_LLM_FALLBACK', 'true').lower() == 'true'
    LLM_CONFIDENCE_THRESHOLD = float(os.getenv('LLM_CONFIDENCE_THRESHOLD', '0.95'))

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/visiting_cards_dev')

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    DATABASE_URL = os.getenv('DATABASE_URL')

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

