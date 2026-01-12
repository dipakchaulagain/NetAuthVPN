from app import db
from app.models import RadReply, RadCheck
from flask import current_app

class RADIUSManager:
    """Manage RADIUS reply attributes for VPN users"""
    
    @staticmethod
    def set_user_ip(username, ip_address):
        """
        Set or update Framed-IP-Address for a user in radreply table
        This is critical for VPN IP assignment
        """
        try:
            # Check if entry exists
            existing = RadReply.query.filter_by(
                username=username,
                attribute='Framed-IP-Address'
            ).first()
            
            if existing:
                # Update existing IP
                existing.value = ip_address
                current_app.logger.info(f"Updated Framed-IP-Address for {username}: {ip_address}")
            else:
                # Create new entry
                new_reply = RadReply(
                    username=username,
                    attribute='Framed-IP-Address',
                    op=':=',
                    value=ip_address
                )
                db.session.add(new_reply)
                current_app.logger.info(f"Created Framed-IP-Address for {username}: {ip_address}")
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error setting user IP: {e}")
            return False
    
    @staticmethod
    def add_user_route(username, route):
        """
        Add a Framed-Route for a user in radreply table
        Routes can be multiple, so we add new entries
        """
        try:
            # Check if this exact route already exists
            existing = RadReply.query.filter_by(
                username=username,
                attribute='Framed-Route',
                value=route
            ).first()
            
            if existing:
                current_app.logger.info(f"Route already exists for {username}: {route}")
                return True
            
            # Add new route
            new_route = RadReply(
                username=username,
                attribute='Framed-Route',
                op='+=',  # Use += for multiple routes
                value=route
            )
            db.session.add(new_route)
            db.session.commit()
            current_app.logger.info(f"Added Framed-Route for {username}: {route}")
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding route: {e}")
            return False
    
    @staticmethod
    def set_account_status(username, enabled=True):
        """
        Set or update Auth-Type in radcheck table
        
        Args:
            username: VPN username
            enabled: True for 'LDAP', False for 'Reject'
        
        Returns:
            Boolean indicating success
        """
        try:
            auth_type = 'LDAP' if enabled else 'Reject'
            
            # Check if entry exists
            check_entry = RadCheck.query.filter_by(
                username=username,
                attribute='Auth-Type'
            ).first()
            
            if check_entry:
                # Update existing entry
                check_entry.value = auth_type
                current_app.logger.info(f"Updated Auth-Type for {username}: {auth_type}")
            else:
                # Create new entry
                check_entry = RadCheck(
                    username=username,
                    attribute='Auth-Type',
                    op=':=',
                    value=auth_type
                )
                db.session.add(check_entry)
                current_app.logger.info(f"Created Auth-Type for {username}: {auth_type}")
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error setting Auth-Type for {username}: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def remove_account_status(username):
        """
        Remove Auth-Type entry from radcheck table
        
        Args:
            username: VPN username
        
        Returns:
            Boolean indicating success
        """
        try:
            RadCheck.query.filter_by(
                username=username,
                attribute='Auth-Type'
            ).delete()
            
            db.session.commit()
            current_app.logger.info(f"Removed Auth-Type for {username}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error removing Auth-Type for {username}: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def remove_user_route(username, route):
        """Remove a specific route for a user"""
        try:
            route_entry = RadReply.query.filter_by(
                username=username,
                attribute='Framed-Route',
                value=route
            ).first()
            
            if route_entry:
                db.session.delete(route_entry)
                db.session.commit()
                current_app.logger.info(f"Removed Framed-Route for {username}: {route}")
                return True
            
            return False
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing route: {e}")
            return False
    
    @staticmethod
    def sync_user_routes(username, routes):
        """
        Sync all routes for a user (remove old ones, add new ones)
        routes: list of route strings
        """
        try:
            # Get existing routes
            existing_routes = RadReply.query.filter_by(
                username=username,
                attribute='Framed-Route'
            ).all()
            
            existing_values = {r.value for r in existing_routes}
            new_values = set(routes)
            
            # Remove routes that are no longer needed
            for route in existing_routes:
                if route.value not in new_values:
                    db.session.delete(route)
                    current_app.logger.info(f"Removed route {route.value} for {username}")
            
            # Add new routes
            for route in new_values:
                if route not in existing_values:
                    new_route = RadReply(
                        username=username,
                        attribute='Framed-Route',
                        op='+=',
                        value=route
                    )
                    db.session.add(new_route)
                    current_app.logger.info(f"Added route {route} for {username}")
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error syncing routes: {e}")
            return False
    
    @staticmethod
    def remove_user(username):
        """Remove all RADIUS reply entries for a user"""
        try:
            RadReply.query.filter_by(username=username).delete()
            db.session.commit()
            current_app.logger.info(f"Removed all RADIUS entries for {username}")
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing user: {e}")
            return False
    
    @staticmethod
    def get_user_attributes(username):
        """Get all RADIUS reply attributes for a user"""
        return RadReply.query.filter_by(username=username).all()
