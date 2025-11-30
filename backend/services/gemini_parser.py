"""
Google Gemini LLM parser for extracting contact information
Uses Gemini API for intelligent parsing when regex confidence is low
"""
import os
import json
import google.generativeai as genai
from typing import Dict, Optional

class GeminiParser:
    """Parse OCR text using Google Gemini LLM"""
    
    def __init__(self):
        """Initialize Gemini client"""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            # Try to use same credentials as Vision API
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path:
                # For service account, we'll use API key approach
                # User needs to set GEMINI_API_KEY explicitly
                pass
        
        if api_key:
            genai.configure(api_key=api_key)
            # Use gemini-2.5-flash (faster, cheaper) - latest model
            try:
                self.client = genai.GenerativeModel('gemini-2.5-flash')
                self.enabled = True
            except Exception as e:
                # Fallback to gemini-2.5-pro if flash not available
                try:
                    self.client = genai.GenerativeModel('gemini-2.5-pro')
                    self.enabled = True
                except Exception as e2:
                    print(f"Warning: Could not initialize Gemini model: {str(e2)}")
                    self.enabled = False
                    self.client = None
        else:
            self.enabled = False
            self.client = None
    
    def parse(self, text: str) -> Optional[Dict]:
        """
        Parse OCR text using Gemini LLM
        
        Args:
            text: Raw OCR text from visiting card
            
        Returns:
            dict with extracted fields, or None if disabled/failed
        """
        if not self.enabled or not text or not text.strip():
            return None
        
        try:
            # Create prompt for structured extraction
            prompt = self._create_prompt(text)
            
            # Call Gemini API
            response = self.client.generate_content(prompt)
            
            # Parse JSON response
            result_text = response.text.strip()
            
            # Extract JSON from markdown code blocks if present
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            # Parse JSON
            extracted_data = json.loads(result_text)
            
            # Convert to standard format
            return self._format_result(extracted_data, text)
            
        except Exception as e:
            print(f"Gemini parsing error: {str(e)}")
            return None
    
    def _create_prompt(self, text: str) -> str:
        """Create prompt for Gemini"""
        return f"""Extract contact information from this visiting card OCR text. Return ONLY valid JSON, no other text.

OCR Text:
{text}

Extract the following fields (use null if not found):
- name: Person's full name
- organisation: Company/organization name only (no address)
- mobile_number: Mobile phone number (with country code if present)
- landline_number: Landline/office phone number (with country code if present)
- email_id: Email address
- designation: Job title/designation

Rules:
1. Return ONLY valid JSON, no explanations
2. Use null for missing fields
3. Clean phone numbers: keep formatting but remove extra spaces
4. Organisation: Only company name, exclude addresses
5. Designation: Full job title, may span multiple lines in original
6. Email: Extract COMPLETE email address. OCR often has spacing issues:
   - If you see "name surname@domain.com" or "name surname @ domain.com", extract as "name.surname@domain.com"
   - If you see just "surname@domain.com" but context suggests a full name (e.g., "yogesh bansal@sobha.com" in text), extract the complete email
   - Always reconstruct the full email address based on context, not just what's immediately before @
   - Common patterns: spaces in name part should become dots, missing dots should be added

Example output format:
{{
  "name": "John Doe",
  "organisation": "ABC Corporation",
  "mobile_number": "+91 98765 43210",
  "landline_number": null,
  "email_id": "john.doe@abc.com",
  "designation": "Senior Manager"
}}

JSON:"""
    
    def _format_result(self, extracted_data: Dict, raw_text: str) -> Dict:
        """Format Gemini output to match standard parser format"""
        from services.confidence import ConfidenceCalculator
        confidence_calc = ConfidenceCalculator()
        
        formatted = {}
        field_confidences = {}
        
        for field in ['name', 'organisation', 'mobile_number', 'landline_number', 'email_id', 'designation']:
            value = extracted_data.get(field)
            
            if value and value != 'null' and str(value).lower() != 'null':
                # Calculate confidence based on field type
                if field == 'email_id':
                    conf = confidence_calc.calculate_email_confidence(str(value))
                elif field in ['mobile_number', 'landline_number']:
                    is_mobile = field == 'mobile_number'
                    conf = confidence_calc.calculate_phone_confidence(str(value), is_mobile)
                elif field == 'name':
                    conf = confidence_calc.calculate_name_confidence(str(value), 'llm_extraction')
                elif field == 'organisation':
                    conf = confidence_calc.calculate_organisation_confidence(str(value), 'llm_extraction')
                elif field == 'designation':
                    conf = confidence_calc.calculate_designation_confidence(str(value), 'llm_extraction')
                else:
                    conf = 0.90  # Default high confidence for LLM
                
                formatted[field] = {
                    'value': str(value),
                    'confidence': conf,
                    'source': 'gemini_llm'
                }
                field_confidences[field] = conf
        
        # Calculate overall confidence
        overall_confidence = confidence_calc.calculate_overall_confidence(field_confidences)
        
        detected_fields = [f for f, conf in field_confidences.items() if conf > 0]
        missing_fields = [f for f in ['name', 'organisation', 'mobile_number', 'landline_number', 'email_id', 'designation'] 
                         if f not in detected_fields]
        
        return {
            'extracted_data': formatted,
            'overall_confidence': overall_confidence,
            'raw_text': raw_text,
            'parsing_metadata': {
                'total_lines': len(raw_text.split('\n')),
                'detected_fields': detected_fields,
                'missing_fields': missing_fields,
                'extraction_method': 'gemini_llm'
            }
        }

