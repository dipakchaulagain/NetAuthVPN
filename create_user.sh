#!/bin/bash
# Quick script to create admin user
cd /home/dipakc/vpn-gw/webui
source venv/bin/activate

python3 << 'EOFPYTHON'
from app import create_app, db
from app.models import WebUIUser

app = create_app()

with app.app_context():
    # Prompt for details
    import getpass
    
    print("Create WebUI Admin User")
    print("=" * 40)
    
    username = input("Username: ")
    
    # Check if exists
    existing = WebUIUser.query.filter_by(username=username).first()
    if existing:
        print(f"\n❌ User '{username}' already exists!")
        exit(1)
    
    full_name = input("Full Name: ")
    email = input("Email: ")
    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm Password: ")
    
    if password != password_confirm:
        print("\n❌ Passwords do not match!")
        exit(1)
    
    print("\nSelect Role:")
    print("1. Administrator (full access)")
    print("2. Operator (no OpenVPN/FreeRADIUS restart)")
    print("3. Viewer (read-only)")
    print("4. Auditor (dashboard + accounting only)")
    
    role_choice = input("Choice [1-4]: ")
    roles = {
        '1': 'Administrator',
        '2': 'Operator',
        '3': 'Viewer',
        '4': 'Auditor'
    }
    role = roles.get(role_choice, 'Administrator')
    
    # Create user
    new_user = WebUIUser(
        username=username,
        full_name=full_name,
        email=email,
        role=role,
        active=True
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    print(f"\n✅ User '{username}' created successfully!")
    print(f"   Role: {role}")
EOFPYTHON
