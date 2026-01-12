import ldap
from flask import current_app
import re

class LDAPClient:
    """LDAP client for user synchronization"""
    
    def __init__(self):
        self.server = current_app.config['LDAP_SERVER']
        self.identity = current_app.config['LDAP_IDENTITY']
        self.password = current_app.config['LDAP_PASSWORD']
        self.base_dn = current_app.config['LDAP_BASE_DN']
        self.user_filter = current_app.config['LDAP_USER_FILTER']
        self.conn = None
    
    def connect(self):
        """Establish LDAP connection"""
        try:
            self.conn = ldap.initialize(self.server)
            self.conn.set_option(ldap.OPT_REFERRALS, 0)
            self.conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
            self.conn.simple_bind_s(self.identity, self.password)
            return True
        except ldap.LDAPError as e:
            current_app.logger.error(f"LDAP connection error: {e}")
            return False
    
    def disconnect(self):
        """Close LDAP connection"""
        if self.conn:
            try:
                self.conn.unbind_s()
            except:
                pass
    
    def search_users(self):
        """
        Search for users matching the configured filter
        Returns list of user dictionaries
        """
        if not self.conn:
            if not self.connect():
                return []
        
        # Convert FreeRADIUS filter format to LDAP filter format
        # Example: (&(sAMAccountName=%{User-Name})(memberOf=...))
        # We need to search for all users, so we modify the filter
        ldap_filter = self.user_filter
        
        # Extract memberOf portion if it exists
        if 'memberOf=' in ldap_filter:
            # Extract the memberOf filter part
            member_of_match = re.search(r'memberOf=([^)]+)', ldap_filter)
            if member_of_match:
                member_of_dn = member_of_match.group(1)
                # Create a simple filter for user enumeration
                ldap_filter = f'(&(objectClass=user)(memberOf={member_of_dn}))'
            else:
                ldap_filter = '(objectClass=user)'
        else:
            ldap_filter = '(objectClass=user)'
        
        try:
            # The previous code block already determined the search_filter
            # Renaming ldap_filter to search_filter for clarity in the try block
            search_filter = ldap_filter
            
            # Attributes to retrieve
            attributes = ['sAMAccountName', 'displayName', 'mail', 'cn', 'givenName', 'sn', 'userPrincipalName']
            
            # Perform search
            # Using search_s directly and then processing results
            result_set = self.conn.search_s(
                self.base_dn,
                ldap.SCOPE_SUBTREE,
                search_filter,
                attributes
            )
            
            users = []
            for dn, attrs in result_set:
                if dn is None:
                    continue
                
                # Extract user information using _get_attr helper
                username = self._get_attr(attrs, 'sAMAccountName')
                if not username:
                    continue
                
                full_name = (
                    self._get_attr(attrs, 'displayName') or
                    self._get_attr(attrs, 'cn') or
                    f"{self._get_attr(attrs, 'givenName') or ''} {self._get_attr(attrs, 'sn') or ''}".strip()
                )
                email = (
                    self._get_attr(attrs, 'mail') or
                    self._get_attr(attrs, 'userPrincipalName') or
                    ''
                )
                
                users.append({
                    'username': username,
                    'full_name': full_name,
                    'email': email
                })
            
            return users
            
        except ldap.LDAPError as e:
            current_app.logger.error(f"LDAP search error: {e}")
            return None
    
    def _get_attr(self, attrs, key):
        """Helper to extract LDAP attribute value"""
        if key in attrs and attrs[key]:
            value = attrs[key][0]
            # Decode bytes to string if needed
            if isinstance(value, bytes):
                return value.decode('utf-8')
            return str(value)
        return None
    
    def authenticate_user(self, username, password):
        """
        Authenticate a user against LDAP (not used for WebUI, but useful for testing)
        """
        try:
            # Search for user DN
            search_filter = f"(sAMAccountName={username})"
            result = self.conn.search_s(
                self.base_dn,
                ldap.SCOPE_SUBTREE,
                search_filter,
                ['dn']
            )
            
            if not result:
                return False
            
            user_dn = result[0][0]
            
            # Try to bind with user credentials
            test_conn = ldap.initialize(self.server)
            test_conn.set_option(ldap.OPT_REFERRALS, 0)
            test_conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
            test_conn.simple_bind_s(user_dn, password)
            test_conn.unbind_s()
            
            return True
            
        except ldap.LDAPError:
            return False
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()
