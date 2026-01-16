#!/bin/bash
# NetAuthVPN Installation Script
# This script sets up the Web UI application with all dependencies

set -e

echo "========================================"
echo " NetAuthVPN - Installation"
echo "========================================"
echo ""

# Check if running as root (we need sudo access)
if [ "$EUID" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "[ERROR] This script requires sudo access"
    exit 1
fi

# Get the directory where the script is located
SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_DIR="/opt/netauthapp"

echo "[1/10] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "Found Python $PYTHON_VERSION"

echo ""
echo "[2/10] Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv python3-dev libldap2-dev libsasl2-dev libssl-dev mysql-client rsync

echo ""
echo "[3/10] deploying to $INSTALL_DIR..."
if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying files to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    
    # Sync files excluding venv, logs, uploads, .git, .env, __pycache__
    rsync -av --exclude 'venv' \
              --exclude 'logs' \
              --exclude 'app/static/uploads' \
              --exclude '.git' \
              --exclude '.env' \
              --exclude '__pycache__' \
              --exclude '*.pyc' \
              "$SOURCE_DIR/" "$INSTALL_DIR/"
    
    echo "Files deployed successfully."
    cd "$INSTALL_DIR"
    SCRIPT_DIR="$INSTALL_DIR"
else
    echo "Already running from $INSTALL_DIR"
    SCRIPT_DIR="$INSTALL_DIR"
fi

echo ""
echo "[4/10] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

echo ""
echo "[5/10] Activating virtual environment and installing Python packages..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo ""
echo "[6/10] Checking .env configuration..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "[WARNING] .env file not found!"
    echo "Creating .env from template..."
    
    read -p "MySQL Host [localhost]: " MYSQL_HOST
    MYSQL_HOST=${MYSQL_HOST:-localhost}
    
    read -p "MySQL User [radius]: " MYSQL_USER
    MYSQL_USER=${MYSQL_USER:-radius}
    
    read -sp "MySQL Password: " MYSQL_PASSWORD
    echo ""
    
    read -p "MySQL Database [radius]: " MYSQL_DB
    MYSQL_DB=${MYSQL_DB:-radius}
    
    read -p "LDAP Server [ldap://localhost]: " LDAP_SERVER
    LDAP_SERVER=${LDAP_SERVER:-ldap://localhost}
    
    read -p "LDAP Identity: " LDAP_IDENTITY
    read -sp "LDAP Password: " LDAP_PASSWORD
    echo ""
    
    read -p "LDAP Base DN: " LDAP_BASE_DN
    read -p "VPN Subnet [10.8.0.0/24]: " VPN_SUBNET
    VPN_SUBNET=${VPN_SUBNET:-10.8.0.0/24}
    
    read -p "VPN Server IP: " VPN_SERVER_IP
    
    # Generate random secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    
    cat > .env << EOF
# Flask Configuration
SECRET_KEY=$SECRET_KEY
FLASK_ENV=production

# Database Configuration
MYSQL_HOST=$MYSQL_HOST
MYSQL_PORT=3306
MYSQL_USER=$MYSQL_USER
MYSQL_PASSWORD=$MYSQL_PASSWORD
MYSQL_DB=$MYSQL_DB

# LDAP Configuration
LDAP_SERVER=$LDAP_SERVER
LDAP_IDENTITY=$LDAP_IDENTITY
LDAP_PASSWORD=$LDAP_PASSWORD
LDAP_BASE_DN=$LDAP_BASE_DN
LDAP_USER_FILTER=(memberOf=CN=vpnusers,OU=Groups,$LDAP_BASE_DN)

# VPN Configuration
VPN_SUBNET=$VPN_SUBNET
VPN_SERVER_IP=$VPN_SERVER_IP

# System Configuration
SYSTEM_USER=$(whoami)
EOF
    
    echo ".env file created successfully"
fi

# Source .env to get MySQL credentials
set -a
source .env
set +a

echo ""
echo "[7/10] Testing database connection..."
if ! mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -h"$MYSQL_HOST" -e "SELECT 1;" &> /dev/null; then
    echo "[ERROR] Cannot connect to MySQL database"
    echo "Please check your database credentials in .env"
    exit 1
fi
echo "Database connection successful"

echo ""
echo "[8/10] Importing database schema..."
mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -h"$MYSQL_HOST" "$MYSQL_DB" < schema.sql
echo "Database schema imported successfully"

echo ""
echo "[9/10] Creating initial admin user..."
read -p "Create admin user? (Y/n): " CREATE_ADMIN
CREATE_ADMIN=${CREATE_ADMIN:-Y}

if [ "$CREATE_ADMIN" = "y" ] || [ "$CREATE_ADMIN" = "Y" ]; then
    read -p "Admin username [admin]: " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}
    
    read -p "Admin full name [Administrator]: " ADMIN_NAME
    ADMIN_NAME=${ADMIN_NAME:-Administrator}
    
    read -p "Admin email [admin@localhost]: " ADMIN_EMAIL
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@localhost}
    
    read -sp "Admin password: " ADMIN_PASS
    echo ""
    
    if [ -z "$ADMIN_PASS" ]; then
        echo "[ERROR] Password cannot be empty"
        exit 1
    fi
    
    python3 run.py create-admin \
        --username "$ADMIN_USER" \
        --password "$ADMIN_PASS" \
        --fullname "$ADMIN_NAME" \
        --email "$ADMIN_EMAIL" \
        --role Administrator || echo "Note: User may already exist"
    
    echo "Admin user created successfully"
