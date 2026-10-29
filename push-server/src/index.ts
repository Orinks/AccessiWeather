import { buildPayload, chunk, contentHash, isActive, sha256Hex, type NwsAlert } from "./alerts";
import { isDeadToken, isProviderTokenError, sendPush, signProviderToken, type ApnsEnv } from "./apns";
import { decryptText, encryptText } from "./crypto";
import { discussionChange, hwoChange, minutelyChange, spsChange, spsEvent, type EventPush, type ProductState } from "./events";
import { activeAlerts, pirateForecast, pointInfo, productList, productText } from "./nws";
import { ARRIVAL_BASELINE, planNotifications, type LocationRow, type PlannedSend, type SentRow } from "./plan";
import { round4, validateRegistration } from "./register";

export interface Env extends ApnsEnv {
  DB: D1Database;
  NWS_USER_AGENT: string;
  KEY_ENCRYPTION_KEY: string;
}

interface Row extends LocationRow {
  office: string;
  latitude: number;
  longitude: number;
  pw_baselined: number;
  minutely_signature: string | null;
  events: string;
  pw_key: string | null;
}

interface Push {
  token: string;
  environment: string;
  payload: unknown;
  collapseKey: string;
  expiration: number;
  onSuccess?: D1PreparedStatement;
}

// Per-run budgets keep each cron invocation under the free plan's 50 subrequests.
const ZONES_PER_REQUEST = 25;
const MAX_ALERT_REQUESTS = 10;
const PIRATE_INTERVAL_MIN = 15;
const MAX_PIRATE_REQUESTS = 8;
const PRODUCT_INTERVAL_MIN = 5;
const MAX_PRODUCT_LISTS = 6;
const MAX_PRODUCT_TEXTS = 3;
const MAX_SENDS_PER_RUN = 20;
const PROVIDER_TOKEN_TTL_MS = 45 * 60_000;
const SENT_RETENTION_MS = 7 * 86_400_000;
const PRODUCT_EVENTS: { [type: string]: string } = { AFD: "discussion", HWO: "hwo", SPS: "sps" };

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
  return ["devices", "locations", "sent"].map((table) => db.prepare(`DELETE FROM ${table} WHERE token = ?`).bind(token));
}

