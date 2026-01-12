import subprocess
import re
from flask import current_app

class IPTablesManager:
    """Manage iptables rules for VPN user security"""
    
    # Chain prefix for VPN user rules
    CHAIN_PREFIX = "VPN_USER_"
    
    @staticmethod
    def _run_command(cmd, check=True):
        """Execute system command safely"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if check and result.returncode != 0:
                current_app.logger.error(f"Command failed: {cmd}")
                current_app.logger.error(f"Error: {result.stderr}")
                return None
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            current_app.logger.error(f"Command timeout: {cmd}")
            return None
        except Exception as e:
            current_app.logger.error(f"Command error: {e}")
            return None
    
    @staticmethod
    def create_user_chain(username):
        """Create a dedicated chain for user rules"""
        chain_name = f"{IPTablesManager.CHAIN_PREFIX}{username}"
        
        # Check if chain exists
        check_cmd = f"sudo iptables -L {chain_name} -n 2>/dev/null"
        if IPTablesManager._run_command(check_cmd, check=False):
            # Chain exists, flush it
            IPTablesManager._run_command(f"sudo iptables -F {chain_name}")
        else:
            # Create new chain
            IPTablesManager._run_command(f"sudo iptables -N {chain_name}")
        
        return chain_name
    
    @staticmethod
    def delete_user_chain(username):
        """Delete user's dedicated chain"""
        chain_name = f"{IPTablesManager.CHAIN_PREFIX}{username}"
        
        # Remove references to this chain
        IPTablesManager._run_command(f"sudo iptables -D FORWARD -j {chain_name} 2>/dev/null", check=False)
        
        # Flush and delete chain
        IPTablesManager._run_command(f"sudo iptables -F {chain_name} 2>/dev/null", check=False)
        IPTablesManager._run_command(f"sudo iptables -X {chain_name} 2>/dev/null", check=False)
    
    @staticmethod
    def apply_user_rules(vpn_user, security_rules):
        """
        Apply security rules for a VPN user
        vpn_user: VPNUser model instance
        security_rules: list of SecurityRule model instances
        """
        username = vpn_user.username
        user_ip = vpn_user.ip_address
        
        # Create/clear user chain
        chain_name = IPTablesManager.create_user_chain(username)
        
        # Add rules to chain
        for rule in security_rules:
            if not rule.active:
                continue
            
            # Build iptables rule
            rule_cmd = f"sudo iptables -A {chain_name}"
            
            # Source (VPN user's IP)
            rule_cmd += f" -s {user_ip}"
            
            # Destination (route)
            rule_cmd += f" -d {rule.route}"
            
            # Protocol
            if rule.protocol != 'any':
                rule_cmd += f" -p {rule.protocol}"
                
                # Port (only for tcp/udp)
                if rule.port and rule.protocol in ['tcp', 'udp']:
                    if '-' in rule.port:
                        # Port range
                        rule_cmd += f" --dport {rule.port}"
                    else:
                        # Single port
                        rule_cmd += f" --dport {rule.port}"
            
            # Action
            rule_cmd += f" -j {rule.action}"
            
            # Execute rule
            result = IPTablesManager._run_command(rule_cmd)
            if result is not None:
                current_app.logger.info(f"Applied rule for {username}: {rule_cmd}")
        
        # Insert chain into FORWARD chain (if not already there)
        # Match packets from user's IP
        insert_cmd = f"sudo iptables -C FORWARD -s {user_ip} -j {chain_name} 2>/dev/null"
        if not IPTablesManager._run_command(insert_cmd, check=False):
            # Not present, add it
            IPTablesManager._run_command(f"sudo iptables -I FORWARD -s {user_ip} -j {chain_name}")
        
        return True
    
    @staticmethod
    def remove_user_rules(username):
        """Remove all iptables rules for a user"""
        IPTablesManager.delete_user_chain(username)
        current_app.logger.info(f"Removed all iptables rules for {username}")
    
    @staticmethod
    def save_rules():
        """Save current iptables rules persistently"""
        # Save to file
        IPTablesManager._run_command("sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null")
        
        # Use netfilter-persistent if available
        IPTablesManager._run_command("sudo netfilter-persistent save 2>/dev/null", check=False)
        
        current_app.logger.info("Saved iptables rules")
        return True
    
    @staticmethod
    def list_chains():
        """List all VPN user chains"""
        output = IPTablesManager._run_command("sudo iptables -L -n | grep 'Chain'")
        if not output:
            return []
        
        chains = []
        for line in output.split('\n'):
            if IPTablesManager.CHAIN_PREFIX in line:
                match = re.search(r'Chain (VPN_USER_\w+)', line)
                if match:
                    chains.append(match.group(1))
        
        return chains
    
    @staticmethod
    def get_rule_count():
        """Get total number of iptables rules"""
        output = IPTablesManager._run_command("sudo iptables -L -n | wc -l")
        if output:
            return int(output.strip())
        return 0
