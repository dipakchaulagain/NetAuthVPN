from flask import Blueprint
from app.dashboard import routes

dashboard_bp = routes.dashboard_bp

__all__ = ['dashboard_bp']
