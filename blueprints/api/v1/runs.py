"""
API v1 - Run endpoints.
"""

from flask import request, jsonify, session
from extensions import limiter, csrf
from utils.decorators import login_required
from . import api_v1_bp


@api_v1_bp.route('/runs', methods=['GET'])
@login_required
def get_runs():
    """
    Get runs for the current user.

    GET /api/v1/runs
    Query params:
        sort  - 'date' | 'distance' | 'time'  (default: date)
        filter - 'all' | 'last7' | 'month' | '5k10k'  (default: all)
    """
    from services.run_service import get_user_runs

    user_id = session['user_id']
    sort_by = request.args.get('sort', 'date')
    filter_opt = request.args.get('filter', 'all')

    runs = get_user_runs(user_id, sort_by=sort_by, filter_opt=filter_opt)

    return jsonify({
        'success': True,
        'runs': [
            {
                'id': r['id'],
                'date': r['date'],
                'distance_km': r['distance_km'],
                'time_min': r['time_min'],
                'pace': r['pace'],
                'calories': r['calories'],
                'run_type': r['run_type'],
                'notes': r['notes'],
                'insight': r['insight'],
                'created_at': r['created_at'],
            }
            for r in runs
        ],
        'count': len(runs)
    })


@api_v1_bp.route('/runs', methods=['POST'])
@csrf.exempt
@limiter.limit("60 per minute")
@login_required
def create_run():
    """
    Create a new run via API.

    POST /api/v1/runs
    Body: { date, distance, time, run_type, notes }
    """
    from services.run_service import add_run
    from services.streak_service import update_user_stats
    from services.badge_service import evaluate_badges_for_user
    from db import get_db

    user_id = session['user_id']

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    conn = get_db()
    user_row = conn.execute("SELECT weight FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    weight = float(user_row['weight']) if user_row and user_row['weight'] else 70.0

    success, run_id, insight, error = add_run(
        user_id=user_id,
        date_str=data.get('date', ''),
        distance_km=float(data.get('distance', 0)),
        time_min=float(data.get('time', 0)),
        run_type=data.get('run_type', 'easy'),
        notes=data.get('notes', ''),
        weight_kg=weight,
    )

    if not success:
        return jsonify({'error': error}), 400

    update_user_stats(user_id, data.get('date', ''), float(data.get('distance', 0)), 'add')
    new_badges = evaluate_badges_for_user(user_id, run_id)

    return jsonify({
        'success': True,
        'runId': run_id,
        'insight': insight,
        'newBadges': new_badges,
        'message': 'Run created successfully'
    }), 201


@api_v1_bp.route('/runs/<int:run_id>', methods=['DELETE'])
@csrf.exempt
@limiter.limit("30 per minute")
@login_required
def delete_run(run_id):
    """
    Delete a run.

    DELETE /api/v1/runs/<run_id>
    """
    from services.run_service import delete_run as _delete_run
    from services.streak_service import update_user_stats

    user_id = session['user_id']
    success, distance_km, date_str, error = _delete_run(run_id, user_id)

    if not success:
        return jsonify({'error': error}), 404

    update_user_stats(user_id, date_str, distance_km, 'delete')

    return jsonify({'success': True, 'message': 'Run deleted'})
