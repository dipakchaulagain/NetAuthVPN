#!/bin/bash
# Main Setup Script for OpenVPN + FreeRADIUS Integration
# Description: Orchestrates the complete setup with proper ordering and firewall configuration

set -e

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Configuration ---
ENV_FILE=".env"
OPENVPN_SCRIPT="openvpn-setup.sh"
RADIUS_SCRIPT="radius-setup.sh"

# --- Functions ---
print_header() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

print_step() {
    echo -e "\n${YELLOW}[+] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_error "This script must be run as root!"
        exit 1
    fi
}

validate_env() {
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Environment file $ENV_FILE not found!"
        echo "Please create a .env file with the required variables."
        echo "See the example format below:"
        echo ""
        echo "#############################################"
        echo "## Combined .env for OpenVPN + FreeRADIUS Setup"
        echo "#############################################"
        echo ""
        echo "# --- OpenVPN Configuration ---"
        echo "IP=192.168.1.100                    # VPN Server Internal IP (also used as DNS for clients)"
        echo "Public_IP=103.103.45.25            # VPN Server Public IP"
        echo "Port=1194"
        echo "Protocol=udp"
        echo "DNS_Server_1=8.8.8.8               # Fallback DNS"
        echo ""
        echo "# --- DNS Configuration ---"
        echo "# UPSTREAM_DNS: DNS servers that DNSmasq will use for upstream queries"
        echo "# Clients use $IP as DNS, which forwards to these upstream servers"
        echo "UPSTREAM_DNS=8.8.8.8 8.8.4.4"
        echo ""
        echo "# --- Shared RADIUS Configuration ---"
        echo "RADIUS_Secret=MySecretKey123"
        echo "RADIUS_Server=localhost"
        echo ""
        echo "# --- FreeRADIUS + MySQL Configuration ---"
        echo "MYSQL_ROOT_PASSWORD=your_root_password"
        echo "RADIUS_DB_PASSWORD=your_radius_db_password"
        echo ""
        echo "# --- LDAP Configuration ---"
        echo "LDAP_SERVER=ldap://ad_or_ldapserver"
        echo "LDAP_IDENTITY=service.user@dc.domain"
        echo "LDAP_PASSWORD=StrongPassword"
        echo "LDAP_BASE_DN=DC=dc,DC=domain"
        echo ""
        echo "# --- Optional Configuration ---"
        echo "# REMOTE_ROOT_IP=192.168.12.9"
        echo "# BIND_ADDRESS=0.0.0.0"
        exit 1
    fi
    
    print_step "Loading and validating environment variables"
    
    # Load .env file
    set -a
    source "$ENV_FILE"
    set +a
    
    # Check required variables
    local required_vars=(
        "MYSQL_ROOT_PASSWORD"
        "RADIUS_DB_PASSWORD"
        "LDAP_SERVER"
        "LDAP_IDENTITY"
        "LDAP_PASSWORD"
        "LDAP_BASE_DN"
        "IP"
        "Public_IP"
        "Port"
        "Protocol"
        "DNS_Server_1"
        "RADIUS_Secret"
        "UPSTREAM_DNS"
    )
    
    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_error "Missing required variables in $ENV_FILE:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please add the missing variables to your .env file and try again."
        exit 1
    fi
    
    # Set defaults for optional variables
    RADIUS_Server=${RADIUS_Server:-"localhost"}
    BIND_ADDRESS=${BIND_ADDRESS:-"0.0.0.0"}
    REMOTE_ROOT_IP=${REMOTE_ROOT_IP:-""}
    LDAP_USER_FILTER=${LDAP_USER_FILTER:-"(&(sAMAccountName=%{%{Stripped-User-Name}:-%{User-Name}}))"}
    OPENVPN_AUTH=${OPENVPN_AUTH:-"yes"}
    RADIUS_Auth_Port=${RADIUS_Auth_Port:-1812}
    RADIUS_Acct_Port=${RADIUS_Acct_Port:-1813}
    Server_Subnet=${Server_Subnet:-"10.8.0.0/24"}
    Cert_Expiration_Days=${Cert_Expiration_Days:-365}
    
    # Validate IP format
    if ! echo "$IP" | grep -qE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
        print_error "Invalid IP address format: $IP"
        exit 1
    fi
    
    # Validate Public IP format
    if ! echo "$Public_IP" | grep -qE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
        print_error "Invalid Public IP address format: $Public_IP"
        exit 1
    fi
    
    # Validate port
    if ! [[ "$Port" =~ ^[0-9]+$ ]] || [ "$Port" -lt 1 ] || [ "$Port" -gt 65535 ]; then
        print_error "Port must be a number between 1 and 65535"
        exit 1
    fi
    
    print_success "Environment validation passed"
}

