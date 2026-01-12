# NetAuthVPN - Infrastructure Scripts

## 🎯 Overview

This project, part of the **NetAuthVPN** solution, provides automated installation and configuration scripts for deploying a production-ready OpenVPN server with FreeRADIUS authentication, LDAP/Active Directory integration, and DNSmasq for DNS forwarding.

### Key Features

- **Unified Authentication**: Single sign-on through LDAP/Active Directory
- **Dynamic IP Assignment**: RADIUS-controlled client IP allocation via `Framed-IP-Address`
- **Centralized Access Control**: User management through RADIUS attributes
- **DNS Forwarding**: Built-in DNSmasq for seamless DNS resolution through VPN tunnel
- **Zero Client Configuration**: Universal `.ovpn` file for all users
- **MySQL Backend**: Persistent storage for accounting and session tracking
- **Custom RADIUS Plugin**: Enhanced OpenVPN-RADIUS integration with advanced attribute support

---

## 📋 Table of Contents

- [Architecture](#architecture)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture Deep Dive](#architecture-deep-dive)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [Advanced Configuration](#advanced-configuration)
- [Contributing](#contributing)

---

## 🏗️ Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPN Client                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  universal-client.ovpn                                    │  │
│  │  - Contains: CA cert, TLS-Crypt key                       │  │
│  │  - Prompts for: Username & Password                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ 1. Connection Request
                             │    (Username/Password)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OpenVPN Server (Port 1194)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OpenVPN Process                                          │  │
│  │  - TLS handshake                                          │  │
│  │  - Certificate validation                                 │  │
│  │  - Extracts username/password                             │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │ 2. RADIUS Auth Request                 │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  RADIUS Plugin (radiusplugin.so)                          │  │
│  │  - Forwards credentials to RADIUS                         │  │
│  │  - Receives RADIUS attributes                             │  │
│  │  - Configures client based on attributes                  │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────────────┘
                         │ 3. Authentication Request
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FreeRADIUS Server (Port 1812/1813)           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Authorization Module                                     │  │
│  │  - Receives Access-Request                                │  │
│  │  - Queries LDAP for user validation                       │  │
│  │  - Queries MySQL for RADIUS attributes                    │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │ 4. LDAP Lookup                          │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LDAP Module                                              │  │
│  │  - Connects to AD/LDAP                                    │  │
│  │  - Validates username/password                            │  │
│  │  - Returns user attributes                                │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       │ 5. SQL Lookup                           │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SQL Module (MySQL)                                       │  │
│  │  - Queries radreply table                                 │  │
│  │  - Retrieves: Framed-IP-Address                           │  │
│  │  - Retrieves: Framed-Route                                │  │
│  │  - Retrieves: Other custom attributes                     │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       │ 6. Access-Accept                        │
│                       │    + RADIUS Attributes                  │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Accounting Module                                        │  │
│  │  - Logs connection to MySQL                               │  │
│  │  - Tracks session data                                    │  │
│  │  - Records bandwidth usage                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                LDAP/Active Directory Server                      │
│  - User database                                                │
│  - Password validation                                          │
│  - Group membership                                             │
└─────────────────────────────────────────────────────────────────┘

                         │ 7. Configuration Applied
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OpenVPN Client Connected                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Assigned Configuration:                                  │  │
│  │  - IP: 10.8.0.X (from Framed-IP-Address)                  │  │
│  │  - Routes: Custom routes (from Framed-Route)              │  │
│  │  - DNS: 192.168.1.100 (VPN server IP)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                       │                                         │
│                       │ DNS Queries                             │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  DNSmasq (Port 53)                                        │  │
│  │  - Receives DNS queries from client                       │  │
│  │  - Forwards to upstream DNS (8.8.8.8, 8.8.4.4)            │  │
│  │  - Returns responses to client                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Client Connection**: User launches VPN client with `universal-client.ovpn`, enters credentials
2. **TLS Handshake**: OpenVPN establishes encrypted tunnel using certificates
3. **RADIUS Authentication**: OpenVPN plugin sends credentials to FreeRADIUS
4. **LDAP Validation**: FreeRADIUS validates credentials against LDAP/AD
5. **Attribute Retrieval**: FreeRADIUS queries MySQL for user-specific attributes
6. **Access Grant**: RADIUS returns Access-Accept with IP assignment and routes
7. **Client Configuration**: OpenVPN applies RADIUS attributes to client connection
8. **DNS Resolution**: Client DNS queries routed through DNSmasq on VPN server

---

## 🔧 Components

### Core Components

| Component | Version | Purpose |
|-----------|---------|---------|
| **OpenVPN** | Latest | VPN server daemon |
| **FreeRADIUS** | 3.0.x | RADIUS authentication server |
| **MySQL** | 8.0+ | RADIUS backend database |
| **DNSmasq** | Latest | DNS forwarding and caching |
| **EasyRSA** | 3.1.6 | PKI certificate management |
| **Custom RADIUS Plugin** | 2.1-9 | Enhanced OpenVPN-RADIUS integration |

### Script Components

1. **setup.sh** - Main orchestration script
2. **openvpn-setup.sh** - OpenVPN configuration and installation
3. **radius-setup.sh** - FreeRADIUS, MySQL, and LDAP setup
4. **.env** - Centralized configuration file

---

## ✅ Prerequisites

### System Requirements

- **Operating System**: Ubuntu 20.04/22.04 or Debian 11/12
- **RAM**: Minimum 2GB (4GB recommended)
- **Disk Space**: Minimum 20GB
- **Network**: Static IP address and public IP/domain
- **Root Access**: Required for installation

### Network Requirements

- **Firewall Ports**:
  - `1194/udp` - OpenVPN (configurable)
  - `1812/udp` - RADIUS Authentication
  - `1813/udp` - RADIUS Accounting
  - `53/udp+tcp` - DNS (DNSmasq)
  - `22/tcp` - SSH (management)
  - `3306/tcp` - MySQL (optional, for remote management)

### External Dependencies

- **LDAP/Active Directory Server**: For user authentication
- **Internet Connection**: For package downloads and updates

---

## 🚀 Installation

### Step 1: Clone or Download Scripts

```bash
# Create project directory
mkdir -p /opt/openvpn-radius-setup
cd /opt/openvpn-radius-setup

# Download scripts (or clone from repository)
# Place setup.sh, openvpn-setup.sh, radius-setup.sh in this directory
```

### Step 2: Create Configuration File

Create a `.env` file in the same directory:

```bash
nano .env
```

Copy and customize the following template:

```bash
#############################################
## Combined .env for OpenVPN + FreeRADIUS + DNS Setup
#############################################

# --- OpenVPN Configuration ---
IP=192.168.1.100                    # VPN Server Internal IP
Public_IP=203.0.113.50              # VPN Server Public IP or Domain
Port=1194
Protocol=udp                        # udp or tcp
Cert_Expiration_Days=365
Server_Subnet=10.8.0.0/24

# --- DNS Configuration for Clients ---
DNS_Server_1=192.168.1.100          # Should match $IP (DNSmasq)
DNS_Server_2=8.8.8.8                # Fallback DNS 1
DNS_Server_3=8.8.4.4                # Fallback DNS 2
DNS_Server_4=                       # Fallback DNS 3 (optional)

# --- DNSmasq Upstream DNS Servers ---
UPSTREAM_DNS=8.8.8.8 8.8.4.4 1.1.1.1

# --- Shared RADIUS Configuration ---
RADIUS_Secret=MyStrongSecretKey2024!
RADIUS_Server=localhost
RADIUS_Auth_Port=1812
RADIUS_Acct_Port=1813

# --- FreeRADIUS + MySQL Configuration ---
MYSQL_ROOT_PASSWORD=YourStrongRootPassword123!
RADIUS_DB_PASSWORD=YourRadiusDBPassword456!

# --- LDAP/Active Directory Configuration ---
LDAP_SERVER=ldap://dc1.company.local
LDAP_IDENTITY=svc_vpn@company.local
LDAP_PASSWORD=YourLDAPServiceAccountPassword
LDAP_BASE_DN=DC=company,DC=local

# --- Optional MySQL Remote Access ---
# REMOTE_ROOT_IP=192.168.1.200
# BIND_ADDRESS=0.0.0.0
```

### Step 3: Make Scripts Executable

```bash
chmod +x setup.sh openvpn-setup.sh radius-setup.sh
```

### Step 4: Run Installation

```bash
# Full installation (recommended)
sudo ./setup.sh

# Or run individual components:
sudo ./setup.sh --radius      # Only FreeRADIUS
sudo ./setup.sh --openvpn     # Only OpenVPN
sudo ./setup.sh --dns         # Only DNSmasq
sudo ./setup.sh --firewall    # Only firewall rules
```

### Installation Time

- **Full Setup**: 5-10 minutes
- **Individual Components**: 2-5 minutes each

---

## ⚙️ Configuration

### Environment Variables Reference

#### OpenVPN Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IP` | Yes | - | VPN server internal IP (used as DNS for clients) |
| `Public_IP` | Yes | - | Public IP or domain for client connections |
| `Port` | Yes | 1194 | OpenVPN listening port |
| `Protocol` | Yes | udp | Protocol (udp or tcp) |
| `Server_Subnet` | No | 10.8.0.0/24 | VPN subnet for clients |
| `Cert_Expiration_Days` | No | 365 | Certificate validity period |

#### DNS Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DNS_Server_1` | Yes | - | Primary DNS (should match $IP) |
| `DNS_Server_2` | No | - | Fallback DNS server |
| `DNS_Server_3` | No | - | Fallback DNS server |
| `DNS_Server_4` | No | - | Fallback DNS server |
| `UPSTREAM_DNS` | Yes | - | Space-separated upstream DNS servers for DNSmasq |

#### RADIUS Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RADIUS_Secret` | Yes | - | Shared secret (must match on both sides) |
| `RADIUS_Server` | No | localhost | RADIUS server address |
| `RADIUS_Auth_Port` | No | 1812 | Authentication port |
| `RADIUS_Acct_Port` | No | 1813 | Accounting port |

#### Database Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MYSQL_ROOT_PASSWORD` | Yes | - | MySQL root password |
| `RADIUS_DB_PASSWORD` | Yes | - | RADIUS database user password |
| `REMOTE_ROOT_IP` | No | - | IP allowed for remote MySQL access |
| `BIND_ADDRESS` | No | 0.0.0.0 | MySQL bind address |

#### LDAP Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LDAP_SERVER` | Yes | - | LDAP/AD server URI |
| `LDAP_IDENTITY` | Yes | - | LDAP service account |
| `LDAP_PASSWORD` | Yes | - | LDAP service account password |
| `LDAP_BASE_DN` | Yes | - | Base DN for searches |
| `LDAP_USER_FILTER` | No | Auto-generated | Custom LDAP filter |

---

## 📖 Usage

### Distributing Client Configuration

After installation, distribute the universal client configuration to users:

```bash
# Show client configuration location
distribute-vpn-client

# Copy to specific path
distribute-vpn-client --copy /tmp/client.ovpn

# Copy to user's home directory
distribute-vpn-client --user username
```

The universal client configuration is located at:
```
/etc/openvpn/clients/universal-client.ovpn
```

### Connecting Clients

1. **Download** `universal-client.ovpn` to client device
2. **Import** into OpenVPN client (OpenVPN GUI, Tunnelblick, etc.)
3. **Connect** and enter LDAP/AD credentials when prompted

### Managing Users in RADIUS

#### Assign Static IP to User

```sql
# Connect to MySQL
mysql -u root -p

# Select RADIUS database
USE radius;

# Assign IP to user
INSERT INTO radreply (username, attribute, op, value)
VALUES ('john.doe', 'Framed-IP-Address', ':=', '10.8.0.50');
```

#### Assign Custom Routes

```sql
# Add custom route for user
INSERT INTO radreply (username, attribute, op, value)
VALUES ('john.doe', 'Framed-Route', '+=', '192.168.10.0/24 10.8.0.1');
```

#### View Active Sessions

```sql
# Check active VPN sessions
SELECT * FROM radacct WHERE acctstoptime IS NULL;
```

#### View Authentication History

```sql
# Recent authentication attempts
SELECT username, reply, authdate 
FROM radpostauth 
ORDER BY authdate DESC 
LIMIT 20;
```

### Service Management

```bash
# Check service status
systemctl status openvpn-server@server
systemctl status freeradius
systemctl status mysql
systemctl status dnsmasq

# Restart services
systemctl restart openvpn-server@server
systemctl restart freeradius

# View logs
tail -f /var/log/openvpn/status.log
tail -f /var/log/freeradius/radius.log
tail -f /var/log/dnsmasq.log
```

---

## 🔍 Architecture Deep Dive

### OpenVPN Configuration

#### Certificate Infrastructure

The setup uses **EasyRSA 3.1.6** with elliptic curve cryptography:

- **Algorithm**: ECDSA
- **Curve**: prime256v1
- **Key Size**: 256-bit
- **Certificate Validity**: Configurable (default 365 days)

#### Security Features

- **TLS-Crypt**: Pre-shared key for additional security layer
- **TLS 1.2+**: Minimum TLS version enforced
- **Cipher**: AES-256-GCM
- **Auth**: SHA256
- **No DH Parameters**: Uses ECDH instead (modern approach)

#### Client Configuration Model

**Universal Configuration Approach**:
- Single `.ovpn` file for all users
- No client-specific certificates required
- Authentication via username/password (RADIUS)
- Dynamic configuration via RADIUS attributes

### FreeRADIUS Configuration

#### Module Stack

1. **Authorization** (`authorize {}`)
   - `filter_username` - Username sanitization
   - `preprocess` - Request preprocessing
   - `ldap` - LDAP authentication check
   - `sql` - Retrieve RADIUS attributes from MySQL
   - `expiration` - Check account expiration
   - `logintime` - Check time-based restrictions

2. **Authentication** (`authenticate {}`)
   - `Auth-Type LDAP` - LDAP password validation

3. **Accounting** (`accounting {}`)
   - `sql` - Log session data to MySQL
   - `acct_unique` - Ensure unique accounting records

4. **Post-Authentication** (`post-auth {}`)
   - `sql` - Log successful authentications
   - Handle rejected authentication attempts

#### RADIUS Attributes

**Standard Attributes**:
- `Framed-IP-Address` - Assign specific IP to user
- `Framed-Route` - Push custom routes to client
- `Session-Timeout` - Maximum session duration
- `Idle-Timeout` - Idle timeout before disconnect

**VSA (Vendor-Specific Attributes)** - Supported via custom plugin

#### Database Schema

Key tables in the `radius` database:

```sql
-- User authentication
radcheck      -- User passwords (not used with LDAP)
radreply      -- User-specific reply attributes
radgroupcheck -- Group check attributes
radgroupreply -- Group reply attributes
radusergroup  -- User-to-group mapping

-- Accounting
radacct       -- Active and historical sessions
radpostauth   -- Authentication log (no passwords stored)

-- Client management
nas           -- RADIUS clients (NAS devices)
```

### DNSmasq Integration

#### DNS Flow

```
Client Query → VPN Tunnel → DNSmasq (VPN Server IP) → Upstream DNS → Internet
```

#### Configuration Highlights

- **Listen Address**: All interfaces (including VPN tunnel)
- **Upstream DNS**: Configurable via `UPSTREAM_DNS` (.env)
- **Custom Records**: `/etc/hosts` for local name resolution
- **Caching**: Built-in DNS caching for performance
- **Logging**: `/var/log/dnsmasq.log` for query tracking

### Firewall Architecture

#### iptables Rules

**INPUT Chain**:
- SSH (22/tcp) - Management access
- OpenVPN (1194/udp) - VPN connections
- DNS (53/udp+tcp) - Client DNS queries
- RADIUS (1812-1813/udp) - Authentication/Accounting
- MySQL (3306/tcp) - Optional remote access

**FORWARD Chain**:
- VPN ↔ Internet traffic
- DNS forwarding from VPN clients

**NAT Table**:
- MASQUERADE for VPN subnet (POSTROUTING)

---

## 🐛 Troubleshooting

### Common Issues

#### 1. FreeRADIUS Won't Start

**Check logs**:
```bash
sudo systemctl status freeradius
sudo freeradius -X  # Debug mode
```

**Common causes**:
- Invalid LDAP credentials in `.env`
- MySQL connection failure
- Port conflicts (1812/1813)

**Solution**:
```bash
# Test LDAP connectivity
ldapsearch -x -H "$LDAP_SERVER" -D "$LDAP_IDENTITY" -w "$LDAP_PASSWORD" -b "$LDAP_BASE_DN"

# Test MySQL connectivity
mysql -u radius -p"$RADIUS_DB_PASSWORD" radius -e "SELECT 1;"
```

#### 2. OpenVPN Clients Can't Connect

**Check OpenVPN logs**:
```bash
tail -f /var/log/openvpn/status.log
journalctl -u openvpn-server@server -f
```

**Common causes**:
- Firewall blocking port
- Incorrect Public_IP in `.env`
- RADIUS authentication failure

**Solution**:
```bash
# Test firewall
sudo iptables -L -n -v | grep 1194

# Test RADIUS from OpenVPN server
echo "User-Name=testuser,User-Password=testpass" | radclient -x localhost:1812 auth "$RADIUS_Secret"
```

#### 3. DNS Not Working for Clients

**Check DNSmasq status**:
```bash
sudo systemctl status dnsmasq
tail -f /var/log/dnsmasq.log
```

**Test DNS resolution**:
```bash
# From VPN server
dig @127.0.0.1 google.com

# From client (after connecting)
nslookup google.com 10.8.0.1
```

**Common causes**:
- systemd-resolved conflict (port 53)
- Wrong upstream DNS servers
- Firewall blocking DNS

#### 4. LDAP Authentication Fails

**Test LDAP directly**:
```bash
# From RADIUS server
ldapsearch -x -H "$LDAP_SERVER" \
  -D "$LDAP_IDENTITY" \
  -w "$LDAP_PASSWORD" \
  -b "$LDAP_BASE_DN" \
  "(sAMAccountName=username)"
```

**Check RADIUS debug**:
```bash
sudo freeradius -X
# Then attempt authentication
```

### Debug Mode

#### FreeRADIUS Debug Mode

```bash
# Stop service
sudo systemctl stop freeradius

# Run in debug mode
sudo freeradius -X

# In another terminal, test
echo "User-Name=testuser,User-Password=testpass" | \
  radclient -x localhost:1812 auth "$RADIUS_Secret"
```

#### OpenVPN Debug Mode

Edit `/etc/openvpn/server/server.conf`:
```
verb 4  # Increase verbosity (0-11)
```

Then restart:
```bash
sudo systemctl restart openvpn-server@server
```

### Log Locations

| Service | Log Location |
|---------|-------------|
| OpenVPN | `/var/log/openvpn/status.log` |
| FreeRADIUS | `/var/log/freeradius/radius.log` |
| DNSmasq | `/var/log/dnsmasq.log` |
| MySQL | `/var/log/mysql/error.log` |
| System | `journalctl -u <service-name>` |

---

## 🔒 Security Considerations

### Best Practices

1. **Strong Passwords**
   - Use complex passwords for all `.env` variables
   - Minimum 16 characters with mixed case, numbers, symbols
   - Rotate passwords regularly

2. **Certificate Security**
   - Protect private keys in `/etc/openvpn/server/`
   - Set restrictive permissions (600 for keys)
   - Consider shorter certificate validity periods

3. **RADIUS Secret**
   - Use cryptographically random secret
   - Minimum 20 characters
   - Never reuse across environments

4. **Firewall Hardening**
   - Allow only necessary ports
   - Use IP whitelisting where possible
   - Enable fail2ban for brute force protection

5. **LDAP Service Account**
   - Create dedicated service account with minimal privileges
   - Read-only access to user directory
   - Monitor for unauthorized access

6. **MySQL Security**
   - Disable remote root access unless required
   - Use strong RADIUS database password
   - Regular database backups

## 🎛️ Advanced Configuration

### Custom LDAP Filters

Restrict VPN access to specific AD groups:

```bash
# In .env file
LDAP_USER_FILTER="(&(sAMAccountName=%{%{Stripped-User-Name}:-%{User-Name}})(memberOf=CN=VPN-Users,OU=Groups,DC=company,DC=local))"
```
## 📚 Additional Resources

### Documentation

- [OpenVPN Official Documentation](https://openvpn.net/community-resources/)
- [FreeRADIUS Documentation](https://freeradius.org/documentation/)
- [DNSmasq Man Page](http://www.thekelleys.org.uk/dnsmasq/doc.html)
- [EasyRSA Documentation](https://easy-rsa.readthedocs.io/)

### Useful Commands Reference

```bash
# RADIUS testing
radtest <username> <password> localhost 0 <secret>

# OpenVPN status
systemctl status openvpn-server@server

# List connected clients
cat /var/log/openvpn/status.log

# MySQL RADIUS queries
mysql -u radius -p radius

# Check certificate expiration
openssl x509 -in /etc/openvpn/server/ca.crt -noout -dates

# View firewall rules
iptables -L -n -v

# DNS query test
dig @<DNS_SERVER> <domain>
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit pull request with detailed description

---

## 📄 License

This project is provided as-is for educational and production use. Please review and comply with the licenses of all included components:

- OpenVPN: GNU GPL v2
- FreeRADIUS: GNU GPL v2
- MySQL: GNU GPL v2 or Commercial
- DNSmasq: GNU GPL v2 or v3

---

## 👤 Author

**Generated by AI Assistant**
- Scripts orchestrated for production-ready deployment
- Comprehensive documentation for enterprise use

---

## 🔄 Changelog

### Version 1.0.0
- Initial release
- OpenVPN + FreeRADIUS + LDAP integration
- DNSmasq DNS forwarding
- Universal client configuration
- Custom RADIUS plugin support
- MySQL backend for accounting
- Automated firewall configuration

---

## ⚠️ Disclaimer

This software is provided "as is" without warranty of any kind. Always test in a non-production environment first. Ensure compliance with your organization's security policies before deployment.

---

## 📞 Support

For issues and questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review service logs
3. Consult official documentation for each component
4. Open an issue in the repository (if applicable)

---

**Last Updated**: January 2026