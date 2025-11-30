"""
Confidence metrics model for tracking extraction quality
"""
from utils.database import db
from datetime import datetime
import uuid

class ConfidenceMetric(db.Model):
    """Model for storing confidence and accuracy metrics"""
    __tablename__ = 'confidence_metrics'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contact_id = db.Column(db.String(36), db.ForeignKey('contacts.id'), nullable=False, index=True)
    overall_confidence = db.Column(db.Numeric(3, 2), index=True)
    field_detection_rate = db.Column(db.Numeric(3, 2))  # % of fields detected
    field_accuracy = db.Column(db.Numeric(3, 2))  # % of correct field values
    missing_fields = db.Column(db.ARRAY(db.String(50)))  # List of missing field names
    detected_fields = db.Column(db.ARRAY(db.String(50)))  # List of detected field names
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'overall_confidence': float(self.overall_confidence) if self.overall_confidence else None,
            'field_detection_rate': float(self.field_detection_rate) if self.field_detection_rate else None,
            'field_accuracy': float(self.field_accuracy) if self.field_accuracy else None,
            'missing_fields': self.missing_fields or [],
            'detected_fields': self.detected_fields or [],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<ConfidenceMetric {self.contact_id}: {self.overall_confidence}>'

