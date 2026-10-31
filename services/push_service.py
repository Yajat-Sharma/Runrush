"""Web Push delivery helpers for authenticated RunRush subscriptions."""

import json
import os


class PushConfigurationError(RuntimeError):
    """Raised when VAPID delivery is not configured."""


def send_push(subscription, payload):
    """Send one JSON payload through the configured Web Push service."""
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subject = os.environ.get("VAPID_SUBJECT", "").strip()
    if not private_key or not subject:
        raise PushConfigurationError("VAPID push delivery is not configured.")

    try:
        from pywebpush import webpush
    except ImportError as exc:
        raise PushConfigurationError("The pywebpush dependency is not installed.") from exc

    return webpush(
        subscription_info=subscription,
        data=json.dumps(payload),
        vapid_private_key=private_key,
        vapid_claims={"sub": subject},
    )
