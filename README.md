<div align="center">
  <img src="static/icons/icon-512.png" alt="RunRush Logo" width="150" height="150" />
  <h1>RunRush</h1>
  <p><strong>Track. Improve. Repeat.</strong></p>
  <p>A modern, offline-first Progressive Web Application (PWA) with Live GPS tracking, audio voice coaching, AI companion (Rumi), 1v1 and FFA Friendly Challenges, workload analytics (ACWR), and enterprise-grade security.</p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Flask-3.1.3-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask" />
    <img src="https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?style=flat-square&logo=javascript&logoColor=black" alt="JavaScript" />
    <img src="https://img.shields.io/badge/PWA-Ready-5A0FC8?style=flat-square&logo=pwa&logoColor=white" alt="PWA" />
    <img src="https://img.shields.io/badge/PostgreSQL-Ready-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
    <img src="https://img.shields.io/badge/Security-Strict_CSP-00f2fe?style=flat-square&logo=auth0&logoColor=black" alt="Strict CSP" />
    <a href="https://github.com/Yajat-Sharma/Runrush/actions/workflows/python-app.yml"><img src="https://github.com/Yajat-Sharma/Runrush/actions/workflows/python-app.yml/badge.svg?branch=main" alt="RunRush CI" /></a>
  </p>
</div>

<p align="center">
  <a href="https://runrush.onrender.com/login"><strong>▶ Open the RunRush live demo</strong></a>
</p>

---

## 🏃 About RunRush

RunRush is an offline-first running ecosystem engineered for runners who demand rich real-time tracking, deep training insights, and social motivation. Built as a high-performance Progressive Web Application (PWA), RunRush seamlessly transitions between connected and offline environments, enabling uninterrupted activity recording, instant sync upon reconnection, and zero-compromise security.

From in-ear live audio split coaching and generative trail artwork to multi-runner Free-For-All challenges and conversational AI coaching, RunRush bridges the gap between everyday training and elite performance tracking.

---

## ✨ Features

### 📍 Live GPS Tracking & Audio Voice Coach
- **Real-Time GPS Route Mapping:** High-frequency location tracking with self-hosted Leaflet maps, live polyline rendering, and start/finish badges.
- **In-Ear Voice Coach:** Real-time audio announcements delivered directly to headphones via the Web Speech Synthesis API, announcing split paces, elapsed times, and motivational milestones.
- **Live Split Tracking:** Automated split calculation (per kilometer/mile) with visual split markers and dynamic pace color-coding.
- **Screen Wake Lock API:** Keeps the display active and prevents mobile sleep during active tracking (`navigator.wakeLock`).
- **Post-Run Route Review Drawer:** Interactive post-run modal featuring comprehensive pace splits, elevation metrics, and map exploration.
- **Trail Share Cards & Artwork:**
  - Continuous glowing trail art with customizable shape frames (**Thumb**, **Heart**, **Square**, **Oval**, or authentic GPS coordinates).
  - Social export presets: **Story** (9:16, 1080×1920) and **Post** (4:5, 1080×1350).
  - Transparent trail sticker export and dark charcoal canvas styling for social media sharing.

### ⚔️ Friendly Challenges (1v1 Duels & FFA Group Showdown)
- **1v1 Head-to-Head Duels:** Challenge friends to direct distance, pace, or elevation showdowns.
- **FFA Group Challenges (V2):** Multi-runner Free-For-All competitions supporting up to 10 runners per challenge.
- **Versatile Goal Formats:** Most Distance (km), Fastest Pace, Most Elevation, or Target Distance sprint goals.
- **Configurable Timeframes:** 24-hour sprints, 3-day showdowns, 7-day endurance tests, or weekend warrior battles.
- **Live Scoreboard & Shared Gold:** Real-time progress tracking, invitations inbox with unread badges, podium medals, and Shared Gold tie-breaker handling.
- **Anti-Cheat & Concurrency Guards:** PostgreSQL transaction isolation, strict run eligibility validation, and duplicate prevention.

### 🤖 AI-Powered Running Intelligence
- **Rumi AI Companion:** Dedicated conversational running coach grounded in deterministic database retrieval, analyzing your personal PRs, recent runs, streaks, and training volume.
- **AI Screenshot Import:** Upload activity screenshots from Garmin, Strava, Apple Fitness, or Nike Run Club; the Google Gemini API (`google-genai`) parses distance, duration, pace, and dates with interactive preview and duplicate detection.
- **AI Run Insights:** Context-aware run debriefs and personalized recovery guidance generated after every run.
- **Voice Quick Log:** Hands-free run logging powered by the Web Speech Recognition API ("Ran 5 kilometers in 25 minutes feeling great").
- **Per-User ML Prediction:** `GradientBoostingRegressor` predicts upcoming run distances from personal activity history, with a weighted-average fallback for newer runners.