/** Spreads periodic work across minutes. */
export function bucket(value: string, size: number): number {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
  return (hash >>> 0) % size;
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
    .prepare("SELECT location_id, latitude, longitude, zones, office, baselined, pw_baselined, minutely_signature FROM locations WHERE token = ?")
    .bind(token)
    .all<Pick<Row, "location_id" | "latitude" | "longitude" | "zones" | "office" | "baselined" | "pw_baselined" | "minutely_signature">>();
  const previous = new Map(existing.map((row) => [row.location_id, row]));
  const rows = [];
  for (const location of registration.locations) {
    const latitude = round4(location.latitude);
    const longitude = round4(location.longitude);
    const prior = previous.get(location.id);
    if (prior && prior.latitude === latitude && prior.longitude === longitude) {
      rows.push({ ...prior, id: location.id, name: location.name });
    } else {
      const point = await pointInfo(env.NWS_USER_AGENT, latitude, longitude);
      // A current location that moved notifies Extreme and Severe alerts already active where it arrived.
      const baseline = location.current ? ARRIVAL_BASELINE : 0;
      rows.push({ id: location.id, name: location.name, latitude, longitude, zones: point.zones.join(","), office: point.office, baselined: baseline, pw_baselined: baseline, minutely_signature: null });
    }
  }
  const pwKey = registration.pirateWeatherKey ? await encryptText(env.KEY_ENCRYPTION_KEY, registration.pirateWeatherKey) : null;
  const now = Date.now();
  await db.batch([
    db
      .prepare(
        "INSERT INTO devices (token, environment, severities, notify_unknown, events, pw_key, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?7) " +
          "ON CONFLICT(token) DO UPDATE SET environment = ?2, severities = ?3, notify_unknown = ?4, events = ?5, pw_key = ?6, updated_at = ?7",
      )
      .bind(token, registration.environment, registration.severities.join(","), registration.notifyUnknown ? 1 : 0, registration.events.join(","), pwKey, now),
    db.prepare("DELETE FROM locations WHERE token = ?").bind(token),
    ...rows.map((row) =>
      db
        .prepare("INSERT INTO locations (token, location_id, name, latitude, longitude, zones, office, baselined, pw_baselined, minutely_signature) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
        .bind(token, row.id, row.name, row.latitude, row.longitude, row.zones, row.office, row.baselined, row.pw_baselined, row.minutely_signature),
    ),
  ]);
  return json({ registered: true, locations: rows.map((row) => ({ id: row.id, nws: row.zones !== "", pirateWeather: pwKey !== null })) });
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

function alertExpiration(alert: NwsAlert, now: number): number {
  const end = Date.parse(alert.ends ?? alert.expires ?? "");
  return Math.floor((Number.isNaN(end) ? now + 6 * 3_600_000 : end) / 1000);
}

const hasEvent = (row: Row, name: string) => row.events.split(",").includes(name);
const wantsRain = (row: Row) => hasEvent(row, "precip_start") || hasEvent(row, "precip_stop");

export function eventPayload(event: EventPush, location: { id: string; name: string }): Record<string, unknown> {
  return {
    aps: { alert: { title: event.title, subtitle: location.name, body: event.body(location.name) }, sound: "default", "thread-id": location.id },
    locationID: location.id,
  };
}

async function hashAlerts(alerts: Iterable<NwsAlert>): Promise<Map<string, string>> {
  return new Map(await Promise.all([...alerts].map(async (a) => [a.id, await contentHash(a)] as const)));
}

export async function runCheck(env: Env, now: number): Promise<void> {
  const db = env.DB;
  const { results: rows } = await db
    .prepare(
      "SELECT l.token, l.location_id, l.name, l.zones, l.office, l.latitude, l.longitude, l.baselined, l.pw_baselined, l.minutely_signature, " +
        "d.environment, d.severities, d.notify_unknown, d.events, d.pw_key FROM locations l JOIN devices d ON d.token = l.token ORDER BY l.token, l.rowid",
    )
    .all<Row>();
  if (rows.length === 0) return;
  const minute = Math.floor(now / 60_000);
  const writes: D1PreparedStatement[] = [];
  const pushes: Push[] = [];
  const upsertSent = (r: { token: string; key: string; hash: string; severity: number }) =>
    db
      .prepare(
        "INSERT INTO sent (token, alert_key, content_hash, severity, sent_at) VALUES (?1, ?2, ?3, ?4, ?5) " +
          "ON CONFLICT(token, alert_key) DO UPDATE SET content_hash = ?3, severity = ?4, sent_at = ?5",
      )
      .bind(r.token, r.key, r.hash, r.severity, now);
  const { results: sentRows } = await db.prepare("SELECT token, alert_key, content_hash, severity FROM sent").all<SentRow>();
  const sent = new Map(sentRows.map((row) => [`${row.token}|${row.alert_key}`, row]));
  const queueAlerts = (sends: PlannedSend[]) => {
    for (const send of sends) {
      pushes.push({
        token: send.token,
        environment: send.location.environment,
        payload: buildPayload(send.kind, send.alert, { id: send.location.location_id, name: send.location.name }),
        collapseKey: send.key,
        expiration: alertExpiration(send.alert, now),
        onSuccess: upsertSent(send),
      });
    }
  };
  const queueEvent = (row: Row, event: EventPush) =>
    pushes.push({
      token: row.token,
      environment: row.environment,
      payload: eventPayload(event, { id: row.location_id, name: row.name }),
      collapseKey: `${event.kind}-${row.location_id}`,
      expiration: Math.floor(now / 1000) + 2 * 3600,
    });

  // NWS alerts, every minute, for locations NWS covers.
  const nwsRows = rows.filter((r) => r.zones !== "");
  const zones = [...new Set(nwsRows.flatMap((r) => r.zones.split(",")))];
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
    for (const zone of alert.ugc) byZone.set(zone, [...(byZone.get(zone) ?? []), alert]);
  }
  const nwsPlan = planNotifications(nwsRows, byZone, sent, await hashAlerts(alerts.values()), failedZones);
  writes.push(
    ...nwsPlan.baselineRecords.map(upsertSent),
    ...nwsPlan.baselined.map((l) => db.prepare("UPDATE locations SET baselined = 1 WHERE token = ? AND location_id = ?").bind(l.token, l.location_id)),
  );
  queueAlerts(nwsPlan.sends);

  // Pirate Weather, every 15 minutes per location, with the user's own key: alerts outside
  // NWS coverage (the app prefers NWS alerts in the US) and rain starting or stopping.
  const pirateDue = rows.filter(
    (r) => r.pw_key && (r.zones === "" || wantsRain(r)) && bucket(`${r.token}|${r.location_id}`, PIRATE_INTERVAL_MIN) === minute % PIRATE_INTERVAL_MIN,
  );
  if (pirateDue.length > MAX_PIRATE_REQUESTS) console.warn(`checking ${MAX_PIRATE_REQUESTS} of ${pirateDue.length} Pirate Weather locations`);
  const pirateRows = pirateDue.slice(0, MAX_PIRATE_REQUESTS);
  const pirate = await Promise.allSettled(
    pirateRows.map(async (r) => pirateForecast(await decryptText(env.KEY_ENCRYPTION_KEY, r.pw_key!), r.latitude, r.longitude)),
  );
  const pirateAlertRows: Row[] = [];
  const pirateByZone = new Map<string, NwsAlert[]>();
  pirateRows.forEach((row, i) => {
    const result = pirate[i];
    if (result.status === "rejected") {
      console.error("Pirate Weather failed", String(result.reason));
      return;
    }
    if (row.zones === "") {
      const zone = `pw:${row.token}:${row.location_id}`;
      pirateAlertRows.push({ ...row, zones: zone, baselined: row.pw_baselined });
      pirateByZone.set(zone, result.value.alerts.filter((a) => isActive(a, now)));
    }
    if (wantsRain(row)) {
      const change = minutelyChange(row.minutely_signature, result.value.minutely, now, PIRATE_INTERVAL_MIN, {
        start: hasEvent(row, "precip_start"),
        stop: hasEvent(row, "precip_stop"),
      });
      if (change.signature !== row.minutely_signature) {
        writes.push(db.prepare("UPDATE locations SET minutely_signature = ? WHERE token = ? AND location_id = ?").bind(change.signature, row.token, row.location_id));
      }
      if (change.event) queueEvent(row, change.event);
    }
  });
  const pirateAlerts = [...pirateByZone.values()].flat();
  const piratePlan = planNotifications(pirateAlertRows, pirateByZone, sent, await hashAlerts(pirateAlerts), new Set());
  writes.push(
    ...piratePlan.baselineRecords.map(upsertSent),
    ...piratePlan.baselined.map((l) => db.prepare("UPDATE locations SET pw_baselined = 1 WHERE token = ? AND location_id = ?").bind(l.token, l.location_id)),
  );
  queueAlerts(piratePlan.sends);

  // Forecast discussion, Hazardous Weather Outlook and Special Weather Statements, per office every 5 minutes.
  const recipients = new Map<string, Row[]>();
  for (const row of rows) {
    if (!row.office) continue;
    for (const [type, name] of Object.entries(PRODUCT_EVENTS)) {
      if (!hasEvent(row, name)) continue;
      const key = `${row.office}|${type}`;
      recipients.set(key, [...(recipients.get(key) ?? []), row]);
    }
  }
  const duePairs = [...recipients.keys()].filter((key) => bucket(key, PRODUCT_INTERVAL_MIN) === minute % PRODUCT_INTERVAL_MIN).slice(0, MAX_PRODUCT_LISTS);
  if (duePairs.length > 0) {
    const { results: stateRows } = await db.prepare("SELECT office, product, state FROM offices").all<{ office: string; product: string; state: string }>();
    const states = new Map(stateRows.map((r) => [`${r.office}|${r.product}`, JSON.parse(r.state) as ProductState]));
    let texts = 0;
    const text = async (id: string) => {
      if (texts >= MAX_PRODUCT_TEXTS) return null;
      texts++;
      return productText(env.NWS_USER_AGENT, id).catch((error) => {
        console.error("NWS product failed", String(error));
        return null;
      });
    };
    for (const key of duePairs) {
      const [office, type] = key.split("|");
      const prev = states.get(key) ?? null;
      const list = await productList(env.NWS_USER_AGENT, type, office).catch((error) => {
        console.error("NWS products failed", String(error));
        return null;
      });
      const latest = list?.[0];
      if (!list || !latest) continue;
      let next: ProductState | null = null;
      let event: EventPush | null = null;
      if (type === "AFD") {
        if (!latest.issuanceTime || prev?.issuance === latest.issuanceTime) continue;
        const body = await text(latest.id);
        if (body === null) continue;
        ({ next, event } = discussionChange(prev, latest.issuanceTime, body));
      } else if (type === "HWO") {
        if (prev?.hash && prev.issuance === latest.issuanceTime) continue;
        const body = await text(latest.id);
        if (body === null) continue;
        ({ next, event } = await hwoChange(prev, latest.issuanceTime, body, office, now));
      } else {
        const change = spsChange(prev, list.slice(0, 10).map((p) => p.id), now);
        if (change.newest) {
          const body = await text(change.newest);
          if (body === null) continue;
          event = spsEvent(body);
        }
        next = change.next;
      }
      writes.push(
        db.prepare("INSERT INTO offices (office, product, state, updated_at) VALUES (?1, ?2, ?3, ?4) ON CONFLICT(office, product) DO UPDATE SET state = ?3, updated_at = ?4")
          .bind(office, type, JSON.stringify(next), now),
      );
      if (!event) continue;
      const notified = new Set<string>();
      for (const row of recipients.get(key) ?? []) {
        if (notified.has(row.token)) continue;
        const covered = type === "SPS" && row.zones.split(",").some((z) => (byZone.get(z) ?? []).some((a) => a.event.toLowerCase() === "special weather statement"));
        if (covered) continue;
        notified.add(row.token);
        queueEvent(row, event);
      }
    }
  }

  // Send.
  if (pushes.length > MAX_SENDS_PER_RUN) console.warn(`sending ${MAX_SENDS_PER_RUN} of ${pushes.length} pushes`);
  const batch = pushes.slice(0, MAX_SENDS_PER_RUN);
  if (batch.length > 0) {
    const jwt = await providerToken(env, now);
    const dead = new Set<string>();
    let resetProviderToken = false;
    await Promise.all(
      batch.map(async (push) => {
        const result = await sendPush(env, jwt, push, push.payload, {
          collapseId: (await sha256Hex(push.collapseKey)).slice(0, 32),
          expiration: push.expiration,
        });
        if (result.status === 200) {
          if (push.onSuccess) writes.push(push.onSuccess);
        } else if (isDeadToken(result)) dead.add(push.token);
        else {
          if (isProviderTokenError(result)) resetProviderToken = true;
          console.error("APNs send failed", result.status, result.reason);
        }
      }),
    );
    for (const token of dead) writes.push(...deleteDevice(db, token));
    if (resetProviderToken) writes.push(db.prepare("DELETE FROM meta WHERE key = 'apns_jwt'"));
  }
  if (minute % 60 === 0) writes.push(db.prepare("DELETE FROM sent WHERE sent_at < ?").bind(now - SENT_RETENTION_MS));
  if (writes.length > 0) await db.batch(writes);
}
