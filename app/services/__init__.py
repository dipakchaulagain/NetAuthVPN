from flask import Blueprint
from app.services import routes

services_bp = routes.services_bp

__all__ = ['services_bp']