check_scripts() {
    print_step "Checking required scripts"
    
    if [ ! -f "$RADIUS_SCRIPT" ]; then
        print_error "$RADIUS_SCRIPT not found!"
        exit 1
    fi
    
    if [ ! -f "$OPENVPN_SCRIPT" ]; then
        print_error "$OPENVPN_SCRIPT not found!"
        exit 1
    fi
    
    # Make scripts executable
    chmod +x "$RADIUS_SCRIPT" "$OPENVPN_SCRIPT"
    
    print_success "All required scripts found and made executable"
}

setup_radius() {
    print_step "Setting up FreeRADIUS with MySQL and LDAP"
    
    echo "Running: $RADIUS_SCRIPT"
    if bash "$RADIUS_SCRIPT"; then
        print_success "FreeRADIUS setup completed"
    else
        print_error "FreeRADIUS setup failed with exit code $?"
        exit 1
    fi
}

setup_openvpn() {
    print_step "Setting up OpenVPN with RADIUS authentication"
    
    # We need to patch the OpenVPN script to use $IP as DNS for clients
    print_step "Configuring OpenVPN to use $IP as DNS server for clients"
    
    echo "Running: $OPENVPN_SCRIPT"
    if bash "$OPENVPN_SCRIPT"; then
        print_success "OpenVPN setup completed"
        
        # Verify OpenVPN is configured to push $IP as DNS
        if grep -q "push \"dhcp-option DNS $IP\"" /etc/openvpn/server/server.conf; then
            print_success "OpenVPN configured to push $IP as DNS to clients"
        else
            print_error "OpenVPN not configured to push $IP as DNS to clients"
            echo "Manually updating OpenVPN configuration..."
            # Add the DNS push to server.conf
            if ! grep -q "push \"dhcp-option DNS $IP\"" /etc/openvpn/server/server.conf; then
                sed -i "/push \"redirect-gateway def1 bypass-dhcp\"/a push \"dhcp-option DNS $IP\"" /etc/openvpn/server/server.conf
                systemctl restart openvpn-server@server
                print_success "Updated OpenVPN to push $IP as DNS"
            fi
        fi
    else
        print_error "OpenVPN setup failed with exit code $?"
        exit 1
    fi
}

setup_dnsmasq() {
    print_step "Setting up DNSmasq for DNS forwarding"
    
    echo "✅ VPN Server IP (Client DNS): $IP"
    echo "✅ Upstream DNS servers for DNSmasq: $UPSTREAM_DNS"
    
    echo "🔧 Updating system..."
    apt update -y
    
    echo "📦 Installing dnsmasq..."
    apt install -y dnsmasq
    
    echo "🛑 Stopping systemd-resolved (port 53 conflict)..."
    systemctl stop systemd-resolved
    systemctl disable systemd-resolved
    
    echo "🔗 Fixing /etc/resolv.conf..."
    rm -f /etc/resolv.conf
    echo "nameserver 127.0.0.1" > /etc/resolv.conf
    
    echo "📝 Configuring dnsmasq..."
    DNSMASQ_CONF="/etc/dnsmasq.conf"
    
    # Backup original config
    cp "$DNSMASQ_CONF" "${DNSMASQ_CONF}.backup" 2>/dev/null || true
    
    cat > "$DNSMASQ_CONF" <<EOF
# Listen on all interfaces
port=53
bind-interfaces

# Use /etc/hosts for custom records
addn-hosts=/etc/hosts

# Do not use resolv.conf
no-resolv

# Logging (optional)
log-queries
log-facility=/var/log/dnsmasq.log
EOF

    # Add upstream DNS servers
    for dns in $UPSTREAM_DNS; do
        echo "server=$dns" >> "$DNSMASQ_CONF"
    done
    
    echo "🚀 Starting dnsmasq..."
    systemctl restart dnsmasq
    systemctl enable dnsmasq
    
    # Wait for dnsmasq to start
    sleep 2
    
    if systemctl is-active --quiet dnsmasq; then
        print_success "DNSmasq is running!"
        echo "📌 Listening on all interfaces (clients use $IP as DNS)"
        echo "📌 Upstream DNS: $UPSTREAM_DNS"
        echo "📌 Custom DNS records: /etc/hosts"
        echo "📌 Logs: /var/log/dnsmasq.log"
        
        # Quick test
        echo "🧪 Quick DNS test..."
        if timeout 2 dig google.com @127.0.0.1 +short >/dev/null 2>&1; then
            print_success "DNS is working"
        else
            print_error "DNS test failed (but service is running)"
        fi
    else
        print_error "DNSmasq failed to start"
        systemctl status dnsmasq --no-pager
    fi
}

