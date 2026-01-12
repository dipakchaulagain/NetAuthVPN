from flask import Blueprint
from app.security import routes

security_bp = routes.security_bp

__all__ = ['security_bp']
