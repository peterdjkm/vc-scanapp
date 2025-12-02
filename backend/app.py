"""
Main Flask application for Visiting Card Scanner API
"""
from flask import Flask, send_from_directory
from flask_cors import CORS
from routes.process import process_bp
from routes.contacts import contacts_bp
from routes.stats import stats_bp
from utils.database import init_db
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Enable CORS for frontend

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/visiting_cards')
app.config['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Register blueprints
app.register_blueprint(process_bp, url_prefix='/api')
app.register_blueprint(contacts_bp, url_prefix='/api')
app.register_blueprint(stats_bp, url_prefix='/api')

# Initialize database (optional - can run without it)
try:
    init_db(app)
except Exception as e:
    print(f"⚠️  Database initialization skipped: {str(e)}")
    print("   API will run without database (extraction still works)")

@app.route('/')
def index():
    """Serve frontend index page"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS)"""
    return send_from_directory('../frontend', path)

@app.route('/api/health')
def health_check():
    """Health check endpoint with database status"""
    database_enabled = app.config.get('DATABASE_ENABLED', False)
    save_to_db = os.getenv('SAVE_TO_DB', 'false').lower() == 'true'
    database_url = os.getenv('DATABASE_URL')
    
    return {
        'status': 'healthy',
        'service': 'visiting-card-scanner-api',
        'version': '1.0.0',
        'database': {
            'enabled': database_enabled,
            'save_to_db_setting': save_to_db,
            'database_url_set': bool(database_url)
        }
    }

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

