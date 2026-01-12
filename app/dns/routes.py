from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import DNSRecord
from app.auth.decorators import role_required
from app.utils import SystemManager, Validators, log_action

dns_bp = Blueprint('dns', __name__)

@dns_bp.route('/')
@login_required
def index():
    """List all DNS records"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    records = DNSRecord.query.filter_by(active=True).order_by(
        DNSRecord.hostname
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('dns/index.html', records=records)

@dns_bp.route('/add', methods=['POST'])
@role_required('Administrator', 'Operator')
def add_record():
    """Add a DNS record"""
    hostname = request.form.get('hostname', '').strip().lower()
    ip_address = request.form.get('ip_address', '').strip()
    description = request.form.get('description', '').strip()
    
    # Validate hostname
    valid, msg = Validators.validate_hostname(hostname)
    if not valid:
        flash(msg, 'danger')
        return redirect(url_for('dns.index'))
    
    # Validate IP
    valid, msg = Validators.validate_ip_address(ip_address)
    if not valid:
        flash(msg, 'danger')
        return redirect(url_for('dns.index'))
    
    # Check if hostname already exists
    existing = DNSRecord.query.filter_by(hostname=hostname, active=True).first()
    if existing:
        flash(f'Hostname {hostname} already exists', 'warning')
        return redirect(url_for('dns.index'))
    
    # Create record
    record = DNSRecord(
        hostname=hostname,
        ip_address=ip_address,
        description=description,
        created_by=current_user.id
    )
    db.session.add(record)
    db.session.commit()
    
    log_action('Add DNS Record', 'DNSRecord', record.id,
              f'Added {hostname} -> {ip_address}')
    
    flash(f'DNS record {hostname} added. Click "Apply Changes" to update /etc/hosts.', 'success')
    return redirect(url_for('dns.index'))

@dns_bp.route('/edit/<int:record_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def edit_record(record_id):
    """Edit a DNS record"""
    record = DNSRecord.query.get_or_404(record_id)
    
    hostname = request.form.get('hostname', '').strip().lower()
    ip_address = request.form.get('ip_address', '').strip()
    description = request.form.get('description', '').strip()
    
    # Validate hostname
    valid, msg = Validators.validate_hostname(hostname)
    if not valid:
        flash(msg, 'danger')
        return redirect(url_for('dns.index'))
    
    # Validate IP
    valid, msg = Validators.validate_ip_address(ip_address)
    if not valid:
        flash(msg, 'danger')
        return redirect(url_for('dns.index'))
    
    # Check if hostname conflicts (if changed)
    if hostname != record.hostname:
        existing = DNSRecord.query.filter_by(hostname=hostname, active=True).first()
        if existing:
            flash(f'Hostname {hostname} already exists', 'warning')
            return redirect(url_for('dns.index'))
    
    # Update record
    record.hostname = hostname
    record.ip_address = ip_address
    record.description = description
    db.session.commit()
    
    log_action('Edit DNS Record', 'DNSRecord', record_id,
              f'Updated {hostname} -> {ip_address}')
    
    flash(f'DNS record updated. Click "Apply Changes" to update /etc/hosts.', 'success')
    return redirect(url_for('dns.index'))

@dns_bp.route('/delete/<int:record_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def delete_record(record_id):
    """Delete a DNS record"""
    record = DNSRecord.query.get_or_404(record_id)
    confirmation = request.form.get('confirmation', '').strip()
    
    # Check confirmation text
    if confirmation.lower() != 'delete':
        flash('Incorrect confirmation text. Please type "delete" to confirm.', 'danger')
        return redirect(url_for('dns.index'))
    
    hostname = record.hostname
    record.active = False
    db.session.commit()
    
    log_action('Delete DNS Record', 'DNSRecord', record_id,
              f'Deleted {hostname}')
    
    flash(f'DNS record {hostname} deleted. Click "Apply Changes" to update /etc/hosts.', 'success')
    return redirect(url_for('dns.index'))

@dns_bp.route('/toggle/<int:record_id>', methods=['POST'])
@role_required('Administrator', 'Operator')
def toggle_record(record_id):
    """Enable/Disable a DNS record"""
    record = DNSRecord.query.get_or_404(record_id)
    confirmation = request.form.get('confirmation', '').strip()
    
    # Check confirmation text when disabling
    if record.enabled and confirmation.lower() != 'disable':
        flash('Incorrect confirmation text. Please type "Disable" to confirm.', 'danger')
        return redirect(url_for('dns.index'))
    
    record.enabled = not record.enabled
    db.session.commit()
    
    status = 'enabled' if record.enabled else 'disabled'
    log_action('Toggle DNS Record', 'DNSRecord', record_id,
              f'{status.capitalize()} DNS: {record.hostname}')
    
    flash(f'DNS record {status}. Click "Apply Changes" to update /etc/hosts.', 'success')
    return redirect(url_for('dns.index'))

@dns_bp.route('/apply', methods=['POST'])
@role_required('Administrator', 'Operator')
def apply_changes():
    """Apply DNS changes to /etc/hosts and restart dnsmasq"""
    try:
        # Get all active records
        records = DNSRecord.query.filter_by(active=True).all()
        
        # Update /etc/hosts
        success, message = SystemManager.update_hosts_file(records)
        
        if not success:
            flash(f'Error updating /etc/hosts: {message}', 'danger')
            return redirect(url_for('dns.index'))
        
        # Restart dnsmasq
        success, message = SystemManager.restart_service('dnsmasq')
        
        if success:
            log_action('Apply DNS Changes', details=f'Updated {len(records)} DNS records and restarted dnsmasq')
            flash(f'Successfully applied {len(records)} DNS records and restarted dnsmasq', 'success')
        else:
            flash(f'/etc/hosts updated but failed to restart dnsmasq: {message}', 'warning')
        
    except Exception as e:
        flash(f'Error applying DNS changes: {str(e)}', 'danger')
    
    return redirect(url_for('dns.index'))
