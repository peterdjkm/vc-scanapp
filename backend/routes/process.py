"""
Process card endpoint - main extraction endpoint
"""
from flask import Blueprint, request, jsonify, current_app
import base64
from services.vision_service import VisionService
from services.parser_service import TextParser
import uuid

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
        
        # Generate contact ID (for reference only - not saved until user clicks "Save Contact")
        contact_id = str(uuid.uuid4())
        
        # IMPORTANT: Do NOT save to database automatically here!
        # The contact should only be saved when the user explicitly clicks "Save Contact"
        # This allows the user to review the extracted data and prevents duplicate saves
        # Duplicate detection will happen in the /api/contacts POST endpoint
        
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