### 📊 Training Analytics & Gamification
- **Training Load (ACWR):** Acute:Chronic Workload Ratio comparing your 7-day acute load to your 28-day chronic baseline, complete with injury prevention zone badges (Detraining / Sweet Spot / Caution / High Spike) and an 8-week interactive chart.
- **Streaks, Badges & Ranks:** Distance-based runner ranks, streak tracking, weekly distance goals, and milestone achievement badges.
- **Leaderboards & Community Feed:** Global and qualified leaderboards, runner following, run likes, and public runner profiles.
- **Automated Monthly Digest:** Monthly performance summaries delivered via in-app reports and automated email digests.

### 📱 PWA & Offline-First Architecture
- **Installable PWA:** Add RunRush to Android (Chrome), iOS (Safari), or Desktop (Chrome/Edge) with native-like performance.
- **Offline Run Logging:** Queue runs safely in IndexedDB when network connectivity is lost.
- **Background Synchronization:** Synchronize queued activities automatically when connection returns, complete with SHA-256 payload hashing and duplicate rejection.
- **Service Worker Caching (v9):** Pre-caches application shell, icons, fonts, and vendor libraries for instant offline loading.

### 🎨 Modern Design System & User Experience
- **Dark Radial Visuals:** High-contrast dark surfaces with glowing cyan accents (`#00f2fe`), subtle borders, and eyebrow badge typography.
- **Runner Spotlight Hero:** Dynamic hero banner showcasing weekly progress, active streaks, and quick launch triggers.
- **Rainbow Expandable Quick Action FAB:** Multi-tier floating action button providing instant access to Live Run, Voice Quick Log, Manual Entry, and Rumi AI.
- **Release Updates Modal:** "What's New" popup displayed on login for 5 days following major releases.
- **Customizable Profiles:** Profile photo upload, avatar icon selector with live preview, and BMI health metrics.

### 🔒 Enterprise-Grade Security & Hardening
- **Strict Content Security Policy (CSP):** Zero inline event handlers (`on*`), 100% migrated to a declarative `data-action` delegation engine via `actions.js`.
- **Dynamic CSP Enforcement:** Seamless toggle via `CSP_ENFORCE` (Report-Only vs. Enforce).
- **Cryptographic Nonces:** Nonces generated on all inline `<script>` and `<style>` tags via Flask-Talisman.
- **Self-Hosted Vendor Assets & SRI:** `unpkg.com` eliminated; Leaflet 1.9.4 and Chart.js 4.4.1 self-hosted locally in `static/vendor/` with strict SHA-384 Subresource Integrity (SRI) hashes on all remaining CDNs.
- **Robust Session Security:** Bcrypt PIN hashing, Flask-WTF CSRF with automatic refresh retries, Flask-Limiter rate limiting, and Werkzeug ProxyFix.

---

## 🏗️ Architecture & Data Flow

### PWA & Offline-First Sync Flow

```mermaid
flowchart TD
    A[RunRush PWA] --> B{Network Available?}
    B -->|Yes| C[Flask Backend]
    B -->|No| D[(IndexedDB Storage)]
    D --> E[Offline Run Queue]
    E --> F{Connection Restored?}
    F -->|Yes| G[Sync Engine JS]
    G -->|Hash validation & duplicate check| C
    C --> H[(PostgreSQL / SQLite)]
    H --> I[Dashboard UI]
```

### End-to-End System Architecture

```mermaid
flowchart LR
    subgraph Client [Browser / PWA Client]
        UI[Design System UI & Modals]
        SW[Service Worker v9]
        IDB[(IndexedDB Queue)]
        LiveGPS[Live GPS Tracker & Voice Coach]
        Actions[Delegated Actions Engine]
    end

    subgraph Server [Flask Application Server]
        Flask[Flask App & Talisman CSP]
        Auth[Auth & Bcrypt Security]
        Challenges[Friendly Challenges V2 Service]
        Rumi[Rumi AI Service]
        ML[GradientBoosting Predictor]
        Reports[Monthly Summary Delivery]
    end

    subgraph External [External Services & APIs]
        Gemini[Google Gemini API]
        Push[Web Push Service]
        Tiles[OpenStreetMap Tiles]
    end

    subgraph Storage [Persistent Storage]
        DB[(PostgreSQL / SQLite)]
    end

    UI <--> Actions
    UI <--> LiveGPS
    UI <--> SW
    SW -.-> IDB
    SW <--> Flask
    Flask <--> Auth
    Flask <--> Challenges
    Flask <--> Rumi
    Flask <--> ML
    Flask <--> Reports
    Flask <--> DB
    Rumi <--> Gemini
    Flask <--> Push
    LiveGPS <--> Tiles
```

