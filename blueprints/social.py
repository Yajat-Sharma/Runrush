"""
Social blueprint - Social feed, follow/unfollow, leaderboard, discover.
"""

from flask import Blueprint, render_template, redirect, url_for, session, request
from utils.decorators import login_required

social_bp = Blueprint('social', __name__)


@social_bp.route('/social-feed')
@login_required
def social_feed():
    """Social feed of followed runners."""
    from app import social_feed as _social_feed
    return _social_feed()


@social_bp.route('/leaderboard')
@login_required
def leaderboard():
    """All-time and weekly leaderboard."""
    from app import leaderboard as _leaderboard
    return _leaderboard()


@social_bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    """Follow a runner."""
    from app import follow as _follow
    return _follow(username)


@social_bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    """Unfollow a runner."""
    from app import unfollow as _unfollow
    return _unfollow(username)
