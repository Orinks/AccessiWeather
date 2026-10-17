import { sha256Hex, type NwsAlert } from "./alerts";

/** Text product and minute-by-minute rain checks, ported from the app's NotificationEventState. */

export const PRODUCT_RATE_LIMIT_MS = 30 * 60_000;
const WET_INTENSITY = 0.01;

export interface ProductState {
  issuance?: string | null;
  hash?: string | null;
  text?: string | null;
  ids?: string[] | null;
  lastNotified?: number | null;
}

export interface EventPush {
  kind: string;
  title: string;
  body: (locationName: string) => string;
}

export function section(text: string, start: string): string | null {
  let inSection = false;
  const body: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const stripped = line.trim();
    if (!inSection) {
      if (stripped.toUpperCase().startsWith(start.toUpperCase())) inSection = true;
      continue;
    }
    if (stripped.startsWith(".") || stripped.startsWith("&&")) break;
    if (stripped) body.push(stripped);
  }
  return inSection && body.length > 0 ? body.join(" ") : null;
}

export const normalized = (text: string | null | undefined) =>
  (text ?? "").split(/\s+/).filter(Boolean).join(" ").toLowerCase().replace(/^[ .!]+|[ .!]+$/g, "");

const NO_CHANGE = new Set([
  "no change", "no changes", "no significant change", "no significant changes",
  "no significant changes made to forecast", "no significant changes made to the forecast",
]);
export const isNoChangeSummary = (text: string | null | undefined) => NO_CHANGE.has(normalized(text));
const truncated = (text: string, limit = 300) => (text.length > limit ? text.slice(0, limit) : text);

export function summarizeChange(previous: string | null | undefined, current: string | null | undefined): string | null {
  if (!current) return null;
  const whatChanged = section(current, ".WHAT HAS CHANGED");
  const noChanges = isNoChangeSummary(whatChanged);
  if (whatChanged && !noChanges) return truncated(whatChanged);
  const keyMessages = section(current, ".KEY MESSAGES");
  if (keyMessages) {
    const previousMessages = section(previous ?? "", ".KEY MESSAGES");
    if (previousMessages === null || normalized(previousMessages) !== normalized(keyMessages)) return truncated(keyMessages);
    if (noChanges) return null;
  }
  if (noChanges) return null;
  const lines = (t: string) => t.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("$"));
  const previousLines = new Set(lines(previous ?? ""));
  const first = lines(current).find((l) => !previousLines.has(l));
  return first ? truncated(first) : null;
}

export function spsBody(text: string): string {
  const paragraphs = text
    .split("\n\n")
    .map((p) => p.split(/\r?\n/).join(" ").trim())
    .filter((p) => {
      const letters = p.replace(/[^\p{L}]/gu, "");
      return letters.length > 40 && /\p{Ll}/u.test(letters);
    });
  const body = paragraphs[0] ?? "A Special Weather Statement was issued. Open Forecaster Notes to read it.";
  return body.length > 160 ? `${body.slice(0, 157)}...` : body;
}

/** The first sighting of every product only records a baseline. */
export function discussionChange(prev: ProductState | null, issuance: string, text: string): { next: ProductState; event: EventPush | null } {
  if (!prev?.issuance) return { next: { issuance, text }, event: null };
  if (!(Date.parse(issuance) > Date.parse(prev.issuance))) return { next: { ...prev, text }, event: null };
  const summary = summarizeChange(prev.text, text);
  const next = { issuance, text };
  if (summary === null && isNoChangeSummary(section(text, ".WHAT HAS CHANGED"))) return { next, event: null };
  return {
    next,
    event: {
      kind: "discussion_update",
      title: "Forecast Discussion Updated",
      body: (name) =>
        `The Area Forecast Discussion for ${name} was updated by the National Weather Service.${summary ? ` ${summary}` : ""}`,
    },
  };
}

export async function hwoChange(
  prev: ProductState | null,
  issuance: string | null,
  text: string,
  office: string,
  now: number,
): Promise<{ next: ProductState; event: EventPush | null }> {
  const hash = await sha256Hex(text.trim());
  if (!prev?.issuance && !prev?.hash) return { next: { issuance, hash, text }, event: null };
  if (prev.issuance === issuance && prev.hash === hash) return { next: prev, event: null };
  const next: ProductState = { issuance, hash, text, lastNotified: prev.lastNotified ?? null };
  if (prev.lastNotified && now - prev.lastNotified < PRODUCT_RATE_LIMIT_MS) return { next, event: null };
  next.lastNotified = now;
  const summary = summarizeChange(prev.text, text)?.trim();
  const body = summary && summary.length > 20 ? summary : `Hazardous Weather Outlook updated for ${office}. Open Forecaster Notes to read it.`;
  return { next, event: { kind: "hwo_update", title: "Hazardous Weather Outlook Updated", body: () => body } };
}

