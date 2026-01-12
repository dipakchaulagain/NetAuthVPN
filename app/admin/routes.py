from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from app.models import WebUIUser, AuditLog
from app.auth.decorators import role_required
from app.utils import log_action
from datetime import datetime
import secrets
import string
from app.admin import admin_bp


@admin_bp.route('/users')
@login_required
@role_required('Administrator')
def users():
    """List all portal users"""
    users = WebUIUser.query.order_by(WebUIUser.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/add', methods=['POST'])
@login_required
@role_required('Administrator')
def add_user():
    """Add a new portal user"""
    username = request.form.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', '').strip()
    password = request.form.get('password', '').strip()
    
    # Validation
    if not all([username, full_name, email, role, password]):
        flash('All fields are required', 'danger')
        return redirect(url_for('admin.users'))
    
    # Check if username already exists
    if WebUIUser.query.filter_by(username=username).first():
        flash(f'Username "{username}" already exists', 'danger')
        return redirect(url_for('admin.users'))
    
    # Check if email already exists
    if WebUIUser.query.filter_by(email=email).first():
        flash(f'Email "{email}" already exists', 'danger')
        return redirect(url_for('admin.users'))
    
    # Validate role
    valid_roles = ['Administrator', 'Operator', 'Viewer', 'Auditor']
    if role not in valid_roles:
        flash('Invalid role selected', 'danger')
        return redirect(url_for('admin.users'))
    
    # Create new user
    new_user = WebUIUser(
        username=username,
        full_name=full_name,
        email=email,
        role=role,
        password_must_change=True  # Force password change on first login
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    log_action('Add Portal User', 'WebUIUser', new_user.id, 
              f'Created user {username} with role {role}')
    
    flash(f'User "{username}" created successfully', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
@role_required('Administrator')
def edit_user(user_id):
    """Edit portal user"""
    user = WebUIUser.query.get_or_404(user_id)
    
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', '').strip()
    
    # Validation
    if not all([full_name, email, role]):
        flash('All fields are required', 'danger')
        return redirect(url_for('admin.users'))
    
    # Check if email is taken by another user
    existing_email = WebUIUser.query.filter_by(email=email).first()
    if existing_email and existing_email.id != user_id:
        flash(f'Email "{email}" is already in use', 'danger')
        return redirect(url_for('admin.users'))
    
    # Validate role
    valid_roles = ['Administrator', 'Operator', 'Viewer', 'Auditor']
    if role not in valid_roles:
        flash('Invalid role selected', 'danger')
        return redirect(url_for('admin.users'))
    
    # Update user
    user.full_name = full_name
    user.email = email
    user.role = role
    
    db.session.commit()
    
    log_action('Edit Portal User', 'WebUIUser', user_id,
              f'Updated user {user.username}: {full_name}, {email}, {role}')
    
    flash(f'User "{user.username}" updated successfully', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('Administrator')
def toggle_user(user_id):
    """Toggle user active status"""
    user = WebUIUser.query.get_or_404(user_id)
    
    # Prevent deactivating yourself
    from flask_login import current_user
    if user.id == current_user.id:
        flash('You cannot deactivate your own account', 'danger')
        return redirect(url_for('admin.users'))
    
    # Toggle status
    user.active = not user.active
    db.session.commit()
    
    status = 'activated' if user.active else 'deactivated'
    log_action('Toggle Portal User Status', 'WebUIUser', user_id,
              f'{status.capitalize()} user {user.username}')
    
    flash(f'User "{user.username}" {status}', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@role_required('Administrator')
def reset_password(user_id):
    """Reset user password"""
    user = WebUIUser.query.get_or_404(user_id)
    
    new_password = request.form.get('new_password', '').strip()
    
    if not new_password:
        flash('Password cannot be empty', 'danger')
        return redirect(url_for('admin.users'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long', 'danger')
        return redirect(url_for('admin.users'))
    
    # Update password and set flag
    user.set_password(new_password)
    user.password_must_change = True  # Force password change on next login
    db.session.commit()
    
    log_action('Reset Portal User Password', 'WebUIUser', user_id,
              f'Reset password for user {user.username}')
    
    flash(f'Password reset for user "{user.username}"', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('Administrator')
def delete_user(user_id):
    """Delete portal user"""
    user = WebUIUser.query.get_or_404(user_id)
    
    # Prevent deleting yourself
    from flask_login import current_user
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('admin.users'))
    
    confirmation = request.form.get('confirmation', '').strip()
    
    # Check confirmation
    if confirmation.lower() != 'delete':
        flash('Incorrect confirmation text. Please type "delete" to confirm.', 'danger')
        return redirect(url_for('admin.users'))
    
    username = user.username
    
    # Delete user
    db.session.delete(user)
    db.session.commit()
    
    log_action('Delete Portal User', 'WebUIUser', user_id,
              f'Deleted user {username}')
    
    flash(f'User "{username}" deleted successfully', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/audit-logs')
@login_required
@role_required('Administrator', 'Auditor')
def audit_logs():
    """View audit logs for portal actions"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filters
    username_filter = request.args.get('username', '').strip()
    action_filter = request.args.get('action', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query
    query = AuditLog.query.join(AuditLog.user)
    
    if username_filter:
        query = query.filter(WebUIUser.username.like(f'%{username_filter}%'))
    
    if action_filter:
        query = query.filter(AuditLog.action.like(f'%{action_filter}%'))
    
    if date_from:
        try:
            from datetime import datetime, timedelta
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= date_from_dt)
        except:
            pass
    
    if date_to:
        try:
            from datetime import datetime, timedelta
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AuditLog.created_at < date_to_dt)
        except:
            pass
    
    # Get paginated results
    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        username_filter=username_filter,
        action_filter=action_filter,
        date_from=date_from,
        date_to=date_to
    )
