from app import db
from app.models import AuditLog
from flask import request
from flask_login import current_user
from datetime import datetime

def log_action(action, resource_type=None, resource_id=None, details=None):
    """
    Log an admin action to the audit log
    Should be called after successful operations
    """
    try:
        if not current_user.is_authenticated:
            return
        
        # Get client IP
        if request.environ.get('HTTP_X_FORWARDED_FOR'):
            ip_address = request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
        else:
            ip_address = request.environ.get('REMOTE_ADDR', 'unknown')
        
        audit_entry = AuditLog(
            user_id=current_user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        
        db.session.add(audit_entry)
        db.session.commit()
        
    except Exception as e:
        # Don't let audit logging failures break the application
        db.session.rollback()
        print(f"Audit logging error: {e}")
