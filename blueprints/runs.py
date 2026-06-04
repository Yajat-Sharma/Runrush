"""
Runs blueprint - Run CRUD routes.
"""

from flask import Blueprint, request, redirect, url_for, session, jsonify, render_template
from utils.decorators import login_required
from services.run_service import add_run, delete_run, update_run, get_user_runs
from services.streak_service import update_user_stats
from services.badge_service import evaluate_badges_for_user
from db import get_db

runs_bp = Blueprint('runs', __name__)


@runs_bp.route('/add', methods=['POST'])
@login_required
def add():
    """Add a new run."""
    user_id = session['user_id']

    # Gather form data
    date_str = request.form.get('date', '').strip()
    distance = request.form.get('distance', '').strip()
    time_min = request.form.get('time_min', '').strip()
    run_type = request.form.get('run_type', 'easy').strip()
    notes = request.form.get('notes', '').strip()

    # Fetch user weight for calorie calculation
    conn = get_db()
    user_row = conn.execute("SELECT weight FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    weight = float(user_row['weight']) if user_row and user_row['weight'] else 70.0

    success, run_id, insight, error = add_run(
        user_id=user_id,
        date_str=date_str,
        distance_km=float(distance) if distance else 0,
        time_min=float(time_min) if time_min else 0,
        run_type=run_type,
        notes=notes,
        weight_kg=weight,
    )

    if not success:
        return redirect(url_for('dashboard.index') + f'?error={error}')

    # Update stats and evaluate badges
    update_user_stats(user_id, date_str, float(distance) if distance else 0, 'add')
    new_badges = evaluate_badges_for_user(user_id, run_id)

    # Return JSON with badge info so frontend can display confetti
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'runId': run_id,
            'insight': insight,
            'newBadges': new_badges
        })

    return redirect(url_for('dashboard.index'))


@runs_bp.route('/delete/<int:run_id>', methods=['POST'])
@login_required
def delete(run_id):
    """Delete a run."""
    user_id = session['user_id']
    success, distance_km, date_str, error = delete_run(run_id, user_id)

    if success and distance_km is not None:
        update_user_stats(user_id, date_str, distance_km, 'delete')

    return redirect(url_for('dashboard.index'))


@runs_bp.route('/edit/<int:run_id>', methods=['GET', 'POST'])
@login_required
def edit(run_id):
    """Edit a run (within 24-hour window)."""
    # Delegate to the monolith's edit route during migration
    from app import edit as _edit
    return _edit(run_id)


@runs_bp.route('/export')
@login_required
def export():
    """Export runs as CSV."""
    from app import export as _export
    return _export()
