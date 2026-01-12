#!/bin/bash

# Exit on errors
set -e

# --- Check if script is run as root ---
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: This script must be run as root!"
        exit 1
    fi
}

# --- Load and validate .env file ---
load_env() {
    ENV_FILE=".env"
    if [ ! -f "$ENV_FILE" ]; then
        echo "Error: $ENV_FILE not found!"
        exit 1
    fi

    # Source .env variables
    set -a
    source "$ENV_FILE"
    set +a

    # Required variables
    : "${IP:?Error: IP must be set in $ENV_FILE}"
    : "${Public_IP:?Error: Public_IP must be set in $ENV_FILE}"
    : "${Port:?Error: Port must be set in $ENV_FILE}"
    : "${Protocol:?Error: Protocol must be set in $ENV_FILE}"
    : "${DNS_Server_1:?Error: At least DNS_Server_1 must be set in $ENV_FILE}"
    : "${RADIUS_Server:?Error: RADIUS_Server IP is required in $ENV_FILE}"
    : "${RADIUS_Secret:?Error: RADIUS_Secret is required in $ENV_FILE}"

    # Validate port
    if ! [[ "$Port" =~ ^[0-9]+$ ]] || [ "$Port" -lt 1 ] || [ "$Port" -gt 65535 ]; then
        echo "Error: Port must be a number between 1 and 65535"
        exit 1
    fi

    # Validate protocol
    Protocol=$(echo "$Protocol" | tr '[:upper:]' '[:lower:]')
    if [ "$Protocol" != "udp" ] && [ "$Protocol" != "tcp" ]; then
        echo "Error: Protocol must be UDP or TCP"
        exit 1
    fi

    # Validate DNS servers
    for dns in "$DNS_Server_1" "$DNS_Server_2" "$DNS_Server_3" "$DNS_Server_4"; do
        if [ -n "$dns" ] && ! echo "$dns" | grep -qE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
            echo "Error: Invalid DNS server IP: $dns"
            exit 1
        fi
    done

    # Defaults
    Cert_Expiration_Days=${Cert_Expiration_Days:-365}
    Server_Subnet=${Server_Subnet:-10.8.0.0/24}
    Server_mask="255.255.255.0" # Simplified for /24 subnet
    RADIUS_Auth_Port=${RADIUS_Auth_Port:-1812}
    RADIUS_Acct_Port=${RADIUS_Acct_Port:-1813}
}

# --- Detect operating system ---
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_NAME=$ID
        OS_VERSION=$VERSION_ID
        case "$ID" in
            ubuntu|debian)
                OS_FAMILY="debian"
                ;;
            *)
                echo "Error: This script only supports Ubuntu/Debian"
                exit 1
                ;;
        esac
    else
        echo "Error: Cannot detect OS. /etc/os-release not found."
        exit 1
    fi
    echo "Detected OS: $OS_NAME $OS_VERSION"
}

# --- Install custom RADIUS plugin from GitHub ---
install_custom_radius_plugin() {
    echo "Installing custom RADIUS plugin from GitHub..."
    
    # Clone the repository
    cd /tmp
    if [ -d "OpenVPN-Auth-Radius-Plugin-Customized" ]; then
        rm -rf OpenVPN-Auth-Radius-Plugin-Customized
    fi
    
    git clone https://github.com/dipakchaulagain/OpenVPN-Auth-Radius-Plugin-Customized.git
    cd OpenVPN-Auth-Radius-Plugin-Customized
    
    # Check if the .deb file exists
    if [ ! -f "openvpn-auth-radius_2.1-9_amd64.deb" ]; then
        echo "Error: openvpn-auth-radius_2.1-9_amd64.deb not found in repository!"
        exit 1
    fi
    
    # Install the .deb package
    dpkg -i openvpn-auth-radius_2.1-9_amd64.deb || {
        echo "Attempting to fix dependencies..."
        apt install -f -y
        dpkg -i openvpn-auth-radius_2.1-9_amd64.deb
    }
    
    echo "Custom RADIUS plugin installed successfully."
}

# --- Install dependencies ---
install_dependencies() {
    echo "Installing dependencies..."
    apt update
    
    # Install standard packages
    apt install -y openvpn iptables iptables-persistent wget openssl git
    
    # Install the custom RADIUS plugin
    install_custom_radius_plugin
    
    echo "Dependencies installed."
}

