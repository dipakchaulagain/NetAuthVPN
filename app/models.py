from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return WebUIUser.query.get(int(user_id))

class WebUIUser(UserMixin, db.Model):
    """Web UI user for authentication"""
    __tablename__ = 'webui_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False)
    role = db.Column(db.Enum('Administrator', 'Operator', 'Viewer', 'Auditor'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    password_must_change = db.Column(db.Boolean, default=False)
    
    # Relationships
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    dns_records = db.relationship('DNSRecord', backref='creator', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, *roles):
        """Check if user has any of the specified roles"""
        return self.role in roles
    
    def is_active(self):
        """Required by Flask-Login"""
        return self.active
    
    def __repr__(self):
        return f'<WebUIUser {self.username}>'

class VPNUser(db.Model):
    """VPN user account with LDAP sync"""
    __tablename__ = 'vpn_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(128))
    email = db.Column(db.String(128))
    ip_address = db.Column(db.String(15), unique=True, nullable=False, index=True)
    ldap_synced = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    routes = db.relationship('VPNUserRoute', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    security_rules = db.relationship('SecurityRule', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<VPNUser {self.username} - {self.ip_address}>'

class VPNUserRoute(db.Model):
    """Custom routes for VPN users"""
    __tablename__ = 'vpn_user_routes'
    
    id = db.Column(db.Integer, primary_key=True)
    vpn_user_id = db.Column(db.Integer, db.ForeignKey('vpn_users.id'), nullable=False, index=True)
    route = db.Column(db.String(32), nullable=False)
    description = db.Column(db.String(255))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VPNUserRoute {self.route}>'

class SecurityRule(db.Model):
    """Per-user firewall rules"""
    __tablename__ = 'security_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    vpn_user_id = db.Column(db.Integer, db.ForeignKey('vpn_users.id'), nullable=False, index=True)
    route = db.Column(db.String(32), nullable=False)
    protocol = db.Column(db.Enum('tcp', 'udp', 'icmp', 'any'), default='any')
    port = db.Column(db.String(20))
    action = db.Column(db.Enum('ACCEPT', 'DROP'), default='ACCEPT')
    description = db.Column(db.String(255))
    active = db.Column(db.Boolean, default=True, index=True)
    enabled = db.Column(db.Boolean, default=True)  # For enable/disable toggle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SecurityRule {self.protocol}:{self.port} -> {self.route}>'

class DNSRecord(db.Model):
    """Custom DNS entries for /etc/hosts"""
    __tablename__ = 'dns_records'
    
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(15), nullable=False)
    description = db.Column(db.String(255))
    active = db.Column(db.Boolean, default=True)
    enabled = db.Column(db.Boolean, default=True)  # For enable/disable toggle
    created_by = db.Column(db.Integer, db.ForeignKey('webui_users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<DNSRecord {self.hostname} -> {self.ip_address}>'

class AuditLog(db.Model):
    """Audit log for admin actions"""
    __tablename__ = 'audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('webui_users.id'), nullable=False, index=True)
    action = db.Column(db.String(128), nullable=False)
    resource_type = db.Column(db.String(64), index=True)
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user {self.user_id}>'

# RADIUS Tables (Read-write models for existing tables)
class RadCheck(db.Model):
    """RADIUS check attributes (existing table)"""
    __tablename__ = 'radcheck'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    attribute = db.Column(db.String(64), nullable=False)
    op = db.Column(db.String(2), nullable=False, default=':=')
    value = db.Column(db.String(253), nullable=False)
    
    def __repr__(self):
        return f'<RadCheck {self.username}: {self.attribute}={self.value}>'

class RadReply(db.Model):
    """RADIUS reply attributes (existing table)"""
    __tablename__ = 'radreply'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    attribute = db.Column(db.String(64), nullable=False)
    op = db.Column(db.String(2), nullable=False, default=':=')
    value = db.Column(db.String(253), nullable=False)
    
    def __repr__(self):
        return f'<RadReply {self.username}: {self.attribute}={self.value}>'

class RadAcct(db.Model):
    """RADIUS accounting (existing table)"""
    __tablename__ = 'radacct'
    
    radacctid = db.Column(db.BigInteger, primary_key=True)
    acctsessionid = db.Column(db.String(64), nullable=False, index=True)
    acctuniqueid = db.Column(db.String(32), nullable=False, unique=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    realm = db.Column(db.String(64))
    nasipaddress = db.Column(db.String(15), nullable=False, index=True)
    nasportid = db.Column(db.String(50))
    nasporttype = db.Column(db.String(32))
    acctstarttime = db.Column(db.DateTime, index=True)
    acctupdatetime = db.Column(db.DateTime)
    acctstoptime = db.Column(db.DateTime, index=True)
    acctinterval = db.Column(db.Integer)
    acctsessiontime = db.Column(db.Integer)
    acctauthentic = db.Column(db.String(32))
    connectinfo_start = db.Column(db.String(50))
    connectinfo_stop = db.Column(db.String(50))
    acctinputoctets = db.Column(db.BigInteger)
    acctoutputoctets = db.Column(db.BigInteger)
    calledstationid = db.Column(db.String(50))
    callingstationid = db.Column(db.String(50))
    acctterminatecause = db.Column(db.String(32))
    servicetype = db.Column(db.String(32))
    framedprotocol = db.Column(db.String(32))
    framedipaddress = db.Column(db.String(15), index=True)
    
    def __repr__(self):
        return f'<RadAcct {self.username} - {self.acctstarttime}>'

class RadPostAuth(db.Model):
    """RADIUS post-auth log (existing table)"""
    __tablename__ = 'radpostauth'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    reply = db.Column(db.String(32), nullable=False)
    authdate = db.Column(db.DateTime, nullable=False, index=True)
    
    def __repr__(self):
        return f'<RadPostAuth {self.username} - {self.reply}>'

class SiteSettings(db.Model):
    """Site customization settings"""
    __tablename__ = 'site_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    site_title = db.Column(db.String(128), default='NetAuthVPN')
    logo_path = db.Column(db.String(255))
    favicon_path = db.Column(db.String(255))
    theme_color = db.Column(db.String(7), default='#667eea')  # Hex color code (gradient start)
    theme_color_secondary = db.Column(db.String(7), default='#764ba2')  # Hex color code (gradient end)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('webui_users.id'))
    
    def __repr__(self):
        return f'<SiteSettings {self.site_title}>'
