from flask import Blueprint
from app.accounting import routes

accounting_bp = routes.accounting_bp

__all__ = ['accounting_bp']
