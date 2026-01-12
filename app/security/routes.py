from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.models import VPNUser, SecurityRule
from app.auth.decorators import role_required
from app.utils import IPTablesManager, NetworkManager, log_action

security_bp = Blueprint('security', __name__)

@security_bp.route('/')
@login_required
@role_required('Administrator', 'Operator', 'Viewer')
def index():
    """Security rules management"""
    rules = SecurityRule.query.order_by(SecurityRule.created_at.desc()).all()
    users = VPNUser.query.filter_by(active=True).order_by(VPNUser.username).all()
    
    return render_template('security/index.html', rules=rules, users=users)

@security_bp.route('/add-rule', methods=['POST'])
@role_required('Administrator', 'Operator')
def add_rule():
    """Add a security rule"""
    user_id = request.form.get('user_id', type=int)
    
    if not user_id:
        flash('Please select a user', 'danger')
        return redirect(url_for('security.index'))
    
    user = VPNUser.query.get_or_404(user_id)
    
    route = request.form.get('route', '').strip()
    protocol = request.form.get('protocol', 'any')
    port = request.form.get('port', '').strip()
    action = request.form.get('action', 'ACCEPT')
    description = request.form.get('description', '').strip()
    
    # Validate route format
    if not NetworkManager.is_valid_route(route):
        flash('Invalid route format', 'danger')
        return redirect(url_for('security.index'))
    
    # IMPORTANT: Check that the route matches one of the user's assigned routes
    user_routes = user.routes.filter_by(active=True).all()
    route_allowed = False
    
    for user_route in user_routes:
        # Check if the security rule route matches exactly or is a subnet of the user's route
        if route == user_route.route:
            route_allowed = True
            break
        # Allow specific /32 hosts within a user's /24 or larger route
        try:
            import ipaddress
            rule_net = ipaddress.IPv4Network(route, strict=False)
            user_net = ipaddress.IPv4Network(user_route.route, strict=False)
            
            # Check if rule network is subnet of or equal to user network
            if rule_net.subnet_of(user_net) or rule_net == user_net:
                route_allowed = True
                break
        except:
            pass
    
    if not route_allowed:
        flash(f'Route {route} is not in user\'s assigned routes. Please add the route first.', 'danger')
        return redirect(url_for('security.index'))
    
    # Validate port if provided
    if port and not NetworkManager.is_valid_port(port):
        flash('Invalid port format', 'danger')
        return redirect(url_for('security.index'))
    
    # Create rule
    rule = SecurityRule(
        vpn_user_id=user_id,
        route=route,
        protocol=protocol,
        port=port if port else None,
        action=action,
        description=description
    )
    db.session.add(rule)
    db.session.commit()
    
    log_action('Add Security Rule', 'SecurityRule', rule.id, 
              f'Added rule for {user.username}: {protocol}:{port} -> {route}')
    
    flash('Security rule added. Click "Apply Rules" to activate.', 'success')
    return redirect(url_for('security.index'))

@security_bp.route('/toggle-rule/<int:rule_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def toggle_rule(rule_id):
    """Enable/Disable a security rule"""
    rule = SecurityRule.query.get_or_404(rule_id)
    confirmation = request.form.get('confirmation', '').strip()
    
    # Check confirmation text
    if confirmation.lower() != 'disable':
        flash('Incorrect confirmation text. Please type "Disable" to confirm.', 'danger')
        return redirect(url_for('security.index'))
    
    # Toggle the enabled status
    rule.enabled = not rule.enabled
    db.session.commit()
    
    status = 'enabled' if rule.enabled else 'disabled'
    log_action('Toggle Security Rule', 'SecurityRule', rule_id,
              f'{status.capitalize()} rule: {rule.protocol}:{rule.port} -> {rule.route}')
    
    flash(f'Security rule {status}. Click "Apply Rules" to activate changes.', 'success')
    return redirect(url_for('security.index'))

@security_bp.route('/delete-rule/<int:rule_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def delete_rule(rule_id):
    """Delete a security rule"""
    rule = SecurityRule.query.get_or_404(rule_id)
    confirmation = request.form.get('confirmation', '').strip()
    
    # Check confirmation text
    if confirmation.lower() != 'delete':
        flash('Incorrect confirmation text. Please type "delete" to confirm.', 'danger')
        return redirect(url_for('security.index'))
    
    user_id = rule.vpn_user_id
    
    rule.active = False
    db.session.commit()
    
    log_action('Delete Security Rule', 'SecurityRule', rule_id,
              f'Deleted rule: {rule.protocol}:{rule.port} -> {rule.route}')
    
    flash('Security rule deleted. Click "Apply Rules" to activate changes.', 'success')
    return redirect(url_for('security.index'))

@security_bp.route('/apply-rules/<int:user_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def apply_rules(user_id):
    """Apply security rules to iptables"""
    user = VPNUser.query.get_or_404(user_id)
    rules = user.security_rules.filter_by(active=True).all()
    
    try:
        # Apply rules to iptables
        IPTablesManager.apply_user_rules(user, rules)
        
        # Save iptables
        IPTablesManager.save_rules()
        
        log_action('Apply Security Rules', 'VPNUser', user_id,
                  f'Applied {len(rules)} rules for {user.username}')
        
        flash(f'Applied {len(rules)} rules for {user.username} to iptables', 'success')
    except Exception as e:
        flash(f'Error applying rules: {str(e)}', 'danger')
    
    return redirect(url_for('security.index'))
