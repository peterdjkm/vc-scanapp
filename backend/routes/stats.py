"""
Statistics endpoints for tracking extraction accuracy
"""
from flask import Blueprint, request, jsonify, current_app
from utils.database import db
from models.contact import Contact
from models.confidence_metric import ConfidenceMetric
from sqlalchemy import func
import os

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Get extraction statistics
    
    Query params:
        user_id: Filter by user_id (default: 'default')
    """
    # Check if database is enabled
    database_enabled = current_app.config.get('DATABASE_ENABLED', False)
    if not database_enabled:
        return jsonify({
            'success': True,
            'message': 'Database disabled - statistics not available',
            'total_processed': 0,
            'average_confidence': 0,
            'field_detection_rates': {},
            'confidence_distribution': {}
        }), 200
    
    try:
        user_id = request.args.get('user_id', 'default')
        
        # Get total processed
        total_processed = Contact.query.filter_by(user_id=user_id).count()
        
        if total_processed == 0:
            return jsonify({
                'success': True,
                'total_processed': 0,
                'message': 'No contacts processed yet'
            }), 200
        
        # Get average confidence
        avg_confidence = db.session.query(
            func.avg(Contact.overall_confidence)
        ).filter_by(user_id=user_id).scalar()
        
        # Get field detection rates
        from models.extraction_result import ExtractionResult
        field_counts = db.session.query(
            ExtractionResult.field_name,
            func.count(ExtractionResult.id).label('count')
        ).join(Contact).filter(
            Contact.user_id == user_id
        ).group_by(ExtractionResult.field_name).all()
        
        total_contacts = Contact.query.filter_by(user_id=user_id).count()
        field_detection_rates = {}
        for field_name, count in field_counts:
            field_detection_rates[field_name] = round(count / total_contacts, 2)
        
        # Get confidence distribution
        confidence_ranges = {
            '>0.97': Contact.query.filter_by(user_id=user_id).filter(
                Contact.overall_confidence > 0.97
            ).count(),
            '0.95-0.97': Contact.query.filter_by(user_id=user_id).filter(
                Contact.overall_confidence >= 0.95,
                Contact.overall_confidence <= 0.97
            ).count(),
            '0.90-0.95': Contact.query.filter_by(user_id=user_id).filter(
                Contact.overall_confidence >= 0.90,
                Contact.overall_confidence < 0.95
            ).count(),
            '<0.90': Contact.query.filter_by(user_id=user_id).filter(
                Contact.overall_confidence < 0.90
            ).count()
        }
        
        return jsonify({
            'success': True,
            'total_processed': total_processed,
            'average_confidence': round(float(avg_confidence), 2) if avg_confidence else 0,
            'field_detection_rates': field_detection_rates,
            'confidence_distribution': confidence_ranges
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

