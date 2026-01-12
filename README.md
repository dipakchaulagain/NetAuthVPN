# NetAuthVPN

A comprehensive Flask-based web application for managing OpenVPN/FreeRADIUS/LDAP infrastructure with advanced features for user management, security, monitoring, auditing, and customization.

## 🌟 Key Features

### 👥 User Management
- **Portal User Management**: Full CRUD operations for WebUI users with role-based access
- **Mandatory Password Change**: New users must change password on first login
- **LDAP/Active Directory Integration**: Automatic VPN user synchronization
- **IP Address Management**: Automatic IP allocation from VPN subnet pool
- **Route Management**: Per-user custom routes with RADIUS integration
- **User Configuration**: Download individual OpenVPN client configurations

### 🔒 Security & Access Control
- **Role-Based Access Control (RBAC)**: Four distinct roles
  - **Administrator**: Full system access
  - **Operator**: Manage users, security, DNS (limited service control)
  - **Viewer**: Read-only access to all data
  - **Auditor**: Access to logs and audit trails
- **Per-User Firewall Rules**: Custom iptables rules for each VPN user
- **Security Rule Application**: Real-time iptables rule deployment
- **Self-Protection**: Users cannot disable/delete their own accounts

### 🌐 Network Management
- **DNS Management**: Custom DNS records with /etc/hosts and dnsmasq integration
- **Service Monitoring**: Real-time status of OpenVPN, FreeRADIUS, MySQL, dnsmasq
- **Service Control**: Restart services directly from the web interface

### 📊 Accounting & Auditing
- **Advanced Visualizations** (Chart.js):
  - Sessions over time (line chart)
  - Top users by data usage (bar chart)
  - Top users by session time (bar chart)
  - Top users by connection count (bar chart)
  - Authentication success/failure rates (doughnut chart)
- **Comprehensive Logging**:
  - VPN session accounting with public IP tracking
  - Authentication attempts
  - WebUI admin actions
- **Dedicated Audit Logs Page**: Complete audit trail for all portal actions
- **CSV Export**: Export logs with session start/end times, public IPs, and data usage

### 🎨 Customization
- **Site Settings Page** (Administrator-only):
  - Custom site title
  - Dual-color gradient theme (primary & secondary colors)
  - Custom logo upload
  - Custom favicon upload
  - Live preview of changes
  - Type hex codes directly or use color picker

## 📋 Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.8 or higher
- **Database**: MySQL 5.7+ or MariaDB 10.3+
- **LDAP**: Active Directory or OpenLDAP server
- **Services**: OpenVPN, FreeRADIUS, dnsmasq
- **Permissions**: sudo access for service management

## 🚀 Quick Installation

```bash
cd /path/to/netauthvpn
chmod +x install.sh
./install.sh
```

The installation script will:
1. Check Python installation
2. Install system dependencies
3. Create Python virtual environment
4. Install Python packages
5. Create/configure .env file
6. Test database connection
7. Import database schema
8. Create initial administrator user
9. Set up directories and permissions

## ⚙️ Manual Installation

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-dev \
    libldap2-dev libsasl2-dev libssl-dev mysql-client
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

Create `.env` file:

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-here-change-this-to-random-32-chars
FLASK_ENV=production

# Database Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=radius
MYSQL_PASSWORD=your-secure-password
MYSQL_DB=radius

# LDAP Configuration
LDAP_SERVER=ldap://192.168.20.184
LDAP_IDENTITY=service.user@domain.com
LDAP_PASSWORD=your-ldap-password
LDAP_BASE_DN=DC=domain,DC=com
LDAP_USER_FILTER=(memberOf=CN=vpnusers,OU=Groups,DC=domain,DC=com)

# VPN Configuration
VPN_SUBNET=10.8.0.0/24
VPN_SERVER_IP=192.168.28.70

# System Configuration
SYSTEM_USER=your-linux-username
```

### 4. Set Up Database

```bash
mysql -u radius -p radius < schema.sql
```

### 5. Create Admin User

```bash
python3 run.py create-admin \
    --username admin \
    --password YourSecurePassword \
    --fullname "Administrator" \
    --email admin@localhost \
    --role Administrator
```

### 6. Create Upload Directory

```bash
mkdir -p app/static/uploads
chmod 755 app/static/uploads
```

## 🏃 Running the Application

### Development Mode

```bash
source venv/bin/activate
python3 run.py
```

Access at: `http://localhost:5000`