configure_firewall() {
    print_step "Configuring firewall rules"
    
    # Get network interface
    NET_IFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
    if [ -z "$NET_IFACE" ]; then
        NET_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
    fi
    
    if [ -z "$NET_IFACE" ]; then
        print_error "Cannot determine network interface"
        exit 1
    fi
    
    # Get subnet IP from Server_Subnet
    SUBNET_IP=$(echo "$Server_Subnet" | cut -d'/' -f1)
    
    print_step "Network interface: $NET_IFACE"
    print_step "VPN subnet IP: $SUBNET_IP"
    print_step "VPN Server IP (DNS for clients): $IP"
    
    # Flush existing rules
    iptables -F
    iptables -t nat -F
    iptables -X
    iptables -t nat -X

    # Default policies
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT ACCEPT

    # Allow localhost
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

    # Allow SSH
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT

    # Allow OpenVPN
    iptables -A INPUT -p $Protocol --dport $Port -j ACCEPT
    
    # Allow DNS (port 53) on ALL interfaces (clients will connect to $IP for DNS)
    iptables -A INPUT -p udp --dport 53 -j ACCEPT
    iptables -A INPUT -p tcp --dport 53 -j ACCEPT
    
    # Allow DNS from VPN subnet (if clients use tunnel IP for DNS)
    iptables -A INPUT -s ${SUBNET_IP}/24 -p udp --dport 53 -j ACCEPT
    iptables -A INPUT -s ${SUBNET_IP}/24 -p tcp --dport 53 -j ACCEPT

    # Allow RADIUS communication (local and remote)
    if [ "$RADIUS_Server" = "localhost" ] || [ "$RADIUS_Server" = "127.0.0.1" ]; then
        # Allow local RADIUS traffic
        iptables -A INPUT -p udp --dport $RADIUS_Auth_Port -s 127.0.0.1 -j ACCEPT
        iptables -A INPUT -p udp --dport $RADIUS_Acct_Port -s 127.0.0.1 -j ACCEPT
    else
        # Allow RADIUS from specific server
        iptables -A INPUT -p udp --dport $RADIUS_Auth_Port -s $RADIUS_Server -j ACCEPT
        iptables -A INPUT -p udp --dport $RADIUS_Acct_Port -s $RADIUS_Server -j ACCEPT
    fi
    
    # Allow MySQL from remote IP if specified
    if [ -n "$REMOTE_ROOT_IP" ]; then
        iptables -A INPUT -p tcp --dport 3306 -s $REMOTE_ROOT_IP -j ACCEPT
        print_success "MySQL port 3306 opened for $REMOTE_ROOT_IP"
    else
        # Allow MySQL only from localhost
        iptables -A INPUT -p tcp --dport 3306 -s 127.0.0.1 -j ACCEPT
    fi

    # NAT for VPN clients
    iptables -t nat -A POSTROUTING -s ${SUBNET_IP}/24 -o $NET_IFACE -j MASQUERADE

    # Forwarding rules between VPN and internet
    iptables -A FORWARD -i $NET_IFACE -o tun0 -m state --state RELATED,ESTABLISHED -j ACCEPT
    #iptables -A FORWARD -i tun0 -o $NET_IFACE -j ACCEPT
    
    # Allow DNS forwarding from VPN clients
    iptables -A FORWARD -i tun0 -o $NET_IFACE -p udp --dport 53 -j ACCEPT
    iptables -A FORWARD -i tun0 -o $NET_IFACE -p tcp --dport 53 -j ACCEPT

    # Save iptables rules
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4
    
    # Install iptables-persistent if not present
    if ! command -v netfilter-persistent >/dev/null 2>&1; then
        apt-get install -y iptables-persistent >/dev/null 2>&1
    fi
    
    if command -v netfilter-persistent >/dev/null 2>&1; then
        netfilter-persistent save >/dev/null 2>&1
    fi
    
    # Enable IP forwarding if not already done
    echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/20-openvpn.conf
    sysctl -p /etc/sysctl.d/20-openvpn.conf >/dev/null 2>&1
    
    print_success "Firewall rules configured and saved"
}

