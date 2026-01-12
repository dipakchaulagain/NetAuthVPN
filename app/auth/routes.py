from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import WebUIUser
from app.auth.forms import LoginForm, ChangePasswordForm
from app.utils import log_action
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = WebUIUser.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        if not user.active:
            flash('Your account has been deactivated. Please contact an administrator.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log in user
        login_user(user, remember=form.remember_me.data)
        
        # Log the action
        log_action('User login', details=f'User {user.username} logged in')
        
        # Check if password must be changed
        if user.password_must_change:
            flash('You must change your password before continuing.', 'warning')
            return redirect(url_for('auth.force_password_change'))
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard.index')
        
        flash(f'Welcome back, {user.full_name}!', 'success')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout"""
    username = current_user.username
    log_action('User logout', details=f'User {username} logged out')
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # Update password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        log_action('Password changed', details=f'User {current_user.username} changed password')
        flash('Password changed successfully', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/change_password.html', form=form)

@auth_bp.route('/force-password-change', methods=['GET', 'POST'])
@login_required
def force_password_change():
    """Force password change for new users"""
    # If user doesn't need to change password, redirect to dashboard
    if not current_user.password_must_change:
        return redirect(url_for('dashboard.index'))
    
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('auth.force_password_change'))
        
        # Update password and clear flag
        current_user.set_password(form.new_password.data)
        current_user.password_must_change = False
        db.session.commit()
        
        log_action('Forced password change', details=f'User {current_user.username} completed mandatory password change')
        flash('Password changed successfully! You can now access the system.', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/force_password_change.html', form=form)
