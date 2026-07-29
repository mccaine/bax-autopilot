-- Initial schema. The coder agent extends this with the app's real tables
-- (auto-run by the postgres container on first boot).
CREATE TABLE IF NOT EXISTS _autopilot_health (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO _autopilot_health DEFAULT VALUES;
