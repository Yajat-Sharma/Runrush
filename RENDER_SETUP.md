# Deploying RunRush on Render with PostgreSQL

## 1. Create a Free PostgreSQL Database

1. Go to [render.com](https://render.com) → **Dashboard** → **New +** → **PostgreSQL**
2. Fill in:
   - **Name**: `runrush-db`
   - **Region**: Pick the closest one (e.g., Oregon)
   - **PostgreSQL Version**: 16
   - **Instance Type**: **Free**
3. Click **Create Database**
4. Wait for it to provision (~30 seconds)

## 2. Get the Database URL

On the database page, find:

- **Internal Database URL** — use this for your web service (same Render network, faster)
- **External Database URL** — use this for local migration scripts

Copy the **Internal Database URL**. It looks like:

```
postgresql://runrush_db_user:abc123@dpg-xyz.internal:5432/runrush_db
```

## 3. Deploy the Flask App as a Web Service

1. **New +** → **Web Service** → Connect your GitHub repo
2. Configure:
   - **Name**: `runrush`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
3. **Environment Variables** → Add:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | *(paste the Internal Database URL)* |
| `ADMIN_USER_ID` | `1` |
| `FLASK_ENV` | `production` |
| `ALLOW_DB_INIT` | `true` |

4. Click **Create Web Service**

## 4. Migrate Existing Data

If you have existing data in `runs.db` that you want to move to PostgreSQL:

1. Copy the **External Database URL** from the Render dashboard
2. Run locally:

```bash
set DATABASE_URL=postgresql://user:pass@host:5432/dbname
python migrate_to_pg.py
```

> **Note**: Use the **External** URL for this step since you're connecting from your local machine. The Internal URL only works within Render's network.

## 5. Common Gotchas

### Free Tier Sleep
Render's free web services spin down after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. Consider upgrading to a paid plan for always-on.

### Free DB Expiry
Free PostgreSQL databases on Render expire after **90 days**. You'll get email warnings. Before expiry, upgrade or export your data.

### Connection Limits
Free tier has a limit of **97 concurrent connections**. This is plenty for a small app, but don't leave connections open — always call `conn.close()`.

### SSL Mode
Render PostgreSQL requires SSL. `psycopg2` handles this automatically with the `postgresql://` URL format — no extra config needed.

### `postgres://` vs `postgresql://`
Render gives you a `postgres://` URL, but `psycopg2` needs `postgresql://`. The `db.py` module handles this conversion automatically.
