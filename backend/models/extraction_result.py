"""
Extraction result model for detailed field-level extraction data
"""
from utils.database import db
from datetime import datetime
import uuid

class ExtractionResult(db.Model):
    """Model for storing detailed field-level extraction results"""
    __tablename__ = 'extraction_results'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contact_id = db.Column(db.String(36), db.ForeignKey('contacts.id'), nullable=False, index=True)
    field_name = db.Column(db.String(50), index=True)
    extracted_value = db.Column(db.Text)
    confidence = db.Column(db.Numeric(3, 2))
    extraction_method = db.Column(db.String(50))  # e.g., 'regex_match', 'line_1', 'label_match'
    source_line = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'field_name': self.field_name,
            'extracted_value': self.extracted_value,
            'confidence': float(self.confidence) if self.confidence else None,
            'extraction_method': self.extraction_method,
            'source_line': self.source_line,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<ExtractionResult {self.field_name}: {self.extracted_value}>'

