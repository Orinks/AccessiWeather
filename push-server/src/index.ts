import { chunk, contentHash, isActive, sha256Hex, buildPayload, type NwsAlert } from "./alerts";
import { isDeadToken, isProviderTokenError, sendPush, signProviderToken, type ApnsEnv } from "./apns";
import { activeAlerts, zonesFor } from "./nws";
import { planNotifications, type LocationRow, type SentRow } from "./plan";
import { round4, validateRegistration } from "./register";

export interface Env extends ApnsEnv {
  DB: D1Database;
  NWS_USER_AGENT: string;
}

const ZONES_PER_REQUEST = 25;
const MAX_ALERT_REQUESTS = 20;
const MAX_SENDS_PER_RUN = 25;
const PROVIDER_TOKEN_TTL_MS = 45 * 60_000;
const SENT_RETENTION_MS = 7 * 86_400_000;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/health") return new Response("ok");
      if (url.pathname === "/v1/devices" && request.method === "POST") return await register(request, env);
      const match = url.pathname.match(/^\/v1\/devices\/([0-9a-fA-F]{64,200})$/);
      if (match && request.method === "DELETE") {
        await env.DB.batch(deleteDevice(env.DB, match[1].toLowerCase()));
        return new Response(null, { status: 204 });
      }
      return json({ error: "not found" }, 404);
    } catch (error) {
      console.error("request failed", error);
      return json({ error: "temporarily unavailable" }, 503);
    }
  },

  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runCheck(env, Date.now()));
  },
};

function deleteDevice(db: D1Database, token: string): D1PreparedStatement[] {
  return ["devices", "locations", "sent"].map((table) =>
    db.prepare(`DELETE FROM ${table} WHERE token = ?`).bind(token),
  );
}

async function register(request: Request, env: Env): Promise<Response> {
  if (Number(request.headers.get("content-length") ?? 0) > 32_768) return json({ error: "too large" }, 413);
  const registration = validateRegistration(await request.json().catch(() => null));
  if (typeof registration === "string") return json({ error: registration }, 400);
  const db = env.DB;
  const { token } = registration;
  if (!registration.enabled || registration.locations.length === 0) {
    await db.batch(deleteDevice(db, token));
    return json({ registered: false });
  }
  const { results: existing } = await db
    .prepare("SELECT location_id, latitude, longitude, zones, baselined FROM locations WHERE token = ?")
    .bind(token)
    .all<{ location_id: string; latitude: number; longitude: number; zones: string; baselined: number }>();
  const previous = new Map(existing.map((row) => [row.location_id, row]));
  const now = Date.now();
  const rows = [];
  for (const location of registration.locations) {
    const latitude = round4(location.latitude);
    const longitude = round4(location.longitude);
    const prior = previous.get(location.id);
    const unchanged = prior && prior.latitude === latitude && prior.longitude === longitude;
    const zones = unchanged ? prior.zones : (await zonesFor(env.NWS_USER_AGENT, latitude, longitude)).join(",");
    rows.push({ ...location, latitude, longitude, zones, baselined: unchanged ? prior.baselined : 0 });
  }
  await db.batch([
    db
      .prepare(
        "INSERT INTO devices (token, environment, severities, notify_unknown, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5, ?5) " +
          "ON CONFLICT(token) DO UPDATE SET environment = ?2, severities = ?3, notify_unknown = ?4, updated_at = ?5",
      )
      .bind(token, registration.environment, registration.severities.join(","), registration.notifyUnknown ? 1 : 0, now),
    db.prepare("DELETE FROM locations WHERE token = ?").bind(token),
    ...rows.map((row) =>
      db
        .prepare("INSERT INTO locations (token, location_id, name, latitude, longitude, zones, baselined) VALUES (?, ?, ?, ?, ?, ?, ?)")
        .bind(token, row.id, row.name, row.latitude, row.longitude, row.zones, row.baselined),
    ),
  ]);
  return json({ registered: true, locations: rows.map((row) => ({ id: row.id, covered: row.zones !== "" })) });
}

async function providerToken(env: Env, now: number): Promise<string> {
  const cached = await env.DB.prepare("SELECT value, updated_at FROM meta WHERE key = 'apns_jwt'").first<{ value: string; updated_at: number }>();
  if (cached && now - cached.updated_at < PROVIDER_TOKEN_TTL_MS) return cached.value;
  const token = await signProviderToken(env, Math.floor(now / 1000));
  await env.DB.prepare("INSERT INTO meta (key, value, updated_at) VALUES ('apns_jwt', ?1, ?2) ON CONFLICT(key) DO UPDATE SET value = ?1, updated_at = ?2")
    .bind(token, now)
    .run();
  return token;
}

