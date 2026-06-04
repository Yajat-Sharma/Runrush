"""
API v1 - User endpoints.
"""

from flask import jsonify, session, request
from extensions import limiter, csrf
from utils.decorators import login_required
from . import api_v1_bp


@api_v1_bp.route('/users/search', methods=['GET'])
@login_required
def search_users():
    """
    Search for users by username.

    GET /api/v1/users/search?q=<query>
    """
    from db import get_db

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400

    user_id = session['user_id']
    conn = get_db()
    users = conn.execute(
        """SELECT id, username, display_name
           FROM users
           WHERE username LIKE ? AND id != ? AND status = 'active'
           LIMIT 10""",
        (f'%{query}%', user_id)
    ).fetchall()
    conn.close()

    return jsonify({
        'success': True,
        'users': [
            {
                'id': u['id'],
                'username': u['username'],
                'display_name': u['display_name'] or u['username'],
            }
            for u in users
        ]
    })


@api_v1_bp.route('/users/me', methods=['GET'])
@login_required
def get_me():
    """
    Get the current user's profile.

    GET /api/v1/users/me
    """
    from services.auth_service import get_current_user

    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'weight': user['weight'],
            'height': user['height'],
            'weekly_goal_km': user['weekly_goal_km'],
            'theme': user['theme'],
            'role': user['role'],
            'status': user['status'],
        }
    })


@api_v1_bp.route('/users/me/stats', methods=['GET'])
@login_required
def get_my_stats():
    """
    Get the current user's cached statistics.

    GET /api/v1/users/me/stats
    """
    from db import get_db

    user_id = session['user_id']
    conn = get_db()
    stats = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if not stats:
        return jsonify({
            'success': True,
            'stats': {
                'total_distance_km': 0,
                'current_streak': 0,
                'best_streak': 0,
                'last_activity_date': None,
            }
        })

    return jsonify({
        'success': True,
        'stats': {
            'total_distance_km': stats['total_distance_km'],
            'current_streak': stats['current_streak'],
            'best_streak': stats['best_streak'],
            'last_activity_date': stats['last_activity_date'],
        }
    })
