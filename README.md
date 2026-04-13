# 🏃 RunRush

> **Your Personal Running Intelligence Platform** — Track runs, build streaks, earn badges, and compete with your community.

---

## 📖 About

RunRush is a full-stack web application for everyday runners who want smart analytics and social motivation — **without GPS hardware or expensive subscriptions**. Log a run in seconds, get a personalized AI insight, and watch your streaks grow.

---

## ✨ Features

| Category | Features |
|---|---|
| **Tracking** | Log runs (date, distance, time, type, notes) · Auto pace & calorie calc · Personal bests (5K / 10K) |
| **Analytics** | 365-day activity heatmap · Run-type breakdown · Monthly & weekly stats |
| **Motivation** | AI run insights · Streak tracker · Badge system with confetti · Weekly goal progress |
| **Social** | Follow/unfollow runners · Social feed · Smart Discover ranking · All-time & weekly leaderboard |
| **Communication** | Weekly HTML email summary (opt-in) via Resend API · @mention friends in run notes |
| **Offline** | Log runs offline → SHA-256 verified auto-sync on reconnect |
| **Settings** | Dark/light mode · Display name · Weight & height · PIN change · CSV export |
| **Admin** | User management · Block/unblock · Role assignment · Activity logs · Admin notes |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML5, CSS3 (glassmorphism), Vanilla JavaScript |
| Backend | Python 3 · Flask 3.0 |
| Database (dev) | SQLite (`runs.db`) |
| Database (prod) | PostgreSQL 16 |
| Auth | Flask session · 4-digit PIN · `hmac.compare_digest` |
| Email | Resend API (via Python `urllib`) |
| Offline Sync | `localStorage` + custom `sync-engine.js` |
| Hosting | Render (Web Service + PostgreSQL) |
| WSGI | Gunicorn |

---

## 🗄️ Database Tables

| Table | Purpose |
|---|---|
| `users` | Accounts, profile, theme, role, status |
| `runs` | Individual run entries with computed stats |
| `user_stats` | Cached totals: total km, current & best streak |
| `badges` | Badge catalog (criteria definitions) |
| `user_badges` | Badges earned per user |
| `friends` | Directional follow relationships |
| `edit_history` | Field-level audit log of run edits |
| `activity_logs` | App-wide action audit trail |
| `admin_notes` | Moderator notes on users |

---

## 🚀 Quick Start (Local)

### 1. Clone & install

```bash
git clone https://github.com/your-username/runrush.git
cd runrush
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) — SQLite is used automatically, no database setup needed.

### 3. Environment variables (optional)

Create a `.env` file (see `.env.example`):

```env
DATABASE_URL=sqlite:///runs.db   # or a postgresql:// URL for production
ADMIN_USER_ID=1                  # user ID that gets admin privileges
RESEND_API_KEY=re_...            # for weekly email summaries
RESEND_FROM_EMAIL=RunRush <noreply@yourdomain.com>
```

---

## ☁️ Deploy to Render

1. Create a **PostgreSQL** database on Render → copy the Internal Database URL
2. Create a **Web Service** → connect your GitHub repo
3. Set environment variables:

| Key | Value |
|---|---|
| `DATABASE_URL` | Internal PostgreSQL URL from Render |
| `ADMIN_USER_ID` | `1` |
| `FLASK_ENV` | `production` |

4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`

See [`RENDER_SETUP.md`](RENDER_SETUP.md) for full instructions.

### Migrate existing data to PostgreSQL

```bash
set DATABASE_URL=postgresql://user:pass@host:5432/dbname
python migrate_to_pg.py
```

---

## 📁 Project Structure

```
runrush/
├── app.py                  # All routes & business logic
├── db.py                   # SQLite / PostgreSQL abstraction layer
├── migrate_to_pg.py        # Data migration script
├── requirements.txt
├── runs.db                 # Local SQLite database (gitignored in prod)
├── static/
│   ├── css/                # Stylesheets
│   └── js/                 # sync-engine.js, offline-storage.js, etc.
├── templates/              # Jinja2 HTML templates
│   ├── index.html          # Dashboard
│   ├── social.html         # Social feed
│   ├── leaderboard.html
│   ├── settings.html
│   ├── login.html / register.html / onboarding.html
│   └── ...
└── migrations/
    └── add_badges_system.py
```

---

## 🧠 Key Business Logic

### Streak Calculation
Unique run dates fetched and sorted. Current streak walks backward from today; best streak is the longest consecutive chain in history. Recalculated from scratch on every add/delete.

### AI Run Insight
Compares today's pace and distance against the user's last 30 days of runs. Returns a personalized motivational message — no external API, pure Python.

### Social Score (Discover Runners)
```
Social Score = (30-day KM × 2) + (30-day Run Count × 5) + (Current Streak × 10)
```
Surfaces the most *currently active* runners, not just all-time leaders.

### Offline Sync
Runs saved to `localStorage` offline. On reconnect, each run is sent with a SHA-256 hash of `date+distance+time` for server-side integrity verification. Duplicates are detected and skipped (HTTP 409).

### Edit Lock
Runs are editable within 24 hours of logging (`created_at`). Admins/moderators bypass the lock. All field changes are recorded in `edit_history`.

---

## 🔒 Authentication

- Username + numeric PIN (≥ 4 digits)
- Flask server-side session
- PIN comparison via `hmac.compare_digest()` (timing-safe)
- Role system: `user` → `moderator` → `admin` (also via `ADMIN_USER_ID` env var)

---

## 📦 Dependencies

```
Flask==3.0.0
python-dotenv==1.0.0
gunicorn
psycopg2-binary
```

---

## 📄 License

MIT — feel free to use, modify, and distribute.

---

<p align="center">Built with ❤️ and Python · RunRush © 2026</p>
