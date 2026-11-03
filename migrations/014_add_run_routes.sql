-- Migration 014: Add run_routes table for GPS route storage
CREATE TABLE IF NOT EXISTS run_routes (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    route_json TEXT NOT NULL,
    total_distance_km REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_run_routes_run_id ON run_routes(run_id);
