# Database Migrations

This directory contains versioned raw SQL migrations for RunRush.
We have selected **yoyo-migrations** (v9.0.0) as our migration tool because it natively supports raw PostgreSQL SQL scripts, tracks migration history seamlessly alongside our raw `psycopg2` setup, and avoids the need to introduce SQLAlchemy ORM just for schema updates.

## Tool & Setup
- **Tool**: `yoyo-migrations` (version 9.0.0)
- **Installation**: Installed via standard `pip install yoyo-migrations==9.0.0` and recorded in `requirements.txt`.
- **Naming Convention**: Migrations should be named sequentially or chronologically, for example: `001_initial_schema.sql`, `002_add_new_feature.sql`.

## Environment Variables
Migrations are executed locally or in CI using a strictly defined environment variable.
To run migrations, you **must** use a dedicated environment variable to specify the database connection:
```bash
export MIGRATION_DATABASE_URL="postgresql://user:pass@localhost:5432/runrush_local"
```
**CRITICAL**: 
- **DO NOT** populate `MIGRATION_DATABASE_URL` with the production database credential in your local `.env`.
- **NEVER** print, echo, or commit the value of this variable.
- Local migrations must always target a safe local or test database.

## Migration Usage

### Creating a New Migration
Create a `.sql` file in the `migrations/` directory following the naming convention.

### Running Migrations Locally
```bash
yoyo apply -d $MIGRATION_DATABASE_URL ./migrations
```

### Checking Migration Status
```bash
yoyo status -d $MIGRATION_DATABASE_URL ./migrations
```

### Rolling Back Migrations
If a rollback is required (and a `.rollback.sql` counterpart exists, or `yoyo` understands the transaction), run:
```bash
yoyo rollback -d $MIGRATION_DATABASE_URL ./migrations
```

## Production Safety Rules
1. **Migrations MUST NOT run automatically** during the Flask application startup (e.g., via `gunicorn` or `app.py`).
2. **Production migrations require explicit execution** by a deployment script or a human operator (e.g., via CI/CD step: `yoyo apply -d $PRODUCTION_MIGRATION_URL`).
3. **Production credentials** (`DATABASE_URL`) must **never** be stored in migration files or locally written configuration files.
4. **All migrations must be reviewed** via a Pull Request before execution against production.
5. The existing `APPROVED_TEST_DB_URL` application guardrail remains fully intact to protect local testing workflows.
