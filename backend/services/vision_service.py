"""
Google Vision API service for OCR
"""
from google.cloud import vision
try:
    from google.oauth2 import service_account
    OAUTH2_AVAILABLE = True
except ImportError:
    OAUTH2_AVAILABLE = False
    service_account = None

import os
import json
import base64
from io import BytesIO
from PIL import Image

# Optional import for image preprocessing (not included in MVP)
try:
    from services.image_preprocessor import ImagePreprocessor
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False
    ImagePreprocessor = None

class VisionService:
    """Service for interacting with Google Vision API"""
    
    def __init__(self, preprocess=True):
        """
        Initialize Vision client
        
        Args:
            preprocess: Whether to preprocess images before OCR (default: True)
        """
        credentials_value = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        if credentials_value:
            # Check if it's a file path or JSON content
            if os.path.exists(credentials_value):
                # It's a file path - use as is
                pass  # Already set in environment
            else:
                # It's likely JSON content (common in cloud deployments like Render.io)
                try:
                    # Try to parse as JSON
                    if credentials_value.strip().startswith('{'):
                        # Parse JSON to validate
                        creds_dict = json.loads(credentials_value)
                        
                        # Write to temporary file (Google client expects file path)
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                            json.dump(creds_dict, f)
                            temp_path = f.name
                        
                        # Update environment variable to point to temp file
                        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
                        print(f"✅ Credentials loaded from JSON environment variable")
                    else:
                        # Might be a file path that doesn't exist yet
                        print(f"⚠️  Credentials value doesn't look like JSON or existing file path")
                except (json.JSONDecodeError, ValueError) as e:
                    # Not valid JSON, treat as file path
                    print(f"⚠️  Could not parse credentials as JSON, treating as file path: {e}")
        
        # Initialize client (will use GOOGLE_APPLICATION_CREDENTIALS from environment)
        self.client = vision.ImageAnnotatorClient()
        
        self.preprocessor = ImagePreprocessor() if (preprocess and PREPROCESSOR_AVAILABLE) else None
    
    def extract_text(self, image_data):
        """
        Extract text from image using Google Vision API
        
        Args:
            image_data: Base64 encoded image string or image bytes
            
        Returns:
            dict: {
                'text': str,  # Full extracted text
                'lines': list,  # List of text lines with positions
                'blocks': list  # Text blocks with bounding boxes
            }
        """
        try:
            # Decode base64 if needed
            if isinstance(image_data, str):
                # Assume base64 encoded
                if image_data.startswith('data:image'):
                    # Remove data URL prefix
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            # Preprocess image for better OCR accuracy (optional)
            if self.preprocessor:
                image_bytes = self.preprocessor.preprocess(image_bytes)
            
            # Create Vision image
            image = vision.Image(content=image_bytes)
            
            # Use DOCUMENT_TEXT_DETECTION for better accuracy on documents
            response = self.client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f'Vision API error: {response.error.message}')
            
            # Extract full text
            full_text = response.full_text_annotation.text if response.full_text_annotation else ''
            
            # Extract text blocks with positions
            blocks = []
            lines = []
            
            if response.full_text_annotation:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        block_text = ''
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = ''.join([symbol.text for symbol in word.symbols])
                                block_text += word_text + ' '
                        blocks.append({
                            'text': block_text.strip(),
                            'confidence': block.confidence if hasattr(block, 'confidence') else None,
                            'bounding_box': self._get_bounding_box(block.bounding_box) if hasattr(block, 'bounding_box') else None
                        })
                
                # Extract lines
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = ''.join([symbol.text for symbol in word.symbols])
                                # Group words into lines (simplified)
                                lines.append({
                                    'text': word_text,
                                    'confidence': word.confidence if hasattr(word, 'confidence') else None
                                })
            
            return {
                'text': full_text,
                'lines': lines,
                'blocks': blocks,
                'raw_response': response
            }
        
        except Exception as e:
            raise Exception(f'Error extracting text: {str(e)}')
    
    def _get_bounding_box(self, bounding_box):
        """Extract bounding box coordinates"""
        if not bounding_box:
            return None
        return {
            'vertices': [
                {'x': vertex.x, 'y': vertex.y}
                for vertex in bounding_box.vertices
            ]
        }