---

## 🛠️ Tech Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.11+, Flask 3.1.3 | Core WSGI application, routing, and blueprints |
| **Frontend** | HTML5, CSS3, Vanilla ES6+ JS, Bootstrap 5 | Reactive UI without heavy SPA runtime overhead |
| **Design System** | Custom CSS Design Tokens | Dark radial card surfaces, cyan glowing accents (`#00f2fe`) |
| **Mapping & GPS** | Leaflet 1.9.4 (Self-Hosted), Geolocation API | Live run trail tracking, split markers, route map review |
| **Audio & Speech** | Web Speech API (Synthesis & Recognition) | Live Voice Coach audio split cues & Voice Quick Log |
| **Offline & PWA** | IndexedDB, Web Storage, Service Worker (v9) | Offline-first run queuing and background sync engine |
| **Data Visualization** | Chart.js 4.4.1 (Self-Hosted) | ACWR workload charts, pace distribution, activity heatmaps |
| **Database** | PostgreSQL (Production), SQLite (Dev) | Relational data persistence with Yoyo migrations (001–016) |
| **AI & LLM** | Google Gemini API (`google-genai`), Pillow | Rumi running coach companion & OCR screenshot import |
| **Machine Learning** | scikit-learn, pandas, NumPy | Per-user `GradientBoostingRegressor` run distance predictions |
| **Security & Headers** | Flask-Talisman, bcrypt, Flask-WTF, Flask-Limiter | Strict CSP with nonces, delegated actions, CSRF, and rate limiting |
| **Notifications** | Web Push API (`pywebpush`), Service Worker Push | Browser background push notifications and invitations |
| **Testing & CI** | pytest, GitHub Actions | 660+ unit, integration, concurrency, and security lint tests |
| **Deployment** | Gunicorn on Render | Production-ready WSGI container deployment |

---

## 📂 Project Structure

