# RunRush - Developer Quick Reference

## 🚀 Quick Start

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/your-username/runrush.git
cd runrush

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# Initialize database
flask init-db

# Run development server
python app_new.py
```

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test file
pytest tests/test_auth.py -v

# Watch mode (requires pytest-watch)
ptw
```

---

## 📁 Project Structure

```
runrush/
├── app_new.py              # Application factory
├── config.py               # Configuration classes
├── extensions.py           # Flask extensions
├── db.py                   # Database abstraction
│
├── models/                 # Data models
│   └── user.py            # User model with password hashing
│
├── services/              # Business logic layer
│   ├── auth_service.py    # Authentication
│   ├── run_service.py     # Run management
│   ├── badge_service.py   # Badge system
│   └── streak_service.py  # Streak calculation
│
├── blueprints/            # Route handlers
│   ├── auth.py           # Login, register, logout
│   ├── dashboard.py      # Main dashboard
│   ├── runs.py           # Run CRUD
│   ├── social.py         # Social features
│   ├── admin.py          # Admin panel
│   └── api/v1/           # Versioned API
│
├── utils/                # Utilities
│   ├── validators.py     # Input validation
│   ├── decorators.py     # Custom decorators
│   └── rate_limiter.py   # Rate limiting
│
└── tests/                # Test suite
    ├── conftest.py       # Pytest fixtures
    ├── test_auth.py      # Auth tests
    └── test_*.py         # Other tests
```

---

## 🔧 Common Tasks

### Add a New Route

```python
# 1. Create/edit blueprint file
# blueprints/my_feature.py

from flask import Blueprint, render_template
from utils.decorators import login_required

my_feature_bp = Blueprint('my_feature', __name__)

@my_feature_bp.route('/my-route')
@login_required
def my_route():
    return render_template('my_template.html')

# 2. Register blueprint in app_new.py
from blueprints.my_feature import my_feature_bp
app.register_blueprint(my_feature_bp)
```

### Add a New Service Function

```python
# services/my_service.py

from db import get_db

def my_business_logic(user_id, data):
    """
    Business logic description.
    
    Args:
        user_id: User ID
        data: Input data
        
    Returns:
        tuple: (success: bool, result: any, error: str or None)
    """
    conn = get_db()
    try:
        # Your logic here
        result = conn.execute("SELECT ...").fetchone()
        conn.commit()
        return True, result, None
    except Exception as e:
        return False, None, str(e)
    finally:
        conn.close()
```

### Add Input Validation

```python
# utils/validators.py

def validate_my_input(value):
    """
    Validate my input.
    
    Args:
        value: Value to validate
        
    Returns:
        validated_value: Validated and sanitized value
        
    Raises:
        ValidationError: If validation fails
    """
    if not value:
        raise ValidationError("Value is required")
    
    # Validation logic
    if not isinstance(value, str):
        raise ValidationError("Value must be a string")
    
    return value.strip()
```

### Add a Test

```python
# tests/test_my_feature.py

import pytest

class TestMyFeature:
    """Test my feature."""
    
    def test_my_function(self, app):
        """Test my function."""
        with app.app_context():
            from services.my_service import my_business_logic
            
            success, result, error = my_business_logic(1, {'key': 'value'})
            
            assert success is True
            assert result is not None
            assert error is None
```

---

## 🔐 Security Checklist

When adding new features:

- [ ] Validate all user inputs
- [ ] Sanitize HTML content
- [ ] Use parameterized queries (no string concatenation)
- [ ] Add CSRF token to forms
- [ ] Add rate limiting to sensitive endpoints
- [ ] Use `@login_required` decorator for protected routes
- [ ] Log security-relevant actions
- [ ] Hash sensitive data (passwords, tokens)
- [ ] Use HTTPS in production
- [ ] Set secure cookie flags

---

## 🧪 Testing Guidelines

### Test Structure

```python
class TestFeatureName:
    """Test feature description."""
    
    def setup_method(self):
        """Setup before each test."""
        pass
    
    def teardown_method(self):
        """Cleanup after each test."""
        pass
    
    def test_success_case(self, fixture):
        """Test successful operation."""
        # Arrange
        input_data = {'key': 'value'}
        
        # Act
        result = function_to_test(input_data)
        
        # Assert
        assert result == expected_value
    
    def test_error_case(self, fixture):
        """Test error handling."""
        with pytest.raises(ExpectedException):
            function_to_test(invalid_input)
```

### Fixtures

```python
# tests/conftest.py

@pytest.fixture
def my_fixture(app):
    """Create test data."""
    with app.app_context():
        # Setup
        data = create_test_data()
        yield data
        # Teardown
        cleanup_test_data()
```

---

## 🎨 Code Style

