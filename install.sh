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
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "[1/9] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "Found Python $PYTHON_VERSION"

echo ""
echo "[2/9] Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv python3-dev libldap2-dev libsasl2-dev libssl-dev mysql-client

echo ""
echo "[3/9] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

echo ""
echo "[4/9] Activating virtual environment and installing Python packages..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo ""
echo "[5/9] Checking .env configuration..."

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
echo "[6/9] Testing database connection..."
if ! mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -h"$MYSQL_HOST" -e "SELECT 1;" &> /dev/null; then
    echo "[ERROR] Cannot connect to MySQL database"
    echo "Please check your database credentials in .env"
    exit 1
fi
echo "Database connection successful"

echo ""
echo "[7/9] Importing database schema..."
mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" -h"$MYSQL_HOST" "$MYSQL_DB" < schema.sql
echo "Database schema imported successfully"

echo ""
echo "[8/9] Creating initial admin user..."
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
echo "[9/9] Setting up directories and permissions..."
mkdir -p logs
mkdir -p app/static/uploads
chmod 755 logs
chmod 755 app/static/uploads

echo ""
echo "========================================"
echo " Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
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
echo "Optional: Set up systemd service for auto-start"
echo "   See README.md for systemd configuration"
echo ""