# --- Configure OpenVPN with Single CA & Radius ---
configure_openvpn() {
    echo "Configuring OpenVPN with RADIUS Authentication..."

    # Install EasyRSA
    local version="3.1.6"
    cd /tmp
    wget -q https://github.com/OpenVPN/easy-rsa/releases/download/v${version}/EasyRSA-${version}.tgz
    tar -xzf EasyRSA-${version}.tgz
    rm -rf /etc/openvpn/easy-rsa 2>/dev/null || true
    mv /tmp/EasyRSA-${version}/ /etc/openvpn/easy-rsa
    chown -R root:root /etc/openvpn/easy-rsa/
    rm -f /tmp/EasyRSA-${version}.tgz

    cd /etc/openvpn/easy-rsa/
    cat > vars <<EOF
set_var EASYRSA_ALGO ec
set_var EASYRSA_CURVE prime256v1
set_var EASYRSA_KEY_SIZE 256
set_var EASYRSA_CA_EXPIRE $Cert_Expiration_Days
set_var EASYRSA_CERT_EXPIRE $Cert_Expiration_Days
EOF

    ./easyrsa init-pki
    echo "Building Certificate Authority (CA)..."
    ./easyrsa --batch build-ca nopass
    SERVER_NAME="server"
    echo "Generating server certificate..."
    ./easyrsa --batch gen-req "$SERVER_NAME" nopass
    ./easyrsa --batch sign-req server "$SERVER_NAME"
    ./easyrsa gen-crl
    openvpn --genkey secret pki/tls-crypt.key

    mkdir -p /etc/openvpn/server
    cp pki/ca.crt pki/private/ca.key "pki/issued/$SERVER_NAME.crt" "pki/private/$SERVER_NAME.key" pki/tls-crypt.key /etc/openvpn/server
    cp pki/crl.pem /etc/openvpn
    chmod 644 /etc/openvpn/crl.pem

    # Determine nobody group
    NOBODY_GROUP=$(getent group nogroup >/dev/null && echo "nogroup" || echo "nobody")

    NET_IFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
    if [ -z "$NET_IFACE" ]; then
        NET_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    fi
    SUBNET_IP=$(echo "$Server_Subnet" | cut -d'/' -f1)

    # Create OpenVPN server configuration WITHOUT CCD
    cat > /etc/openvpn/server/server.conf <<EOF
port $Port
proto $Protocol
dev tun
user nobody
group $NOBODY_GROUP
persist-key
persist-tun
keepalive 10 120
topology subnet
server $SUBNET_IP $Server_mask
ca ca.crt
cert $SERVER_NAME.crt
key $SERVER_NAME.key
tls-crypt tls-crypt.key
crl-verify /etc/openvpn/crl.pem
dh none
ecdh-curve prime256v1
tls-server
tls-version-min 1.2
cipher AES-256-GCM
auth SHA256
username-as-common-name
verify-client-cert none
client-config-dir /etc/openvpn/ccd
ccd-exclusive
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS $DNS_Server_1"
$( [ -n "$DNS_Server_2" ] && echo "push \"dhcp-option DNS $DNS_Server_2\"" )
$( [ -n "$DNS_Server_3" ] && echo "push \"dhcp-option DNS $DNS_Server_3\"" )
$( [ -n "$DNS_Server_4" ] && echo "push \"dhcp-option DNS $DNS_Server_4\"" )
push "route $IP 255.255.255.255"
status /var/log/openvpn/status.log
verb 3
plugin /usr/lib/openvpn/radiusplugin.so /etc/openvpn/radiusplugin.cnf
EOF

    # Create directory for log files
    mkdir -p /var/log/openvpn
    chown nobody:$NOBODY_GROUP /var/log/openvpn
    chmod 775 /var/log/openvpn

    # Create directory for client configurations
    mkdir -p /etc/openvpn/clients
    chmod 755 /etc/openvpn/clients
    echo "Created client directory: /etc/openvpn/clients"

    # Enable IP forwarding
    echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/20-openvpn.conf
    sysctl -p /etc/sysctl.d/20-openvpn.conf

    # Note: Firewall configuration moved to main setup.sh
    echo "Note: Firewall rules will be configured by the main setup script"

    # --- Create RADIUS Plugin Configuration ---
    cat > /etc/openvpn/radiusplugin.cnf <<EOF
NAS-Identifier=OpenVPN-Server
Service-Type=2
Framed-Protocol=1
NAS-Port-Type=5
NAS-IP-Address=$IP
OpenVPNConfig=/etc/openvpn/server/server.conf
subnet=$Server_mask
overwriteccfiles=true
server
{
    acctport=$RADIUS_Acct_Port
    authport=$RADIUS_Auth_Port
    name=$RADIUS_Server
    retry=1
    wait=5
    sharedsecret=$RADIUS_Secret
}
EOF

    # --- Create Universal Client Configuration ---
    # Store in /etc/openvpn/clients/ directory
    CLIENT_FILE="/etc/openvpn/clients/universal-client.ovpn"
    
    cat > "$CLIENT_FILE" <<EOF
client
proto $Protocol
remote $Public_IP $Port
dev tun
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
auth SHA256
cipher AES-256-GCM
tls-client
tls-version-min 1.2
verb 3
auth-user-pass
<ca>
$(cat /etc/openvpn/server/ca.crt)
</ca>
<tls-crypt>
$(cat /etc/openvpn/server/tls-crypt.key)
</tls-crypt>
EOF

    # Set permissions on the client file
    chmod 644 "$CLIENT_FILE"
    
    echo "Universal client configuration created: $CLIENT_FILE"
    echo "All users will use this single configuration file."
    echo "RADIUS server will assign individual IPs and routes via Framed-IP-Address and Framed-Route attributes."

    # --- Create client distribution script ---
    cat > /usr/local/bin/distribute-vpn-client <<'EOF'
#!/bin/bash
# Script to copy the universal client template to various locations
SCRIPT_NAME=$(basename "$0")

usage() {
    echo "Usage: $SCRIPT_NAME [OPTION]"
    echo "Distribute the universal VPN client configuration."
    echo ""
    echo "Options:"
    echo "  -c, --copy PATH    Copy to specific path"
    echo "  -u, --user USER    Copy to user's home directory"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $SCRIPT_NAME                    # Show default locations"
    echo "  $SCRIPT_NAME --copy /tmp/client.ovpn"
    echo "  $SCRIPT_NAME --user john"
}

if [ "$#" -eq 0 ]; then
    echo "Universal VPN client is stored at: /etc/openvpn/clients/universal-client.ovpn"
    echo ""
    echo "To copy to specific locations:"
    echo "  distribute-vpn-client --copy /path/to/client.ovpn"
    echo "  distribute-vpn-client --user username"
    exit 0
fi

case "$1" in
    -c|--copy)
        if [ -z "$2" ]; then
            echo "Error: Please specify destination path"
            exit 1
        fi
        cp /etc/openvpn/clients/universal-client.ovpn "$2"
        echo "Client configuration copied to: $2"
        ;;
    -u|--user)
        if [ -z "$2" ]; then
            echo "Error: Please specify username"
            exit 1
        fi
        USER_HOME=$(eval echo ~$2)
        if [ ! -d "$USER_HOME" ]; then
            echo "Error: User home directory not found: $USER_HOME"
            exit 1
        fi
        cp /etc/openvpn/clients/universal-client.ovpn "$USER_HOME/vpn-client.ovpn"
        chown $2:$2 "$USER_HOME/vpn-client.ovpn"
        echo "Client configuration copied to: $USER_HOME/vpn-client.ovpn"
        ;;
    -h|--help)
        usage
        ;;
    *)
        echo "Unknown option: $1"
        usage
        exit 1
        ;;
