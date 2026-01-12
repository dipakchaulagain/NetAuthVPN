from flask import Blueprint
from app.users import routes

users_bp = routes.users_bp

__all__ = ['users_bp']
