import subprocess
import re
from flask import current_app

class SystemManager:
    """Manage system services and operations"""
    
    # Allowed services for restart (whitelist for security)
    ALLOWED_SERVICES = {
        'openvpn-server@server': {'admin_only': True},
        'freeradius': {'admin_only': True},
        'dnsmasq': {'admin_only': False},
        'mysql': {'admin_only': True},
    }
    
    @staticmethod
    def _run_command(cmd, timeout=30):
        """Execute system command safely"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timeout',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    @staticmethod
    def get_service_status(service_name):
        """
        Get detailed status of a systemd service
        Returns dict with status information
        """
        if service_name not in SystemManager.ALLOWED_SERVICES:
            return None
        
        cmd = f"sudo systemctl status {service_name} --no-pager"
        result = SystemManager._run_command(cmd)
        
        status = {
            'name': service_name,
            'active': False,
            'running': False,
            'enabled': False,
            'uptime': None,
            'memory': None,
            'cpu': None,
            'pid': None,
            'description': ''
        }
        
        if not result['success']:
            return status
        
        output = result['stdout']
        
        # Parse status
        if 'Active: active (running)' in output:
            status['active'] = True
            status['running'] = True
        elif 'Active: active' in output:
            status['active'] = True
        
        # Check if enabled
        enabled_cmd = f"sudo systemctl is-enabled {service_name} 2>/dev/null"
        enabled_result = SystemManager._run_command(enabled_cmd)
        if enabled_result['stdout'].strip() == 'enabled':
            status['enabled'] = True
        
        # Extract uptime (approximate from status line)
        uptime_match = re.search(r'Active:.*since\s+(.+?);\s+(.+?)\s+ago', output)
        if uptime_match:
            status['uptime'] = uptime_match.group(2)
        
        # Extract PID
        pid_match = re.search(r'Main PID:\s+(\d+)', output)
        if pid_match:
            status['pid'] = int(pid_match.group(1))
        
        # Extract memory (if available)
        memory_match = re.search(r'Memory:\s+([0-9.]+\w+)', output)
        if memory_match:
            status['memory'] = memory_match.group(1)
        
        # Extract description
        desc_match = re.search(r'Loaded:.*\((.*?);', output)
        if desc_match:
            status['description'] = desc_match.group(1)
        
        return status
    
    @staticmethod
    def restart_service(service_name):
        """
        Restart a systemd service
        Returns tuple (success, message)
        """
        if service_name not in SystemManager.ALLOWED_SERVICES:
            return False, f"Service {service_name} is not allowed to be restarted"
        
        cmd = f"sudo systemctl restart {service_name}"
        result = SystemManager._run_command(cmd)
        
        if result['success']:
            current_app.logger.info(f"Successfully restarted service: {service_name}")
            return True, f"Service {service_name} restarted successfully"
        else:
            current_app.logger.error(f"Failed to restart {service_name}: {result['stderr']}")
            return False, f"Failed to restart {service_name}: {result['stderr']}"
    
    @staticmethod
    def reload_iptables():
        """Reload iptables (apply saved rules)"""
        # This is safe even for operators
        cmd = "sudo iptables-restore /etc/iptables/rules.v4"
        result = SystemManager._run_command(cmd)
        
        if result['success']:
            return True, "iptables rules reloaded successfully"
        else:
            return False, f"Failed to reload iptables: {result['stderr']}"
    
    @staticmethod
    def get_service_logs(service_name, lines=50):
        """Get recent logs for a service"""
        if service_name not in SystemManager.ALLOWED_SERVICES:
            return None
        
        cmd = f"sudo journalctl -u {service_name} -n {lines} --no-pager"
        result = SystemManager._run_command(cmd)
        
        if result['success']:
            return result['stdout']
        return None
    
    @staticmethod
    def update_hosts_file(dns_records):
        """
        Update /etc/hosts with DNS records
        dns_records: list of DNSRecord model instances
        """
        try:
            # Read current /etc/hosts
            with open('/etc/hosts', 'r') as f:
                lines = f.readlines()
            
            # Remove old VPN WebUI section
            new_lines = []
            skip = False
            for line in lines:
                if '# BEGIN VPN WebUI DNS Records' in line:
                    skip = True
                elif '# END VPN WebUI DNS Records' in line:
                    skip = False
                    continue
                elif not skip:
                    new_lines.append(line)
            
            # Add new VPN WebUI section
            new_lines.append('\n# BEGIN VPN WebUI DNS Records\n')
            for record in dns_records:
                if record.active:
                    new_lines.append(f"{record.ip_address}\t{record.hostname}\n")
            new_lines.append('# END VPN WebUI DNS Records\n')
            
            # Backup original
            SystemManager._run_command('sudo cp /etc/hosts /etc/hosts.backup')
            
            # Write new file to temp location
            temp_file = '/tmp/hosts.new'
            with open(temp_file, 'w') as f:
                f.writelines(new_lines)
            
            # Move to /etc/hosts with sudo
            result = SystemManager._run_command(f'sudo mv {temp_file} /etc/hosts')
            
            if result['success']:
                current_app.logger.info("Updated /etc/hosts with DNS records")
                return True, "DNS records updated successfully"
            else:
                return False, "Failed to update /etc/hosts"
            
        except Exception as e:
            current_app.logger.error(f"Error updating hosts file: {e}")
            return False, str(e)
    
    @staticmethod
    def can_restart_service(service_name, user_role):
        """
        Check if user role can restart a specific service
        """
        if service_name not in SystemManager.ALLOWED_SERVICES:
            return False
        
        service_config = SystemManager.ALLOWED_SERVICES[service_name]
        
        if user_role == 'Administrator':
            return True
        elif user_role == 'Operator':
            return not service_config['admin_only']
        else:
            return False
    
    @staticmethod
    def get_all_services_status():
        """Get status of all monitored services"""
        statuses = {}
        for service_name in SystemManager.ALLOWED_SERVICES.keys():
            statuses[service_name] = SystemManager.get_service_status(service_name)
        return statuses
