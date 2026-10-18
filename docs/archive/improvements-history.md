# Improvements history

Historical notes on completed security and architecture work. This is context, not an implementation or deployment manual.

- PIN storage was moved to bcrypt hashing; CSRF protection and Flask-Limiter rate limits were added for relevant routes.
- Shared validation, service modules, and automated tests were introduced as the application grew.
- Earlier deployment and schema fixes addressed missing dependencies and database-column drift.
- Old checklists and plans included proposed modular architecture and production follow-up items. Their paths, status, and instructions may no longer match the current repository; use the current code and [deployment guide](../deployment.md).
