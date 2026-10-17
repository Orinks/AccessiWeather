export interface NwsAlert {
  id: string;
  event: string;
  severity: string;
  urgency: string;
  headline: string | null;
  description: string | null;
  instruction: string | null;
  areaDesc: string | null;
  ugc: string[];
  sent: string | null;
  expires: string | null;
  ends: string | null;
  messageType: string;
  references: { identifier: string; sent: string | null }[];
}

export type Decision = "new" | "updated" | "escalated";

const text = (value: unknown): string | null =>
  typeof value === "string" && value.length > 0 ? value : null;

export function parseAlerts(json: unknown): NwsAlert[] {
  const features = (json as { features?: unknown })?.features;
  if (!Array.isArray(features)) return [];
  const alerts: NwsAlert[] = [];
  for (const feature of features) {
    const p = (feature as { properties?: Record<string, any> })?.properties;
    if (!p || typeof p.id !== "string" || typeof p.event !== "string") continue;
    const ugc = p.geocode?.UGC;
    const references = Array.isArray(p.references) ? p.references : [];
    alerts.push({
      id: p.id,
      event: p.event,
      severity: text(p.severity) ?? "Unknown",
      urgency: text(p.urgency) ?? "Unknown",
      headline: text(p.headline),
      description: text(p.description),
      instruction: text(p.instruction),
      areaDesc: text(p.areaDesc),
      ugc: Array.isArray(ugc) ? ugc.filter((z): z is string => typeof z === "string") : [],
      sent: text(p.sent),
      expires: text(p.expires),
      ends: text(p.ends),
      messageType: text(p.messageType) ?? "Alert",
      references: references
        .filter((r: any) => typeof r?.identifier === "string")
        .map((r: any) => ({ identifier: r.identifier, sent: text(r.sent) })),
    });
  }
  return alerts;
}

export function severityPriority(severity: string): number {
  switch (severity.toLowerCase()) {
    case "extreme": return 5;
    case "severe": return 4;
    case "moderate": return 3;
    case "minor": return 2;
    default: return 1;
  }
}

export function isActive(alert: NwsAlert, now: number): boolean {
  if (alert.messageType === "Cancel") return false;
  const ends = [alert.ends, alert.expires].filter((v): v is string => v !== null).map(Date.parse);
  return ends.length === 0 || ends.some((t) => Number.isNaN(t) || t > now);
}

/** Updates and extensions reference the original alert; key them by it so they count as updates. */
export function alertKey(alert: NwsAlert): string {
  let key = alert.id;
  let earliest = Infinity;
  for (const ref of alert.references) {
    const sent = ref.sent ? Date.parse(ref.sent) : NaN;
    const order = Number.isNaN(sent) ? Infinity - 1 : sent;
    if (order < earliest) {
      earliest = order;
      key = ref.identifier;
    }
  }
  return key;
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function contentHash(alert: NwsAlert): Promise<string> {
  return sha256Hex(
    [alert.event, alert.description, alert.severity, alert.urgency, alert.headline, alert.instruction]
      .map((v) => v ?? "")
      .join("\u001f"),
  );
}

export function decide(
  previous: { content_hash: string; severity: number } | undefined,
  hash: string,
  severity: number,
): Decision | null {
  if (!previous) return "new";
  if (previous.content_hash === hash) return null;
  return severity > previous.severity ? "escalated" : "updated";
}

export function wants(severities: string, notifyUnknown: boolean, severity: string): boolean {
  if (severityPriority(severity) === 1) return notifyUnknown;
  return severities.split(",").includes(severity.toLowerCase());
}

/** Same wording as the app's local alert notifications (AppModel+Notifications.swift). */
export function buildPayload(
  kind: Decision,
  alert: NwsAlert,
  location: { id: string; name: string },
): Record<string, unknown> {
  const title =
    kind === "updated" ? `Updated alert: ${alert.event}`
    : kind === "escalated" ? `Escalated to ${alert.severity}: ${alert.event}`
    : `${alert.severity} alert: ${alert.event}`;
  return {
    aps: {
      alert: { title, subtitle: location.name, body: alert.headline ?? alert.areaDesc ?? location.name },
      sound: "default",
      "thread-id": location.id,
    },
    alertID: alert.id,
    locationID: location.id,
  };
}

export function zonesFromPoint(json: unknown): string[] {
  const p = (json as { properties?: Record<string, unknown> })?.properties ?? {};
  const zones = [p.forecastZone, p.county, p.fireWeatherZone]
    .filter((v): v is string => typeof v === "string")
    .map((url) => url.split("/").pop() ?? "")
    .filter((z) => /^[A-Z]{2}[CZ]\d{3}$/.test(z));
  return [...new Set(zones)];
}

export function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}
