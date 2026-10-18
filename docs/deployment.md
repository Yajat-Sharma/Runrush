# Deployment

RunRush is deployed on Render as a Python web service. Configure the service to install the repository's `requirements.txt` and start the Flask application with Gunicorn.

## Render setup

1. Create a PostgreSQL database and a web service for this repository. Keep the service and database in the same region when possible.
2. Set the build command to `pip install -r requirements.txt`.
3. Set the start command to `gunicorn app:app`.
4. Set `FLASK_ENV=production`, `DATABASE_URL` to the database's internal connection URL, and a strong, unique `SECRET_KEY` in the Render environment. Do not commit these values.
5. Configure optional environment variables only for the integrations you enable:
   - `ADMIN_USER_ID` (defaults to `1`)
   - `REDIS_URL` for shared rate-limit storage (defaults to in-memory storage)
   - `RESEND_API_KEY` and `RESEND_FROM_EMAIL` for email delivery
   - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` for Google sign-in
   - `GEMINI_API_KEY` for screenshot import
   - `CRON_SECRET` for scheduled endpoints

The application supports SQLite for local development. Use PostgreSQL for persistent hosted data; local SQLite files are not durable across ephemeral deployment instances.

## Migrating existing SQLite data

From the repository root, configure `DATABASE_URL` with the destination PostgreSQL connection string, then run:

```bash
python scripts/migrate_to_pg.py
```

The script reads `runs.db` as the source and writes to the configured PostgreSQL destination. Confirm both database URLs before running it, and keep credentials out of shell history and logs.

## Schema migrations

Versioned SQL migrations live in `migrations/`. Follow [the migration policy](../migrations/README.md); the application does not run `init_db` automatically at startup. In a controlled deployment environment with the approved production target configured, check the migration status and apply reviewed migrations explicitly:

```bash
yoyo status -d "$PRODUCTION_MIGRATION_URL" ./migrations
yoyo apply -d "$PRODUCTION_MIGRATION_URL" ./migrations
```

Review and test migrations against a safe database before production execution. If transferring an existing local SQLite database rather than starting with an empty PostgreSQL database, follow the [data migration steps](#migrating-existing-sqlite-data) after confirming the destination.

## Checks after deployment

- Confirm the Render build installs `requirements.txt` successfully.
- Open the service URL and check login and the dashboard.
- Confirm the service uses PostgreSQL through its configured `DATABASE_URL`.
- Review Render logs for startup or database errors.

## First-deploy checklist

- [ ] Provision PostgreSQL and set the Render service's `DATABASE_URL` to its internal URL.
- [ ] Set a unique production `SECRET_KEY` and `FLASK_ENV=production`.
- [ ] Set any optional integration credentials required by the deployment.
- [ ] Review migration status and apply the required SQL migrations explicitly.
- [ ] For an existing SQLite installation, verify the source file and PostgreSQL destination, then run the data migration helper.
- [ ] Build with `pip install -r requirements.txt` and start with `gunicorn app:app`.
- [ ] Confirm the service starts, login/dashboard load, and data persists in PostgreSQL.

`ALLOW_DB_INIT` is not read by the current `config.py` or `app.py`; it is not a current deployment setting.
