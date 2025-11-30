"""
Confidence calculation service
"""
from typing import Dict, List, Optional

class ConfidenceCalculator:
    """Calculate confidence scores for extracted fields"""
    
    # Confidence thresholds
    MIN_FIELD_CONFIDENCE = 0.70
    
    @staticmethod
    def calculate_email_confidence(email: Optional[str]) -> float:
        """
        Calculate confidence for email field
        Email regex match is very reliable
        """
        if not email:
            return 0.0
        
        # Email regex pattern
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(email_pattern, email):
            return 1.0  # Perfect match
        return 0.0
    
    @staticmethod
    def calculate_phone_confidence(phone: Optional[str], is_mobile: bool = True) -> float:
        """
        Calculate confidence for phone number
        """
        if not phone:
            return 0.0
        
        import re
        
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
        
        # Mobile patterns (10-15 digits, may start with + or country code)
        mobile_patterns = [
            r'^\+?[1-9]\d{9,14}$',  # International format
            r'^[6-9]\d{9}$',  # Indian mobile (10 digits starting with 6-9)
            r'^[2-9]\d{2}[2-9]\d{2}\d{4}$',  # US format
        ]
        
        # Landline patterns
        landline_patterns = [
            r'^\+?[1-9]\d{6,14}$',  # International
            r'^0\d{2,4}[\s\-]?\d{6,8}$',  # With area code
        ]
        
        patterns = mobile_patterns if is_mobile else landline_patterns
        
        for pattern in patterns:
            if re.match(pattern, cleaned):
                # Higher confidence for international format
                if cleaned.startswith('+') or len(cleaned) > 10:
                    return 0.95
                return 0.90
        
        # Partial match (has digits but format unclear)
        if re.search(r'\d{7,}', cleaned):
            return 0.75
        
        return 0.0
    
    @staticmethod
    def calculate_name_confidence(name: Optional[str], source: str) -> float:
        """
        Calculate confidence for name field
        """
        if not name:
            return 0.0
        
        # Confidence based on detection method
        if source == 'label_match':
            # Found after "Name:" label
            return 0.95
        elif source == 'line_1':
            # First prominent line
            return 0.85
        elif source == 'inferred':
            # Inferred from context
            return 0.75
        else:
            return 0.70
    
    @staticmethod
    def calculate_organisation_confidence(org: Optional[str], source: str) -> float:
        """
        Calculate confidence for organisation field
        """
        if not org:
            return 0.0
        
        # Confidence based on detection method
        if source == 'label_match':
            # Found after "Company:" or "Organisation:" label
            return 0.95
        elif source == 'prominent_text':
            # Large/prominent text
            return 0.85
        elif source == 'inferred':
            # Inferred from context
            return 0.75
        else:
            return 0.70
    
    @staticmethod
    def calculate_designation_confidence(designation: Optional[str], source: str) -> float:
        """
        Calculate confidence for designation field
        """
        if not designation:
            return 0.0
        
        # Confidence based on detection method
        if source == 'label_match':
            # Found after "Title:" or "Designation:" label
            return 0.95
        elif source == 'inferred':
            # Inferred from context
            return 0.80
        else:
            return 0.70
    
    @staticmethod
    def calculate_overall_confidence(field_confidences: Dict[str, float]) -> float:
        """
        Calculate overall confidence from field-level confidences
        
        Args:
            field_confidences: Dict of field_name -> confidence score
            
        Returns:
            float: Overall confidence (0.0 - 1.0)
        """
        if not field_confidences:
            return 0.0
        
        # Filter out fields with confidence below minimum
        valid_confidences = [
            conf for conf in field_confidences.values()
            if conf >= ConfidenceCalculator.MIN_FIELD_CONFIDENCE
        ]
        
        if not valid_confidences:
            return 0.0
        
        # Calculate average
        overall = sum(valid_confidences) / len(valid_confidences)
        return round(overall, 2)
    
    @staticmethod
    def get_detected_fields(field_confidences: Dict[str, float]) -> List[str]:
        """Get list of detected fields (confidence >= minimum)"""
        return [
            field for field, conf in field_confidences.items()
            if conf >= ConfidenceCalculator.MIN_FIELD_CONFIDENCE
        ]
    
    @staticmethod
    def get_missing_fields(field_confidences: Dict[str, float], all_fields: List[str]) -> List[str]:
        """Get list of missing fields"""
        detected = ConfidenceCalculator.get_detected_fields(field_confidences)
        return [field for field in all_fields if field not in detected]

