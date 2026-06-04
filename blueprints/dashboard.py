"""
Dashboard blueprint - Main dashboard and onboarding routes.
"""

from flask import Blueprint, render_template, redirect, url_for, session, request
from utils.decorators import login_required
from db import get_db
from datetime import date, datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard', methods=['GET'])
@login_required
def index():
    """Main dashboard."""
    # Delegate to app.py's index view for now (single source of truth during migration)
    from app import index as _index
    return _index()


@dashboard_bp.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    """Post-registration onboarding screen."""
    from flask import request as req, redirect, url_for
    if req.method == 'POST':
        weight = req.form.get('weight', '').strip()
        height = req.form.get('height', '').strip()
        weekly_goal = req.form.get('weekly_goal_km', '').strip()

        conn = get_db()
        conn.execute(
            """UPDATE users SET weight = ?, height = ?, weekly_goal_km = ?
               WHERE id = ?""",
            (
                float(weight) if weight else None,
                float(height) if height else None,
                float(weekly_goal) if weekly_goal else None,
                session['user_id']
            )
        )
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard.index'))

    return render_template('onboarding.html')
