CREATE TABLE IF NOT EXISTS devices (
  token TEXT PRIMARY KEY,
  environment TEXT NOT NULL,
  severities TEXT NOT NULL,
  notify_unknown INTEGER NOT NULL DEFAULT 0,
  -- comma-separated: discussion, hwo, sps, precip_start, precip_stop
  events TEXT NOT NULL DEFAULT '',
  -- the user's own Pirate Weather key, AES-GCM encrypted with KEY_ENCRYPTION_KEY
  pw_key TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- zones: comma-separated NWS UGC codes (forecast zone, county, fire zone); empty outside NWS coverage.
-- baselined: 0 until the first check records the alerts already active there without pushing them.
CREATE TABLE IF NOT EXISTS locations (
  token TEXT NOT NULL,
  location_id TEXT NOT NULL,
  name TEXT NOT NULL,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  zones TEXT NOT NULL,
  office TEXT NOT NULL DEFAULT '',
  baselined INTEGER NOT NULL DEFAULT 0,
  pw_baselined INTEGER NOT NULL DEFAULT 0,
  minutely_signature TEXT,
  PRIMARY KEY (token, location_id)
);

CREATE TABLE IF NOT EXISTS sent (
  token TEXT NOT NULL,
  alert_key TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  severity INTEGER NOT NULL,
  sent_at INTEGER NOT NULL,
  PRIMARY KEY (token, alert_key)
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

-- Last seen AFD/HWO/SPS per forecast office (JSON ProductState).
CREATE TABLE IF NOT EXISTS offices (
  office TEXT NOT NULL,
  product TEXT NOT NULL,
  state TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (office, product)
);