### Production Mode (Gunicorn)

```bash
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 run:app
```

### Systemd Service (Recommended for Production)

1. Create service file `/etc/systemd/system/vpn-webui.service`:

```ini
[Unit]
Description=NetAuthVPN Web UI
After=network.target mysql.service

[Service]
Type=simple
User=your-username
Group=your-username
WorkingDirectory=/path/to/netauthvpn
Environment="PATH=/path/to/netauthvpn/venv/bin"
ExecStart=/path/to/netauthvpn/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 run:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn-webui
sudo systemctl start vpn-webui
sudo systemctl status vpn-webui
```

## 👥 User Roles & Permissions

| Feature | Administrator | Operator | Viewer | Auditor |
|---------|--------------|----------|--------|---------|
| Portal User Management | ✅ | ❌ | ❌ | ❌ |
| VPN User Management | ✅ | ✅ | 👁️ | ❌ |
| Security Rules | ✅ | ✅ | 👁️ | ❌ |
| DNS Management | ✅ | ✅ | 👁️ | ❌ |
| Service Control (All) | ✅ | ⚠️ | ❌ | ❌ |
| Accounting Logs | ✅ | ✅ | ✅ | ✅ |
| Audit Logs | ✅ | ❌ | ❌ | ✅ |
| Site Settings | ✅ | ❌ | ❌ | ❌ |
| CSV Export | ✅ | ✅ | ✅ | ✅ |

*Legend: ✅ Full Access, ⚠️ Limited Access, 👁️ View Only, ❌ No Access*

## 📖 Usage Guide

### Portal User Management

1. Navigate to **Admin → Portal Users**
2. Click **Add User** to create new WebUI accounts
3. Assign appropriate roles
4. New users will be forced to change password on first login
5. Manage user status (activate/deactivate)
6. Reset passwords (user must change on next login)

### Site Customization

1. Navigate to **Settings** (Administrator only)
2. Customize:
   - **Site Title**: Displayed in browser and sidebar
   - **Theme Colors**: Primary and secondary gradient colors
   - **Logo**: Upload custom logo (PNG, JPG, SVG)
   - **Favicon**: Upload custom favicon (ICO, PNG)
3. Type hex codes directly or use color picker
4. Changes apply immediately after saving

### VPN User Management

#### Sync from LDAP

1. Navigate to **VPN Users**
2. Click **Sync with LDAP**
3. Users matching the LDAP filter will be imported
4. Each user receives:
   - Next available IP from VPN subnet
   - RADIUS authentication entry
   - Framed-IP-Address attribute

#### Add Custom Routes

1. View user details
2. Click **Add Route**
3. Enter route in CIDR notation (e.g., `192.168.100.0/24`)
4. Route added to RADIUS as Framed-Route

### Security Rules

