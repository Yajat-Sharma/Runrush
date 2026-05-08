"""
API v1 - Version 1 of the REST API.
"""

from flask import Blueprint, jsonify

api_v1_bp = Blueprint('api_v1', __name__)

# Import route modules
from . import runs, sync, users


@api_v1_bp.route('/')
def index():
    """API v1 index."""
    return jsonify({
        'version': 'v1',
        'title': 'RunRush API',
        'description': 'REST API for RunRush running tracker',
        'endpoints': {
            'runs': '/api/v1/runs',
            'sync': '/api/v1/sync',
            'users': '/api/v1/users',
            'heatmap': '/api/v1/heatmap',
            'badges': '/api/v1/badges'
        },
        'documentation': '/api/v1/docs'
    })


@api_v1_bp.route('/docs')
def docs():
    """API documentation."""
    return jsonify({
        'message': 'API documentation coming soon',
        'swagger_ui': '/api/v1/swagger',
        'openapi_spec': '/api/v1/openapi.json'
    })


@api_v1_bp.errorhandler(400)
def bad_request(e):
    """Handle 400 errors."""
    return jsonify({'error': 'Bad Request', 'message': str(e)}), 400


@api_v1_bp.errorhandler(401)
def unauthorized(e):
    """Handle 401 errors."""
    return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401


@api_v1_bp.errorhandler(403)
def forbidden(e):
    """Handle 403 errors."""
    return jsonify({'error': 'Forbidden', 'message': 'Insufficient permissions'}), 403


@api_v1_bp.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({'error': 'Not Found', 'message': 'Resource not found'}), 404


@api_v1_bp.errorhandler(429)
def rate_limit_exceeded(e):
    """Handle 429 errors."""
    return jsonify({'error': 'Rate Limit Exceeded', 'message': 'Too many requests'}), 429


@api_v1_bp.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal Server Error', 'message': 'An error occurred'}), 500
