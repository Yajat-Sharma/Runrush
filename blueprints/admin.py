"""
Admin blueprint - User management, activity logs, admin notes.
"""

from flask import Blueprint, render_template, redirect, url_for, session, request
from utils.decorators import login_required, admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@login_required
@admin_required
def admin_panel():
    """Admin dashboard."""
    from app import admin as _admin
    return _admin()


@admin_bp.route('/user/<int:user_id>/<action>', methods=['POST'])
@login_required
@admin_required
def user_action(user_id, action):
    """Perform an action on a user (block, unblock, promote, etc.)."""
    from app import user_action as _user_action
    return _user_action(user_id, action)


@admin_bp.route('/user/<int:target_user_id>/analytics')
@login_required
@admin_required
def user_analytics(target_user_id):
    """View analytics for a specific user."""
    from app import user_analytics as _user_analytics
    return _user_analytics(target_user_id)
