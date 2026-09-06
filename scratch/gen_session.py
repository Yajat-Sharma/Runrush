"""Generate a valid Flask session cookie without importing the full app."""
import json
import base64
from itsdangerous import URLSafeTimedSerializer
from flask.sessions import SecureCookieSessionInterface

class SimpleApp:
    secret_key = 'dc5843c7fd08c4a04e467ce3e26678c2649233a5c9cfae4452a6f789d86894e3'
    config = {'SECRET_KEY': secret_key}

class SimpleSession(dict):
    modified = False
    accessed = False
    new = False

# We'll use Flask's own signing mechanism
from itsdangerous import URLSafeTimedSerializer, BadSignature
from flask.sessions import TaggedJSONSerializer

secret = 'dc5843c7fd08c4a04e467ce3e26678c2649233a5c9cfae4452a6f789d86894e3'
salt = 'cookie-session'

# Session data: user_id=1 (Yajat), username='Yajat'
session_data = {'user_id': 1, 'username': 'Yajat'}

serializer = URLSafeTimedSerializer(
    secret_key=secret,
    salt=salt,
    serializer=TaggedJSONSerializer(),
    signer_kwargs={'key_derivation': 'hmac', 'digest_method': 'sha1'}
)

cookie_value = serializer.dumps(session_data)
print(cookie_value)
