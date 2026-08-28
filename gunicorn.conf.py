import os

port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"