fi

echo ""
echo "[10/10] Setting up directories and permissions..."
mkdir -p logs
mkdir -p app/static/uploads
chmod 755 logs
chmod 755 app/static/uploads


echo ""
echo "[Additional] Systemd Service Setup"
read -p "Do you want to setup systemd service for NetAuthVPN? (Y/n): " SETUP_SERVICE
SETUP_SERVICE=${SETUP_SERVICE:-Y}

if [ "$SETUP_SERVICE" = "y" ] || [ "$SETUP_SERVICE" = "Y" ]; then
    echo "Setting up NetAuthVPN service..."
    
    # Create system user
    if ! id "netauthvpn" &>/dev/null; then
        useradd -r -s /bin/false netauthvpn
        echo "Created system user 'netauthvpn'"
    else
        echo "User 'netauthvpn' already exists"
    fi
    
    # Configure sudoers
    echo "Configuring sudoers permissions..."
    cat > /etc/sudoers.d/netauthvpn << 'EOF'
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl restart openvpn-server@server
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl restart freeradius
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl restart dnsmasq
netauthvpn ALL=(ALL) NOPASSWD: /bin/systemctl status *
netauthvpn ALL=(ALL) NOPASSWD: /sbin/iptables *
netauthvpn ALL=(ALL) NOPASSWD: /sbin/iptables-save *
netauthvpn ALL=(ALL) NOPASSWD: /sbin/iptables-restore *
netauthvpn ALL=(ALL) NOPASSWD: /usr/sbin/netfilter-persistent *
netauthvpn ALL=(ALL) NOPASSWD: /bin/cp /tmp/hosts.tmp /etc/hosts
EOF
    chmod 0440 /etc/sudoers.d/netauthvpn
    
    # Create service file
    echo "Creating systemd service file..."
    cat > /etc/systemd/system/netauthvpn.service << EOF
[Unit]
Description=NetAuthVPN Web UI
After=network.target mysql.service

[Service]
Type=simple
User=netauthvpn
Group=netauthvpn
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin"
ExecStart=$SCRIPT_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 run:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Set ownership
    echo "Setting directory ownership..."
    chown -R netauthvpn:netauthvpn "$SCRIPT_DIR"
    
    # Enable and start service
    echo "Enabling and starting service..."
    systemctl daemon-reload
    systemctl enable netauthvpn
    systemctl start netauthvpn
    
    echo "✅ Service 'netauthvpn' is active and running!"
    echo "   Access at: http://$(hostname -I | awk '{print $1}'):5000"

else
    echo "Skipping service setup."
    
    echo ""
    echo "========================================"
    echo " Installation Complete!"
    echo "========================================"
    echo ""
    echo "Manual Run Steps:"
    echo ""
    echo "1. Start the application:"
    echo "   cd $SCRIPT_DIR"
    echo "   source venv/bin/activate"
    echo "   python3 run.py"
    echo ""
    echo "2. Access the web interface:"
    echo "   http://$(hostname -I | awk '{print $1}'):5000"
    echo ""
    echo "3. Login with your admin credentials"
    echo ""
    echo "For production deployment with Gunicorn:"
    echo "   gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 run:app"
    echo ""
fi
