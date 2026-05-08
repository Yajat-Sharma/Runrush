"""
API v1 - Sync endpoints for offline runs.
"""

from flask import request, jsonify
from extensions import limiter, csrf
from utils.decorators import login_required
from . import api_v1_bp


@api_v1_bp.route('/sync', methods=['POST'])
@csrf.exempt  # Exempt CSRF for API endpoints (use API keys instead)
@limiter.limit("30 per minute")
@login_required
def sync_run():
    """
    Sync an offline run.
    
    POST /api/v1/sync
    
    Request Body:
    {
        "tempId": "offline_123_abc",
        "date": "2026-05-01",
        "distance": 5.0,
        "time": 25.0,
        "notes": "Morning run",
        "hash": "sha256hash",
        "createdAt": 1234567890
    }
    
    Response:
    {
        "success": true,
        "runId": 123,
        "insight": "Great pace today!",
        "newBadges": ["FIRST_5K"],
        "message": "Run synced successfully"
    }
    """
    # Import here to avoid circular imports
    from services.auth_service import get_current_user
    from services.run_service import sync_offline_run
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Sync the run
        result = sync_offline_run(user.id, data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            status_code = result.get('status_code', 400)
            return jsonify({'error': result.get('error', 'Sync failed')}), status_code
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500
