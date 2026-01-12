import re
from app.utils.network import NetworkManager

class Validators:
    """Custom validators for form inputs"""
    
    @staticmethod
    def validate_username(username):
        """
        Validate username format
        Alphanumeric, dot, underscore, hyphen, 3-64 characters
        """
        if not username or len(username) < 3 or len(username) > 64:
            return False, "Username must be 3-64 characters"
        
        if not re.match(r'^[a-zA-Z0-9._-]+$', username):
            return False, "Username can only contain letters, numbers, dots, underscores, and hyphens"
        
        return True, ""
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return True, ""  # Email is optional
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        return True, ""
    
    @staticmethod
    def validate_hostname(hostname):
        """
        Validate DNS hostname
        RFC 1123 compliant
        """
        if not hostname or len(hostname) > 253:
            return False, "Hostname must be 1-253 characters"
        
        # Remove trailing dot if present
        if hostname.endswith('.'):
            hostname = hostname[:-1]
        
        # Check each label
        labels = hostname.split('.')
        for label in labels:
            if not label or len(label) > 63:
                return False, "Each label must be 1-63 characters"
            
            if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', label):
                return False, "Invalid hostname format"
        
        return True, ""
    
    @staticmethod
    def validate_ip_address(ip):
        """Validate IPv4 address"""
        if not NetworkManager.is_valid_ip(ip):
            return False, "Invalid IP address format"
        return True, ""
    
    @staticmethod
    def validate_cidr(cidr):
        """Validate CIDR notation"""
        if not NetworkManager.is_valid_cidr(cidr):
            return False, "Invalid CIDR format (e.g., 192.168.1.0/24)"
        return True, ""
    
    @staticmethod
    def validate_port(port):
        """Validate port number or range"""
        if not port:
            return True, ""  # Empty is valid (means any)
        
        if not NetworkManager.is_valid_port(port):
            return False, "Invalid port format (1-65535 or range like 80-443)"
        
        return True, ""
    
    @staticmethod
    def validate_protocol(protocol):
        """Validate protocol"""
        valid_protocols = ['tcp', 'udp', 'icmp', 'any']
        if protocol not in valid_protocols:
            return False, f"Protocol must be one of: {', '.join(valid_protocols)}"
        return True, ""
    
    @staticmethod
    def validate_password(password):
        """
        Validate password strength
        Minimum 8 characters, at least one uppercase, one lowercase, one number
        """
        if not password or len(password) < 8:
            return False, "Password must be at least 8 characters"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one number"
        
        return True, ""
    
    @staticmethod
    def validate_role(role):
        """Validate user role"""
        valid_roles = ['Administrator', 'Operator', 'Viewer', 'Auditor']
        if role not in valid_roles:
            return False, f"Role must be one of: {', '.join(valid_roles)}"
        return True, ""
