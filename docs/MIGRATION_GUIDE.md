# RunRush - Migration Guide to Improved Architecture

## Overview

This guide explains how to migrate from the original `app.py` to the new modular architecture with enhanced security.

## What's New

### 1. **Security Improvements**
- ✅ **Bcrypt Password Hashing**: PINs now hashed with bcrypt (12 rounds)
- ✅ **CSRF Protection**: Flask-WTF CSRF tokens on all forms
- ✅ **Rate Limiting**: Flask-Limiter with configurable limits
- ✅ **Input Sanitization**: Bleach for HTML, comprehensive validators
- ✅ **Login Attempt Tracking**: 5 attempts per 5 minutes

### 2. **Architecture Improvements**
- ✅ **Modular Blueprints**: Code split into logical modules
- ✅ **Service Layer**: Business logic separated from routes
- ✅ **Configuration Management**: Environment-based config
- ✅ **Application Factory**: Testable app creation

### 3. **Testing Infrastructure**
- ✅ **Pytest Framework**: Modern testing with fixtures
- ✅ **Unit Tests**: Auth, validators, rate limiting
- ✅ **Integration Tests**: API endpoints
- ✅ **Test Coverage**: pytest-cov integration

### 4. **API Versioning**
- ✅ **Versioned Endpoints**: `/api/v1/` prefix
- ✅ **Consistent Responses**: JSON error handling
- ✅ **Documentation Ready**: OpenAPI/Swagger structure

---

## Migration Steps

### Step 1: Install New Dependencies

```bash
pip install -r requirements-new.txt
```

**New packages:**
- `bcrypt==4.1.2` - Password hashing
- `Flask-WTF==1.2.1` - CSRF protection
- `Flask-Limiter==3.5.0` - Rate limiting
- `bleach==6.1.0` - HTML sanitization
- `redis==5.0.1` - Rate limit storage (optional)

### Step 2: Set Environment Variables

Update your `.env` file:

```env
# Required
SECRET_KEY=your-secret-key-here-change-this
DATABASE_URL=sqlite:///runs.db  # or postgresql://...

# Optional
FLASK_ENV=production  # development, testing, production
REDIS_URL=redis://localhost:6379  # for rate limiting (or use memory://)
ADMIN_USER_ID=1
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=RunRush <noreply@runrush.app>
```

### Step 3: Migrate Existing PINs to Hashed Format

**CRITICAL**: Existing PINs are stored as plaintext. You must migrate them:

```bash
# Using Flask CLI
flask migrate-pins

# Or manually in Python
python -c "
from app_new import create_app
app = create_app()
with app.app_context():
    from flask.cli import with_appcontext
    import click
    ctx = app.test_cli_runner()
    ctx.invoke(app.cli.commands['migrate-pins'])
"
```

This command:
1. Reads all users from database
2. Checks if PIN is already hashed (starts with `$2`)
3. Hashes plaintext PINs with bcrypt
4. Updates database

**⚠️ WARNING**: After migration, old plaintext PINs will no longer work. Users must use their original PINs (which are now hashed).

### Step 4: Update Database Schema (if needed)

The new code is backward compatible with existing schema. No schema changes required.

### Step 5: Test the New Application

```bash
# Run tests
pytest tests/ -v --cov=. --cov-report=html

# Start development server
python app_new.py

# Or use Flask CLI
export FLASK_APP=app_new.py
flask run
```

### Step 6: Update Production Deployment

#### For Render:

1. Update `requirements.txt`:
   ```bash
   cp requirements-new.txt requirements.txt
   ```

2. Update start command:
   ```bash
   gunicorn app_new:app
   ```