display_summary() {
    print_header "SETUP COMPLETE"
    
    echo -e "\n${GREEN}✅ Installation Summary:${NC}"
    echo "----------------------------------------"
    echo -e "${YELLOW}OpenVPN Server:${NC}"
    echo "  Server Internal IP: $IP"
    echo "  Server Public IP: $Public_IP"
    echo "  Port: $Port/$Protocol"
    echo "  VPN Subnet: $Server_Subnet"
    echo "  Client Config: /etc/openvpn/clients/universal-client.ovpn"
    echo "  Client DNS: $IP (all clients use this as DNS server)"
    echo ""
    echo -e "${YELLOW}FreeRADIUS Server:${NC}"
    echo "  RADIUS Secret: $RADIUS_Secret"
    echo "  LDAP Server: $LDAP_SERVER"
    echo "  MySQL Database: radius"
    echo "  MySQL Bind Address: $BIND_ADDRESS"
    
    if [ -n "$REMOTE_ROOT_IP" ]; then
        echo "  MySQL Remote Access: Enabled for $REMOTE_ROOT_IP"
    else
        echo "  MySQL Remote Access: Disabled (localhost only)"
    fi
    echo ""
    echo -e "${YELLOW}DNSmasq Configuration:${NC}"
    echo "  Listening on: 127.0.0.1, $IP"
    echo "  Client DNS: $IP (VPN clients use this IP for DNS)"
    echo "  Upstream DNS: $UPSTREAM_DNS"
    echo "  DNS Flow: Client → $IP (DNSmasq) → $UPSTREAM_DNS → Internet"
    echo ""
    echo -e "${YELLOW}Firewall Rules Configured:${NC}"
    echo "  ✅ SSH: 22/tcp"
    echo "  ✅ OpenVPN: $Port/$Protocol"
    echo "  ✅ DNS: 53/udp+tcp (on all interfaces, for $IP)"
    echo "  ✅ RADIUS Auth: $RADIUS_Auth_Port/udp"
    echo "  ✅ RADIUS Acct: $RADIUS_Acct_Port/udp"
    if [ -n "$REMOTE_ROOT_IP" ]; then
        echo "  ✅ MySQL: 3306/tcp (restricted to $REMOTE_ROOT_IP)"
    else
        echo "  ✅ MySQL: 3306/tcp (localhost only)"
    fi
    echo "  ✅ NAT: Enabled for VPN clients"
    echo "  ✅ DNS Forwarding: Enabled from VPN clients"
    echo ""
    echo -e "${YELLOW}Shared Configuration:${NC}"
    echo -e "  ${GREEN}RADIUS Secret: $RADIUS_Secret${NC}"
    echo "  Used in both OpenVPN plugin and FreeRADIUS clients.conf"
    echo ""
    echo -e "${YELLOW}Client Configuration:${NC}"
    echo "  Clients connect to: $Public_IP:$Port"
    echo "  Clients use DNS: $IP (VPN server internal IP)"
    echo "  DNS requests go to $IP, which forwards to: $UPSTREAM_DNS"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Check service status:"
    echo "     systemctl status mysql"
    echo "     systemctl status freeradius"
    echo "     systemctl status openvpn-server@server"
    echo "     systemctl status dnsmasq"
    echo "  2. Distribute client config: distribute-vpn-client [options]"
    echo "  3. Test from VPN client:"
    echo "     nslookup google.com $IP"
    echo "     dig @$IP google.com"
    echo "  4. Check logs:"
    echo "     tail -f /var/log/freeradius/radius.log"
    echo "     tail -f /var/log/openvpn/status.log"
    echo "     tail -f /var/log/dnsmasq.log"
    echo ""
    echo "========================================"
}

# --- Main execution ---
main() {
    print_header "COMPLETE OpenVPN + FreeRADIUS + DNS SETUP"
    echo "This script will:"
    echo "1. Validate environment"
    echo "2. Setup FreeRADIUS with MySQL and LDAP"
    echo "3. Setup OpenVPN with RADIUS authentication"
    echo "4. Setup DNSmasq for DNS forwarding via VPN tunnel"
    echo "5. Configure firewall rules"
    
    check_root
    validate_env
    check_scripts
    
    # Setup in correct order
    setup_radius
    setup_openvpn
    setup_dnsmasq
    configure_firewall
    display_summary
    
    echo -e "\n${GREEN}✅ Complete setup finished at $(date)${NC}"
}

# --- Handle command line arguments ---
case "$1" in
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --env-only     Only validate environment"
        echo "  --firewall     Only configure firewall rules"
        echo "  --radius       Only setup FreeRADIUS"
        echo "  --openvpn      Only setup OpenVPN"
        echo "  --dns          Only setup DNSmasq"
        echo ""
        echo "Without arguments: Complete setup"
        exit 0
        ;;
    --env-only)
        validate_env
        echo "Environment is valid."
        exit 0
        ;;
    --firewall)
        check_root
        validate_env
        configure_firewall
        exit 0
        ;;
    --radius)
        check_root
        validate_env
        check_scripts
        setup_radius
        exit 0
        ;;
    --openvpn)
        check_root
        validate_env
        check_scripts
        setup_openvpn
        exit 0
        ;;
    --dns)
        check_root
        validate_env
        setup_dnsmasq
        exit 0
        ;;
    *)
        main
        ;;
esac
