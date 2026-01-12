from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import VPNUser, VPNUserRoute
from app.auth.decorators import role_required
from app.utils import LDAPClient, NetworkManager, RADIUSManager, log_action
from datetime import datetime

users_bp = Blueprint('users', __name__)

@users_bp.route('/')
@login_required
def index():
    """List all VPN users"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    users_query = VPNUser.query.order_by(VPNUser.username)
    users = users_query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('users/index.html', users=users)

@users_bp.route('/download-config')
@login_required
def download_universal_config():
    """Download universal OpenVPN configuration file"""
    from flask import send_file
    import os
    
    # Path to universal client config
    config_path = '/etc/openvpn/clients/universal-client.ovpn'
    
    # Check if file exists
    if not os.path.exists(config_path):
        flash('OpenVPN configuration file not found. Please contact administrator.', 'danger')
        return redirect(url_for('users.index'))
    
    log_action('Download Universal Config', details='Downloaded universal OpenVPN config')
    
    return send_file(
        config_path,
        as_attachment=True,
        download_name='universal-client.ovpn',
        mimetype='text/plain'
    )

@users_bp.route('/sync-ldap', methods=['POST'])
@role_required('Administrator', 'Operator')
def sync_ldap():
    """Sync users from LDAP"""
    try:
        with LDAPClient() as ldap_client:
            ldap_users = ldap_client.search_users()
        
        if not ldap_users:
            flash('No users found in LDAP or connection failed', 'warning')
            return redirect(url_for('users.index'))
        
        synced_count = 0
        error_count = 0
        
        for ldap_user in ldap_users:
            username = ldap_user['username']
            
            # Check if user already exists
            vpn_user = VPNUser.query.filter_by(username=username).first()
            
            if vpn_user:
                # Update existing user
                vpn_user.full_name = ldap_user['full_name']
                vpn_user.email = ldap_user['email']
                vpn_user.ldap_synced = True
                vpn_user.last_sync = datetime.utcnow()
            else:
                # Get next available IP
                ip_address = NetworkManager.get_next_available_ip()
                
                if not ip_address:
                    error_count += 1
                    continue
                
                # Create new user
                vpn_user = VPNUser(
                    username=username,
                    full_name=ldap_user['full_name'],
                    email=ldap_user['email'],
                    ip_address=ip_address,
                    ldap_synced=True,
                    last_sync=datetime.utcnow()
                )
                db.session.add(vpn_user)
                db.session.flush()  # Get the ID
                
                # Add IP to radreply table
                if not RADIUSManager.set_user_ip(username, ip_address):
                    error_count += 1
                    db.session.rollback()
                    continue
                
                # Add Account-Status to radcheck table
                if not RADIUSManager.set_account_status(username, enabled=True):
                    error_count += 1
                    db.session.rollback()
                    continue
                
                synced_count += 1
        
        db.session.commit()
        
        log_action('LDAP Sync', details=f'Synced {synced_count} users from LDAP')
        
        if error_count > 0:
            flash(f'Synced {synced_count} users. {error_count} errors occurred.', 'warning')
        else:
            flash(f'Successfully synced {synced_count} users from LDAP', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error syncing LDAP: {str(e)}', 'danger')
    
    return redirect(url_for('users.index'))

@users_bp.route('/<int:user_id>')
@login_required
def view(user_id):
    """View user details"""
    user = VPNUser.query.get_or_404(user_id)
    routes = user.routes.filter_by(active=True).all()
    
    return render_template('users/view.html', user=user, routes=routes)

@users_bp.route('/<int:user_id>/routes')
@login_required
def get_user_routes(user_id):
    """Get user routes as JSON for AJAX requests"""
    user = VPNUser.query.get_or_404(user_id)
    routes = user.routes.filter_by(active=True).all()
    
    return jsonify({
        'routes': [
            {
                'route': route.route,
                'description': route.description or ''
            }
            for route in routes
        ]
    })

@users_bp.route('/<int:user_id>/add-route', methods=['POST'])
@role_required('Administrator', 'Operator')
def add_route(user_id):
    """Add a route to a user"""
    user = VPNUser.query.get_or_404(user_id)
    
    route = request.form.get('route', '').strip()
    description = request.form.get('description', '').strip()
    
    # Validate route
    if not NetworkManager.is_valid_route(route):
        # Check if it's a host IP with subnet mask
        try:
            import ipaddress
            network = ipaddress.IPv4Network(route, strict=False)
            if network.prefixlen < 32:
                # Suggest the correct network address
                correct_route = str(network.network_address) + '/' + str(network.prefixlen)
                flash(f'Invalid route: {route}. For /{network.prefixlen} subnet, use proper network address: {correct_route}', 'danger')
            else:
                flash('Invalid route format. Use CIDR notation (e.g., 192.168.1.0/24)', 'danger')
        except:
            flash('Invalid route format. Use CIDR notation (e.g., 192.168.1.0/24)', 'danger')
        return redirect(url_for('users.view', user_id=user_id))
    
    # Check if route already exists
    existing = VPNUserRoute.query.filter_by(
        vpn_user_id=user_id,
        route=route,
        active=True
    ).first()
    
    if existing:
        flash('Route already exists for this user', 'warning')
        return redirect(url_for('users.view', user_id=user_id))
    
    # Add route to database
    new_route = VPNUserRoute(
        vpn_user_id=user_id,
        route=route,
        description=description
    )
    db.session.add(new_route)
    db.session.commit()
    
    # Add route to radreply table
    if RADIUSManager.add_user_route(user.username, route):
        log_action('Add Route', 'VPNUser', user_id, f'Added route {route} to {user.username}')
        flash(f'Route {route} added successfully', 'success')
    else:
        flash('Route added to database but failed to update RADIUS', 'warning')
    
    return redirect(url_for('users.view', user_id=user_id))

@users_bp.route('/<int:user_id>/delete-route/<int:route_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def delete_route(user_id, route_id):
    """Delete a route from a user"""
    user = VPNUser.query.get_or_404(user_id)
    route = VPNUserRoute.query.get_or_404(route_id)
    
    if route.vpn_user_id != user_id:
        flash('Invalid route', 'danger')
        return redirect(url_for('users.view', user_id=user_id))
    
    route_value = route.route
    
    # Mark as inactive
    route.active = False
    db.session.commit()
    
    # Remove from radreply
    if RADIUSManager.remove_user_route(user.username, route_value):
        log_action('Delete Route', 'VPNUser', user_id, f'Deleted route {route_value} from {user.username}')
        flash(f'Route {route_value} deleted successfully', 'success')
    else:
        flash('Route deleted from database but failed to update RADIUS', 'warning')
    
    return redirect(url_for('users.view', user_id=user_id))

@users_bp.route('/<int:user_id>/toggle-active', methods=['POST'])
@role_required('Administrator')
def toggle_active(user_id):
    """Toggle user active status"""
    user = VPNUser.query.get_or_404(user_id)
    user.active = not user.active
    
    # Update Account-Status in radcheck
    RADIUSManager.set_account_status(user.username, enabled=user.active)
    
    db.session.commit()
    
    log_action('Toggle User Status', 'VPNUser', user_id, 
              f'Set {user.username} active={user.active}')
    
    status = 'activated' if user.active else 'deactivated'
    flash(f'User {user.username} {status}', 'success')
    
    return redirect(url_for('users.view', user_id=user_id))

@users_bp.route('/<int:user_id>/download-config')
@login_required
def download_config(user_id):
    """Download universal OpenVPN configuration file"""
    from flask import send_file
    import os
    
    user = VPNUser.query.get_or_404(user_id)
    
    # Path to universal client config
    config_path = '/etc/openvpn/clients/universal-client.ovpn'
    
    # Check if file exists
    if not os.path.exists(config_path):
        flash('OpenVPN configuration file not found. Please contact administrator.', 'danger')
        return redirect(url_for('users.view', user_id=user_id))
    
    log_action('Download Config', 'VPNUser', user_id, 
              f'Downloaded OpenVPN config for {user.username}')
    
    return send_file(
        config_path,
        as_attachment=True,
        download_name='universal-client.ovpn',
        mimetype='text/plain'
    )