/** Returns the newest unseen SPS product ID to announce; `productIDs` are newest first. */
export function spsChange(prev: ProductState | null, productIDs: string[], now: number): { next: ProductState; newest: string | null } {
  if (!prev?.ids) return { next: { ids: productIDs }, newest: null };
  const current = new Set(productIDs);
  const kept = prev.ids.filter((id) => current.has(id));
  const fresh = productIDs.filter((id) => !kept.includes(id));
  const next: ProductState = { ids: [...kept, ...fresh], lastNotified: prev.lastNotified ?? null };
  if (fresh.length === 0 || (prev.lastNotified && now - prev.lastNotified < PRODUCT_RATE_LIMIT_MS)) return { next, newest: null };
  next.lastNotified = now;
  return { next, newest: fresh[0] };
}

export const spsEvent = (text: string): EventPush => ({
  kind: "sps_issued",
  title: "Special Weather Statement",
  body: () => spsBody(text),
});

export interface MinutelyPoint {
  time: number;
  intensity: number | null;
  probability: number | null;
  type: string | null;
}

const isWet = (p: MinutelyPoint) => (p.intensity !== null ? p.intensity >= WET_INTENSITY : (p.probability ?? 0) >= 0.5);

function precipitationLabel(type: string | null): string {
  switch (type?.toLowerCase()) {
    case "rain": return "Rain";
    case "snow": return "Snow";
    case "sleet": return "Sleet";
    case "hail": return "Hail";
    default: return "Precipitation";
  }
}

/** `leadMinutes` is how far ahead a change may be; the server uses its polling interval. */
export function minutelyChange(
  signature: string | null,
  points: MinutelyPoint[],
  now: number,
  leadMinutes: number,
  wants: { start: boolean; stop: boolean },
): { signature: string | null; event: EventPush | null } {
  const upcoming = points.filter((p) => p.time * 1000 + 60_000 > now);
  const first = upcoming[0];
  if (!first) return { signature, event: null };
  const wetNow = isWet(first);
  const change = upcoming.find((p) => isWet(p) !== wetNow);
  if (!change) return { signature: "none", event: null };
  const starting = !wetNow;
  const type = starting ? "starting" : "stopping";
  const precipType = (starting ? change : first).type;
  const next = `${type}:${precipType ?? ""}`;
  const minutes = Math.max(1, Math.round((change.time * 1000 - now) / 60_000));
  if (minutes > leadMinutes) return { signature: signature ?? "none", event: null };
  if (signature === null) return { signature: next, event: null };
  if (signature === next) return { signature, event: null };
  if (!(starting ? wants.start : wants.stop)) return { signature: next, event: null };
  const title = `${precipitationLabel(precipType)} ${type} in ${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
  return {
    signature: next,
    event: { kind: starting ? "minutely_precipitation_start" : "minutely_precipitation_stop", title, body: (name) => `${title} for ${name}.` },
  };
}

const iso = (seconds: unknown) => (typeof seconds === "number" ? new Date(seconds * 1000).toISOString() : null);
const capitalized = (s: string) => s.toLowerCase().replace(/\b\p{L}/gu, (c) => c.toUpperCase());

/** Pirate Weather alerts in the app's shape (same IDs as PirateWeatherClient, so taps open them). */
export function parsePirate(json: unknown): { alerts: NwsAlert[]; minutely: MinutelyPoint[] } {
  const body = (json ?? {}) as { alerts?: unknown; minutely?: { data?: unknown } };
  const raw = Array.isArray(body.alerts) ? body.alerts : [];
  const alerts = raw.map((a: any, index: number): NwsAlert => {
    const title = typeof a?.title === "string" ? a.title : null;
    return {
      id: typeof a?.uri === "string" ? a.uri : `pirate-${title ?? "alert"}-${Math.trunc(a?.time ?? 0)}-${index}`,
      event: title ?? "Weather Alert",
      severity: typeof a?.severity === "string" ? capitalized(a.severity) : "Unknown",
      urgency: "Unknown",
      headline: title,
      description: typeof a?.description === "string" ? a.description : null,
      instruction: null,
      areaDesc: Array.isArray(a?.regions) ? a.regions.join(", ") : null,
      ugc: [],
      sent: iso(a?.time),
      expires: iso(a?.expires),
      ends: null,
      messageType: "Alert",
      references: [],
    };
  });
  const data = Array.isArray(body.minutely?.data) ? (body.minutely!.data as any[]) : [];
  const minutely = data
    .filter((p) => typeof p?.time === "number")
    .map((p) => ({
      time: p.time,
      intensity: typeof p.precipIntensity === "number" ? p.precipIntensity : null,
      probability: typeof p.precipProbability === "number" ? p.precipProbability : null,
      type: typeof p.precipType === "string" ? p.precipType : null,
    }));
  return { alerts, minutely };
}
