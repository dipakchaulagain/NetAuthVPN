import ipaddress
from app.models import VPNUser
from flask import current_app

class NetworkManager:
    """Network utilities for IP allocation and validation"""
    
    @staticmethod
    def parse_subnet(subnet_str):
        """
        Parse subnet string (e.g., '10.8.0.0/24')
        Returns ipaddress.IPv4Network object
        """
        try:
            return ipaddress.IPv4Network(subnet_str, strict=False)
        except ValueError as e:
            current_app.logger.error(f"Invalid subnet: {subnet_str} - {e}")
            return None
    
    @staticmethod
    def get_allocated_ips():
        """Get all currently allocated IPs from database (including inactive users with IPs)"""
        users = VPNUser.query.filter(VPNUser.ip_address.isnot(None)).all()
        return {user.ip_address for user in users}
    
    @staticmethod
    def get_next_available_ip(subnet_str=None):
        """
        Find the next available IP in the VPN subnet
        Excludes network address, broadcast, and gateway (.0, .1, .255)
        """
        if subnet_str is None:
            subnet_str = current_app.config['VPN_SUBNET']
        
        subnet = NetworkManager.parse_subnet(subnet_str)
        if not subnet:
            return None
        
        # Get allocated IPs
        allocated_ips = NetworkManager.get_allocated_ips()
        
        # Reserved IPs (network, gateway, broadcast)
        reserved = {
            str(subnet.network_address),  # .0
            str(subnet.network_address + 1),  # .1 (typically VPN server)
            str(subnet.broadcast_address),  # .255
        }
        
        # Find first available IP
        for ip in subnet.hosts():
            ip_str = str(ip)
            if ip_str not in allocated_ips and ip_str not in reserved:
                return ip_str
        
        current_app.logger.error(f"No available IPs in subnet {subnet_str}")
        return None
    
    @staticmethod
    def is_valid_ip(ip_str):
        """Validate IP address format"""
        try:
            ipaddress.IPv4Address(ip_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_cidr(cidr_str):
        """Validate CIDR notation (e.g., 192.168.1.0/24)"""
        try:
            ipaddress.IPv4Network(cidr_str, strict=False)
            return True
        except ValueError:
            return False
    
    
    @staticmethod
    def is_valid_route(route):
        """
        Validate route in CIDR notation
        Ensures proper network addresses (e.g., 192.168.21.0/24 not 192.168.21.10/24)
        
        Args:
            route: String in CIDR format (e.g., '192.168.1.0/24')
        
        Returns:
            Boolean indicating if route is valid
        """
        try:
            network = ipaddress.IPv4Network(route, strict=False)
            
            # For /32 (single host), any IP is valid
            if network.prefixlen == 32:
                return True
            
            # For other subnet masks, ensure it's the network address
            # strict=True will raise ValueError if it's not the network address
            try:
                ipaddress.IPv4Network(route, strict=True)
                return True
            except ValueError:
                # It's a host IP with a subnet mask (e.g., 192.168.21.10/24)
                return False
                
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
            return False
    
    
    @staticmethod
    def is_ip_in_subnet(ip_str, subnet_str):
        """Check if IP is within subnet"""
        try:
            ip = ipaddress.IPv4Address(ip_str)
            subnet = ipaddress.IPv4Network(subnet_str, strict=False)
            return ip in subnet
        except ValueError:
            return False
    
    @staticmethod
    def format_route_for_radius(route_str):
        """
        Format route for RADIUS Framed-Route attribute
        RADIUS expects: "destination/mask [gateway] [metric]"
        For OpenVPN, we typically don't specify gateway/metric
        """
        # Validate route
        if not NetworkManager.is_valid_route(route_str):
            return None
        
        # RADIUS format is typically just the CIDR notation
        return route_str
    
    @staticmethod
    def is_valid_port(port_str):
        """Validate port number or range"""
        if not port_str:
            return True  # Empty port is valid (means any)
        
        # Single port
        if port_str.isdigit():
            port = int(port_str)
            return 1 <= port <= 65535
        
        # Port range (e.g., "80-443")
        if '-' in port_str:
            try:
                start, end = port_str.split('-')
                start_port = int(start)
                end_port = int(end)
                return (1 <= start_port <= 65535 and 
                       1 <= end_port <= 65535 and 
                       start_port <= end_port)
            except:
                return False
        
        return False
    
    @staticmethod
    def get_subnet_info(subnet_str):
        """Get detailed subnet information"""
        subnet = NetworkManager.parse_subnet(subnet_str)
        if not subnet:
            return None
        
        return {
            'network': str(subnet.network_address),
            'netmask': str(subnet.netmask),
            'broadcast': str(subnet.broadcast_address),
            'prefix': subnet.prefixlen,
            'total_hosts': subnet.num_addresses - 2,  # Exclude network and broadcast
            'usable_hosts': subnet.num_addresses - 3,  # Also exclude gateway
            'first_usable': str(subnet.network_address + 2),
            'last_usable': str(subnet.broadcast_address - 1),
        }
