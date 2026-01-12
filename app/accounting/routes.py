from flask import Blueprint, render_template, request, Response, jsonify
from flask_login import login_required
from app import db
from app.models import RadAcct, RadPostAuth, AuditLog
from app.auth.decorators import role_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
import csv
import io

accounting_bp = Blueprint('accounting', __name__)

@accounting_bp.route('/')
@login_required
@role_required('Administrator', 'Operator', 'Viewer', 'Auditor')
def index():
    """Accounting logs viewer (SIEM-style)"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filters
    username_filter = request.args.get('username', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    event_type = request.args.get('event_type', 'all')
    
    # Calculate statistics
    stats = {}
    
    # Total sessions
    total_sessions = RadAcct.query.count()
    stats['total_sessions'] = total_sessions
    
    # Active sessions
    active_sessions = RadAcct.query.filter(RadAcct.acctstoptime.is_(None)).count()
    stats['active_sessions'] = active_sessions
    
    # Total data transferred (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    from sqlalchemy import func
    total_data = db.session.query(
        func.sum(RadAcct.acctinputoctets + RadAcct.acctoutputoctets)
    ).filter(
        RadAcct.acctstarttime >= thirty_days_ago
    ).scalar() or 0
    stats['total_data_gb'] = round(total_data / (1024**3), 2)
    
    # Authentication success rate (last 30 days)
    total_auth = RadPostAuth.query.filter(RadPostAuth.authdate >= thirty_days_ago).count()
    success_auth = RadPostAuth.query.filter(
        RadPostAuth.authdate >= thirty_days_ago,
        RadPostAuth.reply == 'Access-Accept'
    ).count()
    stats['auth_success_rate'] = round((success_auth / total_auth * 100) if total_auth > 0 else 0, 1)
    
    # Build query
    if event_type == 'vpn_sessions':
        # VPN accounting sessions
        query = RadAcct.query
        
        if username_filter:
            query = query.filter(RadAcct.username.like(f'%{username_filter}%'))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(RadAcct.acctstarttime >= date_from_dt)
            except:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(RadAcct.acctstarttime < date_to_dt)
            except:
                pass
        
        results = query.order_by(RadAcct.acctstarttime.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        logs = []
        for session in results.items:
            duration = session.acctsessiontime or 0
            bytes_total = (session.acctinputoctets or 0) + (session.acctoutputoctets or 0)

            
            logs.append({
                'timestamp': session.acctstarttime,
                'username': session.username,
                'event': 'VPN Session',
                'ip': session.framedipaddress,
                'calling_station': session.callingstationid,
                'duration': f'{duration // 60}m {duration % 60}s' if duration else 'Active',
                'bytes': f'{bytes_total / (1024*1024):.2f} MB' if bytes_total else '0 MB',
                'status': 'Active' if session.acctstoptime is None else 'Completed'
            })
        
    elif event_type == 'auth_attempts':
        # Authentication attempts
        query = RadPostAuth.query
        
        if username_filter:
            query = query.filter(RadPostAuth.username.like(f'%{username_filter}%'))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(RadPostAuth.authdate >= date_from_dt)
            except:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(RadPostAuth.authdate < date_to_dt)
            except:
                pass
        
        results = query.order_by(RadPostAuth.authdate.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        logs = []
        for auth in results.items:
            logs.append({
                'timestamp': auth.authdate,
                'username': auth.username,
                'event': 'Authentication',
                'status': auth.reply,
                'ip': '',
                'calling_station': '',
                'duration': '',
                'bytes': ''
            })
    
    elif event_type == 'webui_actions':
        # WebUI audit log
        query = AuditLog.query.join(AuditLog.user)
        
        if username_filter:
            query = query.filter(AuditLog.user.has(username=username_filter))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(AuditLog.created_at >= date_from_dt)
            except:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(AuditLog.created_at < date_to_dt)
            except:
                pass
        
        results = query.order_by(AuditLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        logs = []
        for audit in results.items:
            logs.append({
                'timestamp': audit.created_at,
                'username': audit.user.username,
                'event': audit.action,
                'ip': audit.ip_address,
                'calling_station': '',
                'status': audit.resource_type or '',
                'duration': '',
                'bytes': ''
            })
    
    else:
        # All events / No filter - show VPN sessions by default
        query = RadAcct.query
        
        if username_filter:
            query = query.filter(RadAcct.username.like(f'%{username_filter}%'))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(RadAcct.acctstarttime >= date_from_dt)
            except:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(RadAcct.acctstarttime < date_to_dt)
            except:
                pass
        
        results = query.order_by(RadAcct.acctstarttime.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format results
        logs = []
        for session in results.items:
            duration = session.acctsessiontime or 0
            bytes_total = (session.acctinputoctets or 0) + (session.acctoutputoctets or 0)
            
            logs.append({
                'timestamp': session.acctstarttime,
                'username': session.username,
                'event': 'VPN Session',
                'ip': session.framedipaddress,
                'calling_station': session.callingstationid,
                'duration': f'{duration // 60}m {duration % 60}s' if duration else 'Active',
                'bytes': f'{bytes_total / (1024*1024):.2f} MB' if bytes_total else '0 MB',
                'status': 'Active' if session.acctstoptime is None else 'Completed'
            })
    
    return render_template(
        'accounting/index.html',
        logs=logs,
        results=results,
        stats=stats,
        username_filter=username_filter,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type
    )

@accounting_bp.route('/stats')
@login_required
@role_required('Administrator', 'Operator', 'Viewer', 'Auditor')
def stats():
    """Get statistics data for charts"""
    # Sessions over time (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    sessions_by_day = db.session.query(
        func.date(RadAcct.acctstarttime).label('date'),
        func.count(RadAcct.radacctid).label('count')
    ).filter(
        RadAcct.acctstarttime >= thirty_days_ago
    ).group_by(
        func.date(RadAcct.acctstarttime)
    ).order_by('date').all()
    
    # Top users by data usage (last 30 days)
    top_users = db.session.query(
        RadAcct.username,
        func.sum(RadAcct.acctinputoctets + RadAcct.acctoutputoctets).label('total_bytes')
    ).filter(
        RadAcct.acctstarttime >= thirty_days_ago
    ).group_by(
        RadAcct.username
    ).order_by(
        func.sum(RadAcct.acctinputoctets + RadAcct.acctoutputoctets).desc()
    ).limit(10).all()
    
    # Authentication attempts (last 30 days)
    auth_stats = db.session.query(
        RadPostAuth.reply,
        func.count(RadPostAuth.id).label('count')
    ).filter(
        RadPostAuth.authdate >= thirty_days_ago
    ).group_by(
        RadPostAuth.reply
    ).all()
    
    # Top users by session time (last 30 days)
    top_users_by_time = db.session.query(
        RadAcct.username,
        func.sum(RadAcct.acctsessiontime).label('total_time')
    ).filter(
        RadAcct.acctstarttime >= thirty_days_ago,
        RadAcct.acctsessiontime.isnot(None)
    ).group_by(
        RadAcct.username
    ).order_by(
        func.sum(RadAcct.acctsessiontime).desc()
    ).limit(10).all()
    
    # Top users by connection count (last 30 days)
    top_users_by_connections = db.session.query(
        RadAcct.username,
        func.count(RadAcct.radacctid).label('connection_count')
    ).filter(
        RadAcct.acctstarttime >= thirty_days_ago
    ).group_by(
        RadAcct.username
    ).order_by(
        func.count(RadAcct.radacctid).desc()
    ).limit(10).all()
    
    return jsonify({
        'sessions_by_day': [
            {
                'date': day.date.strftime('%Y-%m-%d'),
                'count': day.count
            }
            for day in sessions_by_day
        ],
        'top_users': [
            {
                'username': user.username,
                'data_mb': round(user.total_bytes / (1024**2), 2)
            }
            for user in top_users
        ],
        'top_users_by_time': [
            {
                'username': user.username,
                'total_hours': round(user.total_time / 3600, 2)
            }
            for user in top_users_by_time
        ],
        'top_users_by_connections': [
            {
                'username': user.username,
                'connections': user.connection_count
            }
            for user in top_users_by_connections
        ],
        'auth_stats': [
            {
                'status': auth.reply,
                'count': auth.count
            }
            for auth in auth_stats
        ]
    })

@accounting_bp.route('/export')
@login_required
@role_required('Administrator', 'Operator', 'Viewer', 'Auditor')
def export_csv():
    """Export accounting logs to CSV"""
    # Get same filters as index
    username_filter = request.args.get('username', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    event_type = request.args.get('event_type', 'vpn_sessions')
    
    # Build query (similar to index)
    if event_type == 'vpn_sessions':
        query = RadAcct.query
        
        if username_filter:
            query = query.filter(RadAcct.username.like(f'%{username_filter}%'))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(RadAcct.acctstarttime >= date_from_dt)
            except:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(RadAcct.acctstarttime < date_to_dt)
            except:
                pass
        
        sessions = query.order_by(RadAcct.acctstarttime.desc()).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Session Start Time', 'Session End Time', 'Username', 'VPN IP Address', 'Public IP (Calling Station)', 
                        'Session Duration (seconds)', 'Bytes In', 'Bytes Out', 'Total Bytes', 'Status'])
        
        for session in sessions:
            writer.writerow([
                session.acctstarttime.isoformat() if session.acctstarttime else '',
                session.acctstoptime.isoformat() if session.acctstoptime else 'Active',
                session.username,
                session.framedipaddress or '',
                session.callingstationid or '',
                session.acctsessiontime or 0,
                session.acctinputoctets or 0,
                session.acctoutputoctets or 0,
                (session.acctinputoctets or 0) + (session.acctoutputoctets or 0),
                'Active' if session.acctstoptime is None else 'Completed'
            ])
    
    else:
        # Default to VPN sessions for 'all' or unrecognized event types
        query = RadAcct.query
        
        if username_filter:
            query = query.filter(RadAcct.username.like(f'%{username_filter}%'))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(RadAcct.acctstarttime >= date_from_dt)
            except:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(RadAcct.acctstarttime < date_to_dt)
            except:
                pass
        
        sessions = query.order_by(RadAcct.acctstarttime.desc()).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Session Start Time', 'Session End Time', 'Username', 'VPN IP Address', 'Public IP (Calling Station)', 
                        'Session Duration (seconds)', 'Bytes In', 'Bytes Out', 'Total Bytes', 'Status'])
        
        for session in sessions:
            writer.writerow([
                session.acctstarttime.isoformat() if session.acctstarttime else '',
                session.acctstoptime.isoformat() if session.acctstoptime else 'Active',
                session.username,
                session.framedipaddress or '',
                session.callingstationid or '',
                session.acctsessiontime or 0,
                session.acctinputoctets or 0,
                session.acctoutputoctets or 0,
                (session.acctinputoctets or 0) + (session.acctoutputoctets or 0),
                'Active' if session.acctstoptime is None else 'Completed'
            ])
    
    # Create response
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=accounting_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response