esac
EOF

    chmod 755 /usr/local/bin/distribute-vpn-client

    # --- Enable and start services ---
    systemctl enable openvpn-server@server
    systemctl restart openvpn-server@server

    # --- Display summary ---
    echo ""
    echo "================================================"
    echo "✅ OpenVPN with RADIUS Authentication Complete!"
    echo "================================================"
    echo ""
    echo "📋 Server Configuration:"
    echo "   Public IP: $Public_IP"
    echo "   Port: $Port"
    echo "   Protocol: $Protocol"
    echo "   VPN Subnet: $Server_Subnet"
    echo "   RADIUS Server: $RADIUS_Server:$RADIUS_Auth_Port"
    echo "   RADIUS Secret: [Using shared secret from .env]"
    echo ""
    echo "👥 Client Management:"
    echo "   Universal config: /etc/openvpn/clients/universal-client.ovpn"
    echo "   Distribute command: distribute-vpn-client [options]"
    echo ""
    echo "⚡ RADIUS Integration:"
    echo "   • All users share the same .ovpn file"
    echo "   • RADIUS server handles authentication"
    echo "   • RADIUS assigns IPs via Framed-IP-Address attribute"
    echo "   • RADIUS assigns routes via Framed-Route attribute"
    echo "   • NO CCD files needed - RADIUS plugin handles everything"
    echo ""
    echo "🔧 Test Connection:"
    echo "   sudo systemctl status openvpn-server@server"
    echo "   tail -f /var/log/openvpn/openvpn.log"
    echo ""
    echo "================================================"
}

# --- Main function ---
main() {
    echo "================================================"
    echo "🚀 OpenVPN + Custom RADIUS Plugin Installation"
    echo "================================================"
    echo ""
    
    check_root
    load_env
    detect_os
    install_dependencies
    configure_openvpn
    
    echo ""
    echo "✅ OpenVPN installation completed successfully!"
    echo ""
}

main
