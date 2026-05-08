"""
Services package - Business logic layer.
"""

from .auth_service import (
    get_current_user,
    get_user_role,
    authenticate_user,
    register_user,
    change_user_pin,
    log_activity
)

from .run_service import (
    add_run,
    update_run,
    delete_run,
    get_user_runs,
    calculate_stats,
    generate_run_insight
)

from .badge_service import (
    evaluate_badges_for_user,
    award_badge,
    get_user_badges
)

from .streak_service import (
    calculate_streak_for_user,
    update_user_stats
)

__all__ = [
    'get_current_user',
    'get_user_role',
    'authenticate_user',
    'register_user',
    'change_user_pin',
    'log_activity',
    'add_run',
    'update_run',
    'delete_run',
    'get_user_runs',
    'calculate_stats',
    'generate_run_insight',
    'evaluate_badges_for_user',
    'award_badge',
    'get_user_badges',
    'calculate_streak_for_user',
    'update_user_stats'
]
