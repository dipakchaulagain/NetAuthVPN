from flask import Blueprint, render_template
from flask_login import login_required
from app import db
from app.models import VPNUser, RadAcct, RadPostAuth
from app.utils import SystemManager
from sqlalchemy import func, desc
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main dashboard"""
    # Get statistics
    stats = {
        'total_users': VPNUser.query.filter_by(active=True).count(),
        'active_connections': 0,
        'total_data_usage': 0,
        'recent_logins': 0
    }
    
    # Active connections (sessions with no stop time)
    active_sessions = RadAcct.query.filter(
        RadAcct.acctstoptime.is_(None)
    ).all()
    stats['active_connections'] = len(active_sessions)
    
    # Total data usage (last 30 days, in MB)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    total_bytes = db.session.query(
        func.sum(RadAcct.acctinputoctets + RadAcct.acctoutputoctets)
    ).filter(
        RadAcct.acctstarttime >= thirty_days_ago
    ).scalar() or 0
    stats['total_data_usage'] = round(total_bytes / (1024 * 1024), 2)  # Convert to MB
    
    # Recent successful logins (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    stats['recent_logins'] = RadPostAuth.query.filter(
        RadPostAuth.authdate >= yesterday,
        RadPostAuth.reply == 'Access-Accept'
    ).count()
    
    # Get active sessions details
    active_users = []
    for session in active_sessions[:10]:  # Limit to 10
        active_users.append({
            'username': session.username,
            'ip': session.framedipaddress,
            'start_time': session.acctstarttime,
            'bytes_in': session.acctinputoctets or 0,
            'bytes_out': session.acctoutputoctets or 0
        })
    
    # Get recent connection logs
    recent_logs = RadPostAuth.query.order_by(
        desc(RadPostAuth.authdate)
    ).limit(10).all()
    
    # Get service status
    services = SystemManager.get_all_services_status()
    
    return render_template(
        'dashboard/index.html',
        stats=stats,
        active_users=active_users,
        recent_logs=recent_logs,
        services=services
    )