3. Set environment variables in Render dashboard:
   - `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `FLASK_ENV=production`
   - `DATABASE_URL` (auto-set by Render)
   - `REDIS_URL` (if using Redis for rate limiting)

4. Deploy and run migration:
   ```bash
   # SSH into Render instance or use Render Shell
   flask migrate-pins
   ```

---

## Code Structure Comparison

### Before (Original)
```
runrush/
├── app.py (2590 lines - everything)
├── db.py
├── requirements.txt
└── templates/
```

### After (Improved)
```
runrush/
├── app_new.py (main factory)
├── config.py (configuration)
├── extensions.py (Flask extensions)
├── db.py (unchanged)
├── models/
│   └── user.py (User model with hashing)
├── services/
│   ├── auth_service.py
│   ├── run_service.py
│   ├── badge_service.py
│   └── streak_service.py
├── blueprints/
│   ├── auth.py
│   ├── dashboard.py
│   ├── runs.py
│   ├── social.py
│   ├── admin.py
│   └── api/v1/
├── utils/
│   ├── validators.py
│   ├── decorators.py
│   └── rate_limiter.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_validators.py
│   └── test_rate_limiter.py
└── requirements-new.txt
```

---

## Breaking Changes

### 1. PIN Storage Format
- **Before**: Plaintext PINs in database
- **After**: Bcrypt hashed PINs
- **Migration**: Run `flask migrate-pins` command

### 2. Import Paths
- **Before**: `from app import get_current_user`
- **After**: `from services.auth_service import get_current_user`

### 3. Route URLs
- **Before**: `/login`, `/register`
- **After**: `/auth/login`, `/auth/register`
- **API**: `/api/sync-run` → `/api/v1/sync`

### 4. CSRF Tokens Required
- **Before**: No CSRF protection
- **After**: All POST forms need CSRF token

**Template Update:**
```html
<!-- Add to all forms -->
<form method="POST">
    {{ csrf_token() }}
    <!-- form fields -->
</form>
```

---

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_auth.py -v
```

### Run with Coverage
```bash
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

### Run Tests in CI/CD
```bash
# GitHub Actions example
pytest tests/ --cov=. --cov-report=xml
```

---

## Performance Considerations

### Rate Limiting Storage

**Memory (Default)**:
- Fast, no external dependencies
- Lost on restart
- Good for development

**Redis (Recommended for Production)**:
```python
# config.py
RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
```

Benefits:
- Persistent across restarts
- Shared across multiple workers
- Better for production

### Bcrypt Cost Factor

```python
# config.py
BCRYPT_LOG_ROUNDS = 12  # Default (secure)
# Increase for more security (slower)
# Decrease for faster tests (less secure)
```

---

## Rollback Plan

If you need to rollback:

1. **Keep original `app.py`**:
   ```bash
   git checkout app.py
   ```

2. **Revert requirements**:
   ```bash
   pip install -r requirements.txt
   ```

3. **PINs are still compatible**: Bcrypt can verify both hashed and plaintext (if you haven't deleted old code)

---

## Gradual Migration Strategy

You can run both versions side-by-side:

1. **Deploy new version to staging**:
   ```bash
   gunicorn app_new:app --bind 0.0.0.0:5001
   ```

2. **Keep old version running**:
   ```bash
   gunicorn app:app --bind 0.0.0.0:5000
   ```

3. **Use load balancer** to gradually shift traffic

4. **Monitor errors** and performance

5. **Full cutover** when confident

---

## Troubleshooting

### Issue: "Invalid username or PIN" after migration
**Cause**: PINs not migrated  
**Solution**: Run `flask migrate-pins`

### Issue: "CSRF token missing"
**Cause**: Forms missing CSRF token  
**Solution**: Add `{{ csrf_token() }}` to forms

### Issue: "Too many requests"
**Cause**: Rate limiting triggered  
**Solution**: Wait or increase limits in config

### Issue: Tests failing
**Cause**: Missing test dependencies  
**Solution**: `pip install -r requirements-dev.txt`

---

## Support

For issues or questions:
1. Check this migration guide
2. Review test files for examples
3. Check `IMPROVEMENTS_PLAN.md` for architecture details
4. Open an issue on GitHub

---

## Next Steps

After successful migration:

1. ✅ **Enable HTTPS** in production (set `SESSION_COOKIE_SECURE=True`)
2. ✅ **Set up Redis** for rate limiting
3. ✅ **Configure monitoring** (Sentry, New Relic, etc.)
4. ✅ **Set up CI/CD** with automated tests
5. ✅ **Add API documentation** (Swagger UI)
6. ✅ **Implement API keys** for external access

---

## Checklist

- [ ] Install new dependencies
- [ ] Set environment variables
- [ ] Run PIN migration
- [ ] Update templates with CSRF tokens
- [ ] Run tests
- [ ] Deploy to staging
- [ ] Test thoroughly
- [ ] Deploy to production
- [ ] Monitor for errors
- [ ] Update documentation

---

**Migration Complete!** 🎉

Your RunRush application now has:
- 🔒 Secure password hashing
- 🛡️ CSRF protection
- ⏱️ Rate limiting
- 🧪 Comprehensive tests
- 📦 Modular architecture
- 🚀 API versioning