function expiration(alert: NwsAlert, now: number): number {
  const end = Date.parse(alert.ends ?? alert.expires ?? "");
  return Math.floor((Number.isNaN(end) ? now + 6 * 3_600_000 : end) / 1000);
}

export async function runCheck(env: Env, now: number): Promise<void> {
  const db = env.DB;
  const { results: locations } = await db
    .prepare(
      "SELECT l.token, l.location_id, l.name, l.zones, l.baselined, d.environment, d.severities, d.notify_unknown " +
        "FROM locations l JOIN devices d ON d.token = l.token WHERE l.zones != '' ORDER BY l.token, l.rowid",
    )
    .all<LocationRow>();
  if (locations.length === 0) return;

  const zones = [...new Set(locations.flatMap((l) => l.zones.split(",")))];
  const chunks = chunk(zones, ZONES_PER_REQUEST);
  if (chunks.length > MAX_ALERT_REQUESTS) console.warn(`checking ${MAX_ALERT_REQUESTS} of ${chunks.length} zone batches`);
  const failedZones = new Set<string>(chunks.slice(MAX_ALERT_REQUESTS).flat());
  const checked = chunks.slice(0, MAX_ALERT_REQUESTS);
  const results = await Promise.allSettled(checked.map((c) => activeAlerts(env.NWS_USER_AGENT, c)));
  const alerts = new Map<string, NwsAlert>();
  results.forEach((result, i) => {
    if (result.status === "fulfilled") for (const alert of result.value) alerts.set(alert.id, alert);
    else {
      console.error("NWS alerts failed", result.reason);
      for (const zone of checked[i]) failedZones.add(zone);
    }
  });

  const byZone = new Map<string, NwsAlert[]>();
  for (const alert of alerts.values()) {
    if (!isActive(alert, now)) continue;
    for (const zone of alert.ugc) {
      const list = byZone.get(zone) ?? [];
      list.push(alert);
      byZone.set(zone, list);
    }
  }
  const hashes = new Map(await Promise.all([...alerts.values()].map(async (a) => [a.id, await contentHash(a)] as const)));
  const { results: sentRows } = await db.prepare("SELECT token, alert_key, content_hash, severity FROM sent").all<SentRow>();
  const sent = new Map(sentRows.map((row) => [`${row.token}|${row.alert_key}`, row]));
  const plan = planNotifications(locations, byZone, sent, hashes, failedZones);

  const upsertSent = (r: { token: string; key: string; hash: string; severity: number }) =>
    db
      .prepare(
        "INSERT INTO sent (token, alert_key, content_hash, severity, sent_at) VALUES (?1, ?2, ?3, ?4, ?5) " +
          "ON CONFLICT(token, alert_key) DO UPDATE SET content_hash = ?3, severity = ?4, sent_at = ?5",
      )
      .bind(r.token, r.key, r.hash, r.severity, now);
  const writes: D1PreparedStatement[] = [
    ...plan.baselineRecords.map(upsertSent),
    ...plan.baselined.map((l) =>
      db.prepare("UPDATE locations SET baselined = 1 WHERE token = ? AND location_id = ?").bind(l.token, l.location_id),
    ),
  ];

  const sends = plan.sends.slice(0, MAX_SENDS_PER_RUN);
  if (sends.length > 0) {
    const jwt = await providerToken(env, now);
    const dead = new Set<string>();
    let resetProviderToken = false;
    await Promise.all(
      sends.map(async (send) => {
        const result = await sendPush(
          env,
          jwt,
          { token: send.token, environment: send.location.environment },
          buildPayload(send.kind, send.alert, { id: send.location.location_id, name: send.location.name }),
          { collapseId: (await sha256Hex(send.key)).slice(0, 32), expiration: expiration(send.alert, now) },
        );
        if (result.status === 200) writes.push(upsertSent(send));
        else if (isDeadToken(result)) dead.add(send.token);
        else {
          if (isProviderTokenError(result)) resetProviderToken = true;
          console.error("APNs send failed", result.status, result.reason);
        }
      }),
    );
    for (const token of dead) writes.push(...deleteDevice(db, token));
    if (resetProviderToken) writes.push(db.prepare("DELETE FROM meta WHERE key = 'apns_jwt'"));
  }
  if (new Date(now).getUTCMinutes() === 0) {
    writes.push(db.prepare("DELETE FROM sent WHERE sent_at < ?").bind(now - SENT_RETENTION_MS));
  }
  if (writes.length > 0) await db.batch(writes);
}