```text
RunRush/
├── .github/workflows/          # GitHub Actions CI/CD workflows
│   └── python-app.yml
├── blueprints/                 # Modular Flask blueprints
│   └── api/v1/
├── docs/                       # Project and operational documentation
│   ├── archive/                # Historical audits and architectural investigations
│   ├── deployment.md           # Render & PostgreSQL deployment guide
│   ├── developer-guide.md      # Engineering standards and developer guide
│   └── project-summary.md      # System overview and design rationale
├── migrations/                 # Schema migrations (001 to 016)
│   ├── 001_initial_schema.sql
│   ├── 002_seed_badges_challenges.sql
│   ├── 003_add_user_onboarding_fields.sql
│   ├── 004_add_monthly_goals.sql
│   ├── 005_add_profile_emoji.sql
│   ├── 006_add_notifications.sql
│   ├── 007_add_monthly_summary_deliveries.sql
│   ├── 008_add_run_likes.sql
│   ├── 009_drop_user_pets.sql
│   ├── 010_add_web_push_subscriptions.sql
│   ├── 011_add_monthly_report_views.sql
│   ├── 012_add_monthly_report_preferences.sql
│   ├── 013_auto_enable_google_user_notifications.sql
│   ├── 014_add_run_routes.sql
│   ├── 015_add_friendly_challenges.sql
│   ├── 016_add_group_challenges.sql
│   └── README.md
├── models/                     # Data models
│   └── user.py
├── scripts/                    # Maintenance, data migration, and QA scripts
│   ├── migrate_to_pg.py
│   ├── run_visual_qa.py
│   └── smoke_script.py
├── services/                   # Business logic and domain services
│   ├── auth_service.py
│   ├── badge_service.py
│   ├── challenge_service.py
│   ├── friendly_challenge_service.py  # V1 & V2 1v1 and FFA Challenges engine
│   ├── goal_service.py
│   ├── monthly_report_service.py
│   ├── monthly_summary_delivery.py
│   ├── push_service.py                # Web Push notification dispatcher
│   ├── rumi_service.py                # Rumi AI running companion service
│   ├── run_service.py
│   ├── social_service.py
│   ├── training_load.py               # ACWR training load calculations
│   └── weather_service.py
├── static/
│   ├── css/
│   │   ├── design-system/tokens.css   # Dark radial tokens, cyan accents
│   │   ├── auth.css
│   │   ├── challenges.css
│   │   └── landing.css
│   ├── js/
│   │   ├── actions.js                 # CSP event delegation dispatcher (RR_ACTIONS)
│   │   ├── challenges.js              # Friendly Challenges frontend engine
│   │   ├── live_run_tracker.js        # GPS tracking, voice coach, trail artwork
│   │   ├── offline-storage.js         # IndexedDB storage wrapper
│   │   ├── push-notifications.js      # Web push subscription manager
│   │   ├── pwa-register.js            # Service worker lifecycle & What's New modal
│   │   ├── rumi_chat.js               # Rumi conversational AI UI
│   │   ├── sync-engine.js             # Offline-to-server sync engine
│   │   └── voice_quick_log.js         # Speech-to-text run entry
│   ├── vendor/                        # Self-hosted libraries (SRI pinned)
│   │   ├── chartjs/chart.umd.js
│   │   └── leaflet/
│   ├── manifest.json                  # PWA Web App Manifest
│   └── sw.js                          # Service Worker v9
├── templates/
│   ├── components/
│   │   ├── challenges_section.html    # Friendly challenges board & scoreboard
│   │   └── profile_content.html
│   ├── partials/
│   │   ├── _live_run_modal.html       # Live GPS run tracking modal
│   │   ├── _quick_actions_fab.html    # Rainbow expandable FAB
│   │   ├── _rumi_chat_modal.html      # Rumi AI companion chat drawer
│   │   ├── _trail_share_modal.html    # Continuous trail artwork share modal
│   │   └── _whats_new_modal.html      # Major release update popup
│   ├── index.html                     # Core 4-tab dashboard
│   ├── login.html
│   └── settings.html
├── tests/                             # Comprehensive automated test suite (660+ tests)
│   ├── test_challenges_group_*.py     # FFA Group challenge test suites
│   ├── test_csp_lint.py               # Zero inline event handler regression guard
│   ├── test_live_run_splits.py        # Split calculations and audio triggers
│   ├── test_rumi.py                   # Rumi deterministic retrieval tests
│   ├── test_security_headers.py       # Strict CSP and Talisman headers
│   ├── test_trail_shapes.py           # Trail shape frame transformation tests
│   └── test_voice_coach.py            # Audio voice coach cue tests
├── utils/                             # Shared utilities (validators, decorators, rate limits)
├── .env.example                       # Environment configuration template
├── app.py                             # Main Flask application entrypoint
├── config.py                          # Multi-environment configuration
├── db.py                              # Database connection manager (PG/SQLite)
├── ml_predictor.py                    # scikit-learn run prediction model
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Testing and development dependencies
├── schema.sql                         # Baseline SQLite schema
├── REPORT.md                          # Detailed CSP hardening & security report
└── README.md
```

---

## 📱 PWA Installation

RunRush can be installed directly onto any supported device for a full-screen, native application experience:

- **Android (Chrome):** Visit the application URL and tap **Install App** in the banner or select **Add to Home screen** from the browser menu.
- **iOS (Safari):** Tap the **Share** button, scroll down, and select **Add to Home Screen**.
- **Desktop (Chrome / Edge):** Click the **Install** icon on the right side of the URL address bar.

---

## 💻 Local Development

### 1. Prerequisites
- Python 3.11 or higher
- Git

### 2. Clone & Setup Virtual Environment
```bash
git clone https://github.com/Yajat-Sharma/Runrush.git
cd Runrush

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure your settings:
```bash
cp .env.example .env
```

Key environment options in `.env`:
```ini
FLASK_ENV=development
SECRET_KEY=your-secure-random-secret-key

# Database (defaults to local runs.db SQLite file if unset)
# DATABASE_URL=postgresql://user:password@localhost:5432/runrush

# AI & LLM (optional for Rumi AI & screenshot OCR)
GEMINI_API_KEY=your_gemini_api_key

# Security & CSP
CSP_ENFORCE=0        # 0 = Report-Only (recommended for dev), 1 = Strict Enforce
FORCE_HTTPS=0        # Set to 0 for local HTTP development

