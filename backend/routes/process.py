"""
Process card endpoint - main extraction endpoint
"""
from flask import Blueprint, request, jsonify, current_app
import base64
import os
from services.vision_service import VisionService
from services.parser_service import TextParser
from utils.database import db
from models.contact import Contact
from models.extraction_result import ExtractionResult
from models.confidence_metric import ConfidenceMetric
import uuid
from datetime import datetime

process_bp = Blueprint('process', __name__)

@process_bp.route('/process-card', methods=['POST'])
def process_card():
    """
    Process visiting card image and extract contact information
    
    Request:
        {
            "image": "base64_encoded_image" or multipart form data,
            "user_id": "default" (optional)
        }
    
    Response:
        {
            "success": true,
            "contact_id": "uuid",
            "extracted_data": {...},
            "overall_confidence": 0.97,
            ...
        }
    """
    try:
        # Get image data
        image_data = None
        
        if request.is_json:
            # JSON request with base64 image
            data = request.get_json()
            image_data = data.get('image')
            user_id = data.get('user_id', 'default')
        else:
            # Multipart form data
            if 'image' in request.files:
                file = request.files['image']
                image_data = file.read()
            elif 'image' in request.form:
                image_data = request.form['image']
            user_id = request.form.get('user_id', 'default')
        
        if not image_data:
            return jsonify({
                'success': False,
                'error': 'No image provided'
            }), 400
        
        # Initialize services
        vision_service = VisionService()
        
        # Initialize parser with LLM fallback if configured
        from config import Config
        use_llm = Config.USE_LLM_FALLBACK and Config.GEMINI_API_KEY
        llm_threshold = Config.LLM_CONFIDENCE_THRESHOLD
        parser = TextParser(use_llm_fallback=use_llm, llm_confidence_threshold=llm_threshold)
        
        # Extract text using Google Vision API
        vision_result = vision_service.extract_text(image_data)
        raw_text = vision_result['text']
        
        if not raw_text:
            return jsonify({
                'success': False,
                'error': 'No text detected in image',
                'raw_text': ''
            }), 400
        
        # Parse text to extract structured data
        parse_result = parser.parse(raw_text)
        
        # Generate contact ID
        contact_id = str(uuid.uuid4())
        
        # Save to database (optional - can be disabled for testing)
        save_to_db = os.getenv('SAVE_TO_DB', 'false').lower() == 'true'
        database_enabled = current_app.config.get('DATABASE_ENABLED', False)
        
        if save_to_db and database_enabled:
            # Create contact record
            contact = Contact(
                id=contact_id,
                user_id=user_id,
                name=parse_result['extracted_data'].get('name', {}).get('value'),
                organisation=parse_result['extracted_data'].get('organisation', {}).get('value'),
                mobile_number=parse_result['extracted_data'].get('mobile_number', {}).get('value'),
                landline_number=parse_result['extracted_data'].get('landline_number', {}).get('value'),
                email_id=parse_result['extracted_data'].get('email_id', {}).get('value'),
                designation=parse_result['extracted_data'].get('designation', {}).get('value'),
                raw_text=raw_text,
                overall_confidence=parse_result['overall_confidence']
            )
            
            db.session.add(contact)
            db.session.flush()
            
            # Save extraction results
            for field_name, field_data in parse_result['extracted_data'].items():
                extraction_result = ExtractionResult(
                    contact_id=contact_id,
                    field_name=field_name,
                    extracted_value=field_data.get('value'),
                    confidence=field_data.get('confidence'),
                    extraction_method=field_data.get('source'),
                    source_line=None  # Can be enhanced later
                )
                db.session.add(extraction_result)
            
            # Save confidence metrics
            confidence_metric = ConfidenceMetric(
                contact_id=contact_id,
                overall_confidence=parse_result['overall_confidence'],
                field_detection_rate=len(parse_result['parsing_metadata']['detected_fields']) / len(parser.ALL_FIELDS),
                field_accuracy=None,  # Will be calculated after manual validation
                missing_fields=parse_result['parsing_metadata']['missing_fields'],
                detected_fields=parse_result['parsing_metadata']['detected_fields']
            )
            db.session.add(confidence_metric)
            
            db.session.commit()
        
        # Prepare response
        response = {
            'success': True,
            'contact_id': contact_id,
            'extracted_data': {
                field: {
                    'value': data.get('value'),
                    'confidence': data.get('confidence'),
                    'source': data.get('source')
                }
                for field, data in parse_result['extracted_data'].items()
            },
            'overall_confidence': parse_result['overall_confidence'],
            'raw_text': raw_text,
            'parsing_metadata': parse_result['parsing_metadata']
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

