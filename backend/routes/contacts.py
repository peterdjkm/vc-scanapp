"""
Contacts endpoints
"""
from flask import Blueprint, request, jsonify, current_app
import uuid
from utils.database import db
from models.contact import Contact
from utils.duplicate_detector import is_duplicate, find_duplicates
import os

contacts_bp = Blueprint('contacts', __name__)

@contacts_bp.route('/contacts', methods=['GET'])
def get_contacts():
    """
    Get all contacts
    
    Query params:
        user_id: Filter by user_id (default: 'default')
        limit: Limit results (default: 100)
        offset: Offset for pagination (default: 0)
    """
    # Check if database is enabled
    database_enabled = current_app.config.get('DATABASE_ENABLED', False)
    if not database_enabled:
        return jsonify({
            'success': True,
            'message': 'Database disabled - contacts not available',
            'contacts': [],
            'total': 0,
            'limit': 100,
            'offset': 0
        }), 200
    
    try:
        user_id = request.args.get('user_id', 'default')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Query contacts
        query = Contact.query.filter_by(user_id=user_id)
        total = query.count()
        
        contacts = query.order_by(Contact.created_at.desc()).limit(limit).offset(offset).all()
        
        return jsonify({
            'success': True,
            'contacts': [contact.to_dict() for contact in contacts],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@contacts_bp.route('/contacts/<contact_id>', methods=['GET'])
def get_contact(contact_id):
    """Get specific contact by ID"""
    # Check if database is enabled
    database_enabled = current_app.config.get('DATABASE_ENABLED', False)
    if not database_enabled:
        return jsonify({
            'success': False,
            'error': 'Database disabled - contacts not available'
        }), 503
    
    try:
        contact = Contact.query.get(contact_id)
        
        if not contact:
            return jsonify({
                'success': False,
                'error': 'Contact not found'
            }), 404
        
        return jsonify({
            'success': True,
            'contact': contact.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@contacts_bp.route('/contacts/<contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """Delete a contact by ID"""
    # Check if database is enabled
    database_enabled = current_app.config.get('DATABASE_ENABLED', False)
    database_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    
    if not database_enabled or not database_uri:
        return jsonify({
            'success': False,
            'error': 'Database disabled - cannot delete contacts'
        }), 503
    
    try:
        contact = Contact.query.get(contact_id)
        
        if not contact:
            return jsonify({
                'success': False,
                'error': 'Contact not found'
            }), 404
        
        db.session.delete(contact)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Contact deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@contacts_bp.route('/contacts', methods=['POST'])
def save_contact():
    """
    Save or update contact with duplicate detection
    
    Request body:
        {
            "id": "uuid" (optional, for update),
            "user_id": "default",
            "name": "...",
            "organisation": "...",
            ...
        }
    """
    # Check if database is enabled and properly configured
    database_enabled = current_app.config.get('DATABASE_ENABLED', False)
    database_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    
    if not database_enabled or not database_uri:
        return jsonify({
            'success': False,
            'error': 'Database disabled - cannot save contacts'
        }), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        user_id = data.get('user_id', 'default')
        contact_id = data.get('id')
        force_new = data.get('_force_new', False)  # Flag to bypass duplicate check
        
        if contact_id:
            # Update existing contact
            contact = Contact.query.get(contact_id)
            if not contact:
                return jsonify({
                    'success': False,
                    'error': 'Contact not found'
                }), 404
        else:
            # Check for duplicates before creating new contact (unless force_new is True)
            if not force_new:
                is_dup, duplicate_info = is_duplicate(data, user_id, threshold=0.85)
                
                if is_dup:
                    # Return duplicate information - let frontend decide what to do
                    return jsonify({
                        'success': False,
                        'error': 'Duplicate contact detected',
                        'is_duplicate': True,
                        'duplicate': duplicate_info,
                        'message': f"Similar contact found: {duplicate_info['contact'].get('name', 'Unknown')} "
                                  f"(similarity: {duplicate_info['similarity']:.1%})"
                    }), 409  # 409 Conflict
            
            # Create new contact
            contact = Contact(id=str(uuid.uuid4()))
            db.session.add(contact)
        
        # Update fields
        for field in ['user_id', 'name', 'organisation', 'mobile_number', 
                      'landline_number', 'email_id', 'designation', 'raw_text', 'overall_confidence']:
            if field in data:
                setattr(contact, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'contact': contact.to_dict(),
            'is_duplicate': False
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

