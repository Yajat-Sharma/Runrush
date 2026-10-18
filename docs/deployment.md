# Deployment

RunRush is deployed on Render as a Python web service. Configure the service to install the repository's `requirements.txt` and start the Flask application with Gunicorn.

## Render setup

1. Create a PostgreSQL database and a web service for this repository. Keep the service and database in the same region when possible.
2. Set the build command to `pip install -r requirements.txt`.
3. Set the start command to `gunicorn app:app`.
4. Set `DATABASE_URL` to the database's internal connection URL and set a strong, unique `SECRET_KEY` in the Render environment. Do not commit either value.
5. Add any optional integration credentials (such as Google OAuth or Gemini) only when enabling those integrations.

The application supports SQLite for local development. Use PostgreSQL for persistent hosted data; local SQLite files are not durable across ephemeral deployment instances.

## Migrating existing SQLite data

From the repository root, configure `DATABASE_URL` with the destination PostgreSQL connection string, then run:

```bash
python scripts/migrate_to_pg.py
```

The script reads `runs.db` as the source and writes to the configured PostgreSQL destination. Confirm both database URLs before running it, and keep credentials out of shell history and logs.

## Schema migrations

Versioned SQL migrations live in `migrations/`. Follow [the migration policy](../migrations/README.md); schema migrations are not run automatically during application startup. Review and test migrations against a safe database before production execution.

## Checks after deployment

- Confirm the Render build installs `requirements.txt` successfully.
- Open the service URL and check login and the dashboard.
- Confirm the service uses PostgreSQL through its configured `DATABASE_URL`.
- Review Render logs for startup or database errors.

`ALLOW_DB_INIT` is not read by the current `config.py` or `app.py`; it is not a current deployment setting.
