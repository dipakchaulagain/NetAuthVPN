from flask import Blueprint
from app.dns import routes

dns_bp = routes.dns_bp

__all__ = ['dns_bp']
