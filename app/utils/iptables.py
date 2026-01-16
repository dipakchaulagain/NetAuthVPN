import subprocess
import re
from flask import current_app

class IPTablesManager:
    """Manage iptables rules for VPN user security"""
    
    # Chain prefix for VPN user rules
    CHAIN_PREFIX = "VPN_USER_"
    
    @staticmethod
    def _run_command(cmd, check=True):
        """Execute system command safely. Returns (success, stdout)"""
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
    def _run_command_with_status(cmd):
        """Execute system command and return (success, stdout)"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return (result.returncode == 0, result.stdout)
        except Exception as e:
            current_app.logger.error(f"Command error: {e}")
            return (False, "")
    
    @staticmethod
    def _remove_all_forward_references(chain_name, user_ip=None):
        """Remove ALL FORWARD chain references to a user's chain"""
        removed_count = 0
        
        # Method 1: Try direct removal by chain name (up to 20 times for safety)
        for _ in range(20):
            if user_ip:
                # Try with source IP
                success, _ = IPTablesManager._run_command_with_status(
                    f"sudo iptables -D FORWARD -s {user_ip} -j {chain_name}"
                )
            else:
                # Try without source IP
                success, _ = IPTablesManager._run_command_with_status(
                    f"sudo iptables -D FORWARD -j {chain_name}"
                )
            
            if success:
                removed_count += 1
                current_app.logger.info(f"Removed FORWARD reference to {chain_name}")
            else:
                # No more rules to remove
                break
        
        # Method 2: Fallback - search by chain name and remove by line number
        for _ in range(20):
            # Get line numbers of any remaining references
            output = IPTablesManager._run_command(
                f"sudo iptables -L FORWARD -n --line-numbers 2>/dev/null | grep '{chain_name}'",
                check=False
            )
            
            if output and output.strip():
                lines = output.strip().split('\n')
                if lines and lines[0]:
                    # Parse line number from first match (e.g., "1    10.8.0.6     0.0.0.0/0    VPN_USER_xxx")
                    parts = lines[0].split()
                    if parts and parts[0].isdigit():
                        line_num = parts[0]
                        success, _ = IPTablesManager._run_command_with_status(
                            f"sudo iptables -D FORWARD {line_num}"
                        )
                        if success:
                            removed_count += 1
                            continue
            break
        
        current_app.logger.info(f"Removed {removed_count} FORWARD references for {chain_name}")
        return removed_count
    
    @staticmethod
    def create_user_chain(username):
        """Create a dedicated chain for user rules"""
        chain_name = f"{IPTablesManager.CHAIN_PREFIX}{username}"
        
        # Check if chain exists
        success, _ = IPTablesManager._run_command_with_status(
            f"sudo iptables -L {chain_name} -n 2>/dev/null"
        )
        
        if success:
            # Chain exists, flush it
            IPTablesManager._run_command(f"sudo iptables -F {chain_name}")
        else:
            # Create new chain
            IPTablesManager._run_command(f"sudo iptables -N {chain_name}")
        
        return chain_name
    
    @staticmethod
    def delete_user_chain(username):
        """Delete user's dedicated chain and remove ALL references from FORWARD"""
        chain_name = f"{IPTablesManager.CHAIN_PREFIX}{username}"
        
        # Remove ALL references to this chain from FORWARD
        IPTablesManager._remove_all_forward_references(chain_name)
        
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
        
        if not user_ip:
            current_app.logger.error(f"Cannot apply rules for {username}: no IP address assigned")
            return False
        
        chain_name = f"{IPTablesManager.CHAIN_PREFIX}{username}"
        
        # FIRST: Remove ALL existing FORWARD references to prevent duplicates
        # This must happen BEFORE we create/flush the chain
        IPTablesManager._remove_all_forward_references(chain_name, user_ip)
        
        # Create/clear user chain (this flushes existing rules in the chain)
        chain_name = IPTablesManager.create_user_chain(username)
        
        # Add rules to chain
        enabled_rules = [r for r in security_rules if r.active and r.enabled]
        for rule in enabled_rules:
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
                    rule_cmd += f" --dport {rule.port}"
            
            # Action
            rule_cmd += f" -j {rule.action}"
            
            # Execute rule
            result = IPTablesManager._run_command(rule_cmd)
            if result is not None:
                current_app.logger.info(f"Applied rule for {username}: {rule_cmd}")
        
        # Insert EXACTLY ONE reference to user chain in FORWARD
        IPTablesManager._run_command(f"sudo iptables -I FORWARD -s {user_ip} -j {chain_name}")
        current_app.logger.info(f"Added single FORWARD rule for {username}: {user_ip} -> {chain_name}")
        
        return True
    
    @staticmethod
    def is_rules_applied(username, user_ip):
        """
        Check if user's security rules are currently applied in iptables
        Returns True if the user's chain exists and has a FORWARD reference
        """
        if not user_ip:
            return False
        
        chain_name = f"{IPTablesManager.CHAIN_PREFIX}{username}"
        
        # Check if chain exists
        success, _ = IPTablesManager._run_command_with_status(
            f"sudo iptables -L {chain_name} -n 2>/dev/null"
        )
        
        if not success:
            return False
        
        # Check if FORWARD has a reference to the chain
        output = IPTablesManager._run_command(
            f"sudo iptables -L FORWARD -n 2>/dev/null | grep '{chain_name}'",
            check=False
        )
        
        return bool(output and output.strip())
    
    @staticmethod
    def remove_user_rules(username):
        """Remove all iptables rules for a user"""
        IPTablesManager.delete_user_chain(username)
        current_app.logger.info(f"Removed all iptables rules for {username}")
    
    @staticmethod
    def save_rules():
        """Save current iptables rules persistently"""
        # IMPORTANT: Remove overly permissive rule that bypasses per-user security rules
        # The rule "-A FORWARD -i tun0 -o <interface> -j ACCEPT" allows all VPN traffic
        # which makes per-user firewall rules ineffective
        for _ in range(5):  # Try up to 5 times to remove all instances
            success, _ = IPTablesManager._run_command_with_status(
                "sudo iptables -D FORWARD -i tun0 -j ACCEPT 2>/dev/null"
            )
            if not success:
                break
        
        # Also try to remove interface-specific variants
        output = IPTablesManager._run_command(
            "ip route | grep default | awk '{print $5}' | head -1",
            check=False
        )
        if output and output.strip():
            net_iface = output.strip()
            for _ in range(5):
                success, _ = IPTablesManager._run_command_with_status(
                    f"sudo iptables -D FORWARD -i tun0 -o {net_iface} -j ACCEPT 2>/dev/null"
                )
                if not success:
                    break
        
        # Now save to file
        IPTablesManager._run_command("sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null")
        
        # Use netfilter-persistent if available
        IPTablesManager._run_command("sudo netfilter-persistent save 2>/dev/null", check=False)
        
        current_app.logger.info("Saved iptables rules (removed overly permissive tun0 rules)")
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
                match = re.search(r'Chain (VPN_USER_[\w.]+)', line)
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

