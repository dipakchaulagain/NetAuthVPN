from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.auth.decorators import role_required
from app.utils import SystemManager, log_action

services_bp = Blueprint('services', __name__)

@services_bp.route('/')
@login_required
def index():
    """Services status page"""
    services = SystemManager.get_all_services_status()
    
    # Get iptables info
    rule_count = 0
    try:
        from app.utils import IPTablesManager
        rule_count = IPTablesManager.get_rule_count()
    except:
        pass
    
    return render_template(
        'services/index.html',
        services=services,
        rule_count=rule_count
    )

@services_bp.route('/restart/<service_name>', methods=['POST'])
@login_required
def restart_service(service_name):
    """Restart a service"""
    # Check if user can restart this service
    if not SystemManager.can_restart_service(service_name, current_user.role):
        flash(f'You do not have permission to restart {service_name}', 'danger')
        return redirect(url_for('services.index'))
    
    # Restart service
    success, message = SystemManager.restart_service(service_name)
    
    if success:
        log_action('Restart Service', 'Service', details=f'Restarted {service_name}')
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    return redirect(url_for('services.index'))

@services_bp.route('/logs/<service_name>')
@login_required
def view_logs(service_name):
    """View service logs (AJAX endpoint for modal)"""
    lines = request.args.get('lines', 100, type=int)
    logs = SystemManager.get_service_logs(service_name, lines=lines)
    
    if logs is None:
        return jsonify({
            'service': service_name,
            'logs': f'Error: Cannot retrieve logs for {service_name}'
        })
    
    return jsonify({
        'service': service_name,
        'logs': logs
    })

@services_bp.route('/status/<service_name>')
@login_required
def get_status(service_name):
    """Get service status (AJAX endpoint)"""
    status = SystemManager.get_service_status(service_name)
    
    if status is None:
        return jsonify({'error': 'Service not found'}), 404
    
    return jsonify(status)

@services_bp.route('/reload-iptables', methods=['POST'])
@login_required
@role_required('Administrator', 'Operator')
def reload_iptables():
    """Reload iptables rules"""
    success, message = SystemManager.reload_iptables()
    
    if success:
        log_action('Reload iptables', details='Reloaded iptables from /etc/iptables/rules.v4')
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    return redirect(url_for('services.index'))
