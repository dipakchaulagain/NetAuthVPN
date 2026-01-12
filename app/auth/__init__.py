from flask import Blueprint
from app.auth import routes

auth_bp = routes.auth_bp

__all__ = ['auth_bp']