# Web Push Notifications (optional)
VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
VAPID_CLAIM_EMAIL=mailto:admin@runrush.app
```

### 4. Run the Development Server
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000`.

---

## 🧪 Testing & Quality Assurance

RunRush maintains an extensive test suite of **660+ automated tests** verifying unit logic, database migrations, challenge concurrency, AI retrieval, and CSP template compliance.

Run all tests with:
```bash
pytest -q
```

Target specific test domains:
```bash
# Security & CSP template linting
pytest tests/test_security_headers.py tests/test_csp_lint.py

# Live Run Tracker, Splits & Voice Coach
pytest tests/test_live_run_splits.py tests/test_voice_coach.py tests/test_trail_shapes.py

# Friendly Challenges (1v1 & FFA Group Showdown)
pytest tests/test_friendly_challenges.py tests/test_challenges_group_*.py

# Rumi AI Companion
pytest tests/test_rumi.py
```

---

## 🌍 Production Deployment

RunRush is designed for zero-configuration containerized deployment on platforms such as **Render**, **Railway**, or **Fly.io** using Gunicorn and managed PostgreSQL.

1. Create a managed **PostgreSQL** database.
2. Configure environment variables (`DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`, `CSP_ENFORCE=1`, `FORCE_HTTPS=1`).
3. Migrate your SQLite database or initialize the PostgreSQL schema:
   ```bash
   python scripts/migrate_to_pg.py
   ```
4. Set the start command:
   ```bash
   gunicorn app:app --config gunicorn.conf.py
   ```

Refer to the [Render Deployment Guide](docs/deployment.md) for full deployment instructions.

---

## 🔒 Security & Reliability

- **Strict Content Security Policy (CSP):** Zero inline scripts/handlers; nonces required for inline styles/scripts; self-hosted Leaflet and Chart.js; pinned SRI hashes for Bootstrap and Font Awesome.
- **CSRF Token Auto-Refresh:** Single-page async flows automatically request fresh CSRF tokens if a session token expires.
- **Credential Protection:** User PINs and passwords hashed using `bcrypt` with salt rounds.
- **Rate Limiting:** Granular IP and user-based limits applied via `Flask-Limiter` on sensitive authentication and challenge routes.
- **Offline Integrity:** Queued offline submissions are authenticated and checked for duplicate hashes before transactional commit.

---

## 🗺️ Product Roadmap

### ✅ Completed Milestones
- [x] Core offline-first run tracking with IndexedDB queue & auto-sync
- [x] Four-tab unified dashboard (Home, Runs, Leaderboard, Analytics)
- [x] Live GPS Run Tracker with self-hosted Leaflet route maps & wake lock
- [x] In-ear Audio Voice Coach with real-time split pacing announcements
- [x] Trail Share Cards with continuous glowing trail shapes (Thumb, Heart, Square, Oval) and Story/Post formats
- [x] Friendly Challenges V1 (1v1 Duels) & V2 (FFA Group Showdown) with podium medals
- [x] Rumi conversational AI running companion with deterministic DB grounding
- [x] Strava CSV and Gemini-powered OCR screenshot import
- [x] Acute:Chronic Workload Ratio (ACWR) injury prevention analytics
- [x] Web Push Notifications and automated monthly digest reports
- [x] Complete CSP Phase 0–4 overhaul (100% inline handler elimination & dynamic enforcement toggle)
- [x] Expanded test coverage (660+ automated tests passing)

### 🚧 Future Horizons
- [ ] Direct Garmin Connect & Apple Health Cloud API sync
- [ ] Heart rate zone integration via Bluetooth Low Energy (BLE) heart rate monitors
- [ ] Custom marathon, half-marathon, and 10k adaptive training plans
- [ ] Team & club running hubs with communal mileage milestones

---

## 📚 Documentation Links

- [Deployment Guide](docs/deployment.md)
- [Developer Guide](docs/developer-guide.md)
- [CSP Hardening & Enforcement Report](REPORT.md)
- [CSP Template Inventory](CSP_INVENTORY.md)
- [Project Summary](docs/project-summary.md)
- [Archived Documentation](docs/archive/)

---

## 🤝 Contributing

Contributions are welcomed! Please follow these steps:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/amazing-feature`).
3. Run tests and linting to ensure compliance (`pytest`).
4. Commit your changes (`git commit -m "feat: add amazing feature"`).
5. Push to your branch and open a Pull Request.

<div align="center">
  <p>Built with ⚡ by <strong>Yajat Sharma</strong></p>
</div>
