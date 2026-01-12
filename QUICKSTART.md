# NetAuthVPN - Quick Start Guide

## Installation Steps

1. **Navigate to webui directory:**
   ```bash
   cd /home/dipakc/vpn-gw/webui
   ```

2. **Run installation script:**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **Follow prompts to create admin user**

4. **Start the application:**
   ```bash
   source venv/bin/activate
   python3 run.py
   ```

5. **Access Web UI:**
   ```
   http://YOUR_SERVER_IP:5000
   ```

## First Time Setup

1. **Login** with admin credentials you created
2. **Sync LDAP Users**: Navigate to VPN Users → Click "Sync with LDAP"
3. **Verify IP Allocation**: Check each user has an assigned IP
4. **Add Routes** (optional): Click on a user → Add Route
5. **Configure Security Rules** (optional): Security Rules → Select user → Add rules
6. **Add DNS Records** (optional): DNS Records → Add custom entries

## Key Features

- **Dashboard**: Overview of connections, data usage, service status
- **VPN Users**: LDAP sync, IP management, route configuration
- **Security Rules**: Per-user firewall rules (iptables)
- **DNS Records**: Custom DNS via /etc/hosts + dnsmasq
- **Accounting**: SIEM-style logs with CSV export
- **Services**: Monitor and restart services

## Role Permissions

| Feature | Admin | Operator | Viewer | Auditor |
|---------|-------|----------|---------|---------|
| Dashboard | ✓ | ✓ | ✓ | ✓ |
| VPN Users (view) | ✓ | ✓ | ✓ | - |
| VPN Users (edit) | ✓ | ✓ | - | - |
| LDAP Sync | ✓ | ✓ | - | - |
| Security Rules | ✓ | ✓ | - | - |
| DNS Management | ✓ | ✓ | - | - |
| Accounting | ✓ | ✓ | ✓ | ✓ |
| Services (view) | ✓ | ✓ | ✓ | - |
| Restart OpenVPN | ✓ | - | - | - |
| Restart FreeRADIUS | ✓ | - | - | - |
| Restart dnsmasq | ✓ | ✓ | - | - |

## Troubleshooting

**Can't access Web UI:**
- Check if service is running: `ps aux | grep python3`
- Check firewall: `sudo iptables -L | grep 5000`

**LDAP sync fails:**
- Verify credentials in `.env`
- Test: `ldapsearch -x -H $LDAP_SERVER -D "$LDAP_IDENTITY" -W`

**Database errors:**
- Check MySQL is running: `sudo systemctl status mysql`
- Verify credentials: `mysql -u radius -p`

**Service restart fails:**
- Check sudo access: `sudo -l`
- Test manually: `sudo systemctl restart dnsmasq`

## Production Deployment

For production use with Gunicorn:

```bash
cd /home/dipakc/vpn-gw/webui
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 --access-logfile logs/access.log --error-logfile logs/error.log run:app
```

Or use systemd service (see README.md).

## Important Notes

1. **RADIUS Integration**: All IP assignments and routes are stored in `radreply` table
2. **Iptables**: Rules are applied immediately but require "Apply Rules" button
3. **DNS**: Changes require clicking "Apply Changes" to update /etc/hosts and restart dnsmasq
4. **Audit Trail**: All admin actions are logged in `audit_log` table

## Support

For detailed documentation, see `README.md` in the webui directory.