1. Navigate to **Security Rules**
2. Click **Add Rule**
3. Select user and configure:
   - Destination route (must be in user's routes)
   - Protocol (tcp/udp/icmp/any)
   - Port (optional)
   - Action (ACCEPT/DROP)
4. Click **Apply Rules** to update iptables

### DNS Management

1. Navigate to **DNS Records**
2. Add hostname → IP mappings
3. Click **Apply Changes** to:
   - Update `/etc/hosts`
   - Restart dnsmasq

### Accounting & Logs

1. Navigate to **Accounting**
2. View statistics cards and interactive charts
3. Filter by username, date range, event type
4. Export to CSV with session times and public IPs

### Audit Logs

1. Navigate to **Admin → Audit Logs**
2. Filter by username, action, date range
3. View complete audit trail of portal actions
4. Color-coded action badges

## 🗄️ Database Schema

### WebUI Tables

| Table | Purpose |
|-------|---------|
| `webui_users` | Portal user accounts with roles and password policies |
| `vpn_users` | VPN user management and IP allocation |
| `vpn_user_routes` | Custom routes per VPN user |
| `security_rules` | Per-user firewall rules |
| `dns_records` | Custom DNS hostname mappings |
| `audit_log` | Complete audit trail of admin actions |
| `site_settings` | Site customization (title, logo, theme) |

### RADIUS Tables (Existing)

| Table | Purpose |
|-------|---------|
| `radcheck` | User authentication credentials |
| `radreply` | User attributes (IP, routes) |
| `radacct` | VPN session accounting |
| `radpostauth` | Authentication attempt logs |

## 🔒 Security Considerations

### Sudo Access

Required sudoers configuration (`/etc/sudoers.d/netauthvpn`):

```bash
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl restart openvpn-server@server
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl restart freeradius
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl restart dnsmasq
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl status *
netauthvpn ALL=(ALL) NOPASSWD: /sbin/iptables *
netauthvpn ALL=(ALL) NOPASSWD: /sbin/iptables-save *
netauthvpn ALL=(ALL) NOPASSWD: /sbin/iptables-restore *
netauthvpn ALL=(ALL) NOPASSWD: /bin/cp /tmp/hosts.tmp /etc/hosts
```

### Application Security

- ✅ Password hashing with bcrypt
- ✅ CSRF protection via Flask-WTF
- ✅ Secure session management
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ Complete audit logging with IP tracking
- ✅ Role-based access control
- ✅ Mandatory password change on first login
- ✅ Self-protection (cannot delete own account)

### Best Practices

1. Change default credentials immediately
2. Use strong SECRET_KEY (32+ random characters)
3. Enable HTTPS in production (nginx reverse proxy)
4. Regular database backups
5. Monitor audit logs regularly
6. Limit sudo permissions to minimum required
7. Keep dependencies updated

## 🐛 Troubleshooting

### Cannot Connect to MySQL

```bash
mysql -u radius -p -h localhost radius
cat .env | grep MYSQL
sudo systemctl status mysql
```

### LDAP Sync Fails

```bash
ldapsearch -x -H ldap://server -D "user@domain" -W -b "DC=domain,DC=com"
cat .env | grep LDAP
tail -f logs/vpn_webui.log
```

### Service Restart Fails

```bash
sudo systemctl status openvpn-server@server
sudo -l | grep systemctl
sudo journalctl -u openvpn-server@server -n 50
```

### File Upload Issues

```bash
ls -la app/static/uploads
chmod 755 app/static/uploads
```

## 📡 API Endpoints

### Authentication
- `POST /auth/login` - User login
- `GET /auth/logout` - User logout
- `POST /auth/change-password` - Change password
- `POST /auth/force-password-change` - Mandatory password change

### Dashboard
- `GET /` - Main dashboard with statistics

### VPN Users
- `GET /users` - List VPN users
- `POST /users/sync-ldap` - Sync from LDAP
- `POST /users/<id>/add-route` - Add route
- `GET /users/<id>/download-config` - Download .ovpn

### Security
- `GET /security` - List security rules
- `POST /security/add-rule` - Add rule
- `POST /security/apply-rules/<user_id>` - Apply iptables rules

### DNS
- `GET /dns` - List DNS records
- `POST /dns/add` - Add record
- `POST /dns/apply` - Apply changes

### Accounting
- `GET /accounting` - View logs
- `GET /accounting/export` - Export CSV
- `GET /accounting/stats` - Get chart data (JSON)

### Admin
- `GET /admin/users` - Manage portal users
- `POST /admin/users/add` - Add portal user
- `POST /admin/users/<id>/reset-password` - Reset password
- `GET /admin/audit-logs` - View audit logs

### Settings
- `GET /settings` - View/edit settings
- `POST /settings/update` - Update settings
- `POST /settings/reset-logo` - Remove logo
- `POST /settings/reset-favicon` - Remove favicon

## 🔄 Maintenance

### Backup Database

```bash
mysqldump -u radius -p radius > backup_$(date +%Y%m%d).sql
```

### Update Application

```bash
cd /path/to/netauthvpn
git pull  # If using git
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart vpn-webui
```

### View Logs

```bash
# Application logs
tail -f logs/vpn_webui.log

# Systemd service logs
sudo journalctl -u vpn-webui -f
```

## 📦 Dependencies

See `requirements.txt` for complete list:

- Flask 3.0.0 - Web framework
- Flask-Login - User session management
- Flask-SQLAlchemy - Database ORM
- Flask-WTF - Form handling and CSRF protection
- PyMySQL - MySQL connector
- python-ldap - LDAP integration
- bcrypt - Password hashing
- gunicorn - Production WSGI server

## 📄 License

Internal use only. Proprietary software.

## 🤝 Support

For issues, questions, or feature requests, contact your system administrator.

---

**Version**: 2.1  
**Last Updated**: January 2026  
**Maintained by**: System Administration Team
