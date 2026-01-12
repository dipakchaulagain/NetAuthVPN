#!/usr/bin/env python3
"""
VPN Management Web UI
Entry point for the Flask application
"""

from app import create_app, db
from app.models import (
    WebUIUser, VPNUser, VPNUserRoute, SecurityRule,
    DNSRecord, AuditLog, RadReply, RadAcct, RadPostAuth
)
import click

app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell"""
    return {
        'db': db,
        'WebUIUser': WebUIUser,
        'VPNUser': VPNUser,
        'VPNUserRoute': VPNUserRoute,
        'SecurityRule': SecurityRule,
        'DNSRecord': DNSRecord,
        'AuditLog': AuditLog,
        'RadReply': RadReply,
        'RadAcct': RadAcct,
        'RadPostAuth': RadPostAuth
    }

@app.cli.command()
def init_db():
    """Initialize the database"""
    click.echo('Creating database tables...')
    db.create_all()
    click.echo('Database initialized!')

@app.cli.command()
@click.option('--username', prompt=True, help='Username')
@click.option('--password', prompt=True, hide_input=True, 
              confirmation_prompt=True, help='Password')
@click.option('--fullname', prompt=True, help='Full Name')
@click.option('--email', prompt=True, help='Email')
@click.option('--role', type=click.Choice(['Administrator', 'Operator', 'Viewer', 'Auditor']),
              default='Administrator', help='User role')
def create_admin(username, password, fullname, email, role):
    """Create an admin user"""
    user = WebUIUser.query.filter_by(username=username).first()
    
    if user:
        click.echo(f'User {username} already exists!')
        return
    
    new_user = WebUIUser(
        username=username,
        full_name=fullname,
        email=email,
        role=role,
        active=True
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    click.echo(f'User {username} created successfully with role {role}!')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
