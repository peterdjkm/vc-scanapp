"""
Duplicate detection utility for contacts
Handles fuzzy matching to detect similar contacts despite OCR variations
"""
import re
from difflib import SequenceMatcher
from utils.database import db
from models.contact import Contact


def normalize_phone(phone):
    """Normalize phone number for comparison"""
    if not phone:
        return None
    # Remove all non-digit characters except +
    normalized = re.sub(r'[^\d+]', '', phone)
    # Remove country code if present (assume +91 for India)
    if normalized.startswith('+91'):
        normalized = normalized[3:]
    elif normalized.startswith('91') and len(normalized) > 10:
        normalized = normalized[2:]
    # Remove leading zeros
    normalized = normalized.lstrip('0')
    return normalized


def normalize_text(text):
    """Normalize text for comparison (lowercase, remove extra spaces)"""
    if not text:
        return None
    # Convert to lowercase, remove extra spaces
    normalized = ' '.join(text.lower().split())
    # Remove common punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)
    return normalized


def similarity_score(str1, str2):
    """Calculate similarity score between two strings (0-1)"""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1, str2).ratio()


def find_duplicates(contact_data, user_id='default', threshold=0.85):
    """
    Find potential duplicate contacts
    
    Args:
        contact_data: dict with contact fields (name, email_id, mobile_number, etc.)
        user_id: User ID to filter by
        threshold: Similarity threshold (0-1) for fuzzy matching
        
    Returns:
        list: List of duplicate contact IDs and similarity scores
    """
    if not contact_data:
        return []
    
    # Get all contacts for this user
    existing_contacts = Contact.query.filter_by(user_id=user_id).all()
    
    duplicates = []
    
    # Normalize input data
    input_name = normalize_text(contact_data.get('name'))
    input_email = normalize_text(contact_data.get('email_id'))
    input_mobile = normalize_phone(contact_data.get('mobile_number'))
    input_org = normalize_text(contact_data.get('organisation'))
    
    for contact in existing_contacts:
        match_score = 0.0
        match_reasons = []
        
        # Email match (exact - emails are unique identifiers)
        if input_email and contact.email_id:
            contact_email = normalize_text(contact.email_id)
            if input_email == contact_email:
                match_score = 1.0
                match_reasons.append('email')
            elif similarity_score(input_email, contact_email) > 0.9:
                match_score = max(match_score, 0.95)
                match_reasons.append('email_similar')
        
        # Phone number match (normalized)
        if input_mobile and contact.mobile_number:
            contact_mobile = normalize_phone(contact.mobile_number)
            if input_mobile == contact_mobile:
                match_score = max(match_score, 0.9)
                match_reasons.append('mobile')
        
        # Name + Organization combination (fuzzy match)
        if input_name and contact.name:
            contact_name = normalize_text(contact.name)
            name_sim = similarity_score(input_name, contact_name)
            
            # If organization matches too, increase confidence
            org_sim = 0.0
            if input_org and contact.organisation:
                contact_org = normalize_text(contact.organisation)
                org_sim = similarity_score(input_org, contact_org)
            
            # Combined score: name similarity + org similarity boost
            combined_score = name_sim * 0.7 + org_sim * 0.3
            if combined_score > threshold:
                match_score = max(match_score, combined_score)
                match_reasons.append('name_org')
            elif name_sim > 0.95:  # Very high name similarity
                match_score = max(match_score, name_sim)
                match_reasons.append('name')
        
        # If match score exceeds threshold, it's a duplicate
        if match_score >= threshold:
            duplicates.append({
                'contact_id': contact.id,
                'contact': contact.to_dict(),
                'similarity': match_score,
                'match_reasons': match_reasons
            })
    
    # Sort by similarity (highest first)
    duplicates.sort(key=lambda x: x['similarity'], reverse=True)
    
    return duplicates


def is_duplicate(contact_data, user_id='default', threshold=0.85):
    """
    Check if contact is a duplicate
    
    Returns:
        tuple: (is_duplicate: bool, duplicate_info: dict or None)
    """
    duplicates = find_duplicates(contact_data, user_id, threshold)
    
    if duplicates:
        return True, duplicates[0]  # Return the best match
    return False, None

