from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import SiteSettings
from app.auth.decorators import role_required
from app.utils import log_action
from app.settings import settings_bp
import os


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'ico', 'svg'}
UPLOAD_FOLDER = 'app/static/uploads'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@settings_bp.route('/')
@login_required
@role_required('Administrator')
def index():
    """View and edit site settings"""
    settings = SiteSettings.query.first()
    if not settings:
        # Create default settings if none exist
        settings = SiteSettings(site_title='VPN Manager', theme_color='#667eea')
        db.session.add(settings)
        db.session.commit()
    
    return render_template('settings/index.html', settings=settings)

@settings_bp.route('/update', methods=['POST'])
@login_required
@role_required('Administrator')
def update():
    """Update site settings"""
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings()
        db.session.add(settings)
    
    # Update text fields
    site_title = request.form.get('site_title', '').strip()
    theme_color = request.form.get('theme_color', '').strip()
    theme_color_secondary = request.form.get('theme_color_secondary', '').strip()
    
    if site_title:
        settings.site_title = site_title
    
    if theme_color:
        # Validate hex color
        if theme_color.startswith('#') and len(theme_color) == 7:
            settings.theme_color = theme_color
    
    if theme_color_secondary:
        # Validate hex color
        if theme_color_secondary.startswith('#') and len(theme_color_secondary) == 7:
            settings.theme_color_secondary = theme_color_secondary
    
    # Handle logo upload
    if 'logo' in request.files:
        logo_file = request.files['logo']
        if logo_file and logo_file.filename and allowed_file(logo_file.filename):
            filename = secure_filename(logo_file.filename)
            # Add timestamp to avoid conflicts
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'logo_{timestamp}_{filename}'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            logo_file.save(filepath)
            settings.logo_path = f'/static/uploads/{filename}'
    
    # Handle favicon upload
    if 'favicon' in request.files:
        favicon_file = request.files['favicon']
        if favicon_file and favicon_file.filename and allowed_file(favicon_file.filename):
            filename = secure_filename(favicon_file.filename)
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'favicon_{timestamp}_{filename}'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            favicon_file.save(filepath)
            settings.favicon_path = f'/static/uploads/{filename}'
    
    settings.updated_by = current_user.id
    db.session.commit()
    
    log_action('Update Site Settings', 'SiteSettings', settings.id,
              f'Updated site settings: {site_title}')
    
    flash('Site settings updated successfully', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/reset-logo', methods=['POST'])
@login_required
@role_required('Administrator')
def reset_logo():
    """Remove custom logo"""
    settings = SiteSettings.query.first()
    if settings:
        settings.logo_path = None
        settings.updated_by = current_user.id
        db.session.commit()
        log_action('Reset Logo', 'SiteSettings', settings.id, 'Removed custom logo')
        flash('Logo reset to default', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/reset-favicon', methods=['POST'])
@login_required
@role_required('Administrator')
def reset_favicon():
    """Remove custom favicon"""
    settings = SiteSettings.query.first()
    if settings:
        settings.favicon_path = None
        settings.updated_by = current_user.id
        db.session.commit()
        log_action('Reset Favicon', 'SiteSettings', settings.id, 'Removed custom favicon')
        flash('Favicon reset to default', 'success')
    return redirect(url_for('settings.index'))