### Python (PEP 8)

```python
# Good
def calculate_pace(distance_km, time_min):
    """Calculate pace in min/km."""
    if distance_km <= 0:
        raise ValueError("Distance must be positive")
    return time_min / distance_km

# Bad
def calc(d,t):
    return t/d
```

### Docstrings

```python
def function_name(arg1, arg2):
    """
    Short description.
    
    Longer description if needed.
    
    Args:
        arg1: Description of arg1
        arg2: Description of arg2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this exception is raised
    """
    pass
```

### Imports

```python
# Standard library
import os
import sys
from datetime import datetime

# Third-party
from flask import Flask, request
import bcrypt

# Local
from models.user import User
from services.auth_service import authenticate_user
```

---

## 🐛 Debugging

### Enable Debug Mode

```python
# config.py
class DevelopmentConfig(Config):
    DEBUG = True
```

### Print Debugging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Variable value: {variable}")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Interactive Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use ipdb (better)
import ipdb; ipdb.set_trace()
```

### Flask Shell

```bash
flask shell

>>> from services.auth_service import get_current_user
>>> from db import get_db
>>> conn = get_db()
>>> users = conn.execute("SELECT * FROM users").fetchall()
>>> print(users)
```

---

## 📊 Database

### Run Migrations

```bash
# Initialize database
flask init-db

# Migrate PINs to hashed format
flask migrate-pins

# Create admin user
flask create-admin
```

### Database Console

```bash
# SQLite
sqlite3 runs.db

# PostgreSQL
psql $DATABASE_URL
```

### Common Queries

```sql
-- List all users
SELECT id, username, role, status FROM users;

-- Count runs per user
SELECT user_id, COUNT(*) as run_count 
FROM runs 
GROUP BY user_id 
ORDER BY run_count DESC;

-- Find users with no runs
SELECT u.id, u.username 
FROM users u 
LEFT JOIN runs r ON u.id = r.user_id 
WHERE r.id IS NULL;

-- Activity in last 7 days
SELECT date, COUNT(*) as runs, SUM(distance_km) as total_km
FROM runs
WHERE date >= date('now', '-7 days')
GROUP BY date
ORDER BY date DESC;
```

---

## 🚀 Deployment

### Local Production Test

```bash
# Set production config
export FLASK_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Run with Gunicorn
gunicorn app_new:app --bind 0.0.0.0:5000 --workers 4
```

### Render Deployment

```bash
# Build command
pip install -r requirements.txt

# Start command
gunicorn app_new:app

# Environment variables (set in Render dashboard)
SECRET_KEY=...
DATABASE_URL=...  # Auto-set by Render
FLASK_ENV=production
REDIS_URL=...  # If using Redis
```

### Health Check Endpoint

```python
@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })
```

---

## 📚 Resources

### Documentation
- Flask: https://flask.palletsprojects.com/
- Pytest: https://docs.pytest.org/
- Bcrypt: https://github.com/pyca/bcrypt/
- Flask-WTF: https://flask-wtf.readthedocs.io/
- Flask-Limiter: https://flask-limiter.readthedocs.io/

### Tools
- Black (formatter): `black .`
- Flake8 (linter): `flake8 .`
- MyPy (type checker): `mypy .`
- Coverage: `pytest --cov=.`

---

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Write code + tests
3. Run tests: `pytest`
4. Format code: `black .`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Create Pull Request

---

## 💡 Tips & Tricks

### Speed Up Tests

```python
# conftest.py
@pytest.fixture(scope='session')
def app():
    """Create app once per test session."""
    app = create_app('testing')
    yield app
```

### Mock External Services

```python
def test_email_sending(mocker):
    """Test email without actually sending."""
    mock_send = mocker.patch('services.email_service.send_email')
    mock_send.return_value = True
    
    result = trigger_email()
    
    assert mock_send.called
    assert result is True
```

### Environment-Specific Config

```bash
# Development
export FLASK_ENV=development

# Testing
export FLASK_ENV=testing

# Production
export FLASK_ENV=production
```

---

## 🆘 Troubleshooting

### "ModuleNotFoundError"
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements-dev.txt
```

### "CSRF token missing"
```html
<!-- Add to all POST forms -->
<form method="POST">
    {{ csrf_token() }}
    <!-- form fields -->
</form>
```

### "Rate limit exceeded"
```python
# Increase limit in blueprint
@limiter.limit("100 per hour")  # Instead of default
def my_route():
    pass
```

### Tests failing
```bash
# Clear pytest cache
pytest --cache-clear

# Run with verbose output
pytest -vv

# Run single test
pytest tests/test_auth.py::TestAuth::test_login -vv
```

---

**Happy Coding!** 🎉
