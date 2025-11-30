"""
Contact model
"""
from utils.database import db
from datetime import datetime
import uuid

class Contact(db.Model):
    """Contact model for storing extracted visiting card data"""
    __tablename__ = 'contacts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(50), default='default', index=True)
    name = db.Column(db.String(255))
    organisation = db.Column(db.String(255))
    mobile_number = db.Column(db.String(50))
    landline_number = db.Column(db.String(50))
    email_id = db.Column(db.String(255))
    designation = db.Column(db.String(255))
    image_path = db.Column(db.String(500))
    raw_text = db.Column(db.Text)
    overall_confidence = db.Column(db.Numeric(3, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    extraction_results = db.relationship('ExtractionResult', backref='contact', lazy=True, cascade='all, delete-orphan')
    confidence_metrics = db.relationship('ConfidenceMetric', backref='contact', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'organisation': self.organisation,
            'mobile_number': self.mobile_number,
            'landline_number': self.landline_number,
            'email_id': self.email_id,
            'designation': self.designation,
            'image_path': self.image_path,
            'raw_text': self.raw_text,
            'overall_confidence': float(self.overall_confidence) if self.overall_confidence else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Contact {self.id}: {self.name}>'

