import { alertKey, decide, isTimeSensitive, severityPriority, wants, type Decision, type NwsAlert } from "./alerts";

/** `baselined` value for a current location that just moved: its active Extreme and Severe alerts are pushed. */
export const ARRIVAL_BASELINE = 2;

export interface LocationRow {
  token: string;
  location_id: string;
  name: string;
  zones: string;
  baselined: number;
  environment: string;
  severities: string;
  notify_unknown: number;
}

export interface SentRow {
  token: string;
  alert_key: string;
  content_hash: string;
  severity: number;
}

export interface Record {
  token: string;
  key: string;
  hash: string;
  severity: number;
}

export interface PlannedSend extends Record {
  kind: Decision;
  alert: NwsAlert;
  location: LocationRow;
}

export interface Plan {
  sends: PlannedSend[];
  /** Alerts already active when a location was first checked: recorded, not pushed. */
  baselineRecords: Record[];
  baselined: { token: string; location_id: string }[];
}

/**
 * Decides which pushes to send. Each alert goes to a device once, under the first of its
 * locations that the alert covers; a location whose zones couldn't be fetched isn't baselined.
 */
export function planNotifications(
  locations: LocationRow[],
  alertsByZone: Map<string, NwsAlert[]>,
  sent: Map<string, SentRow>,
  hashes: Map<string, string>,
  failedZones: Set<string>,
): Plan {
  const plan: Plan = { sends: [], baselineRecords: [], baselined: [] };
  const claimed = new Set<string>();
  for (const location of locations) {
    const zones = location.zones.split(",").filter(Boolean);
    const failed = zones.some((z) => failedZones.has(z));
    const arriving = location.baselined === ARRIVAL_BASELINE;
    const matched = new Map<string, NwsAlert>();
    for (const zone of zones) for (const alert of alertsByZone.get(zone) ?? []) matched.set(alert.id, alert);
    const newestFirst = [...matched.values()].sort(
      (a, b) => (Date.parse(b.sent ?? "") || 0) - (Date.parse(a.sent ?? "") || 0),
    );
    for (const alert of newestFirst) {
      const key = alertKey(alert);
      const claim = `${location.token}|${key}`;
      if (claimed.has(claim)) continue;
      claimed.add(claim);
      const hash = hashes.get(alert.id) ?? "";
      const severity = severityPriority(alert.severity);
      if (!location.baselined || (arriving && !isTimeSensitive(alert.severity))) {
        if (!failed) plan.baselineRecords.push({ token: location.token, key, hash, severity });
        continue;
      }
      if (!wants(location.severities, location.notify_unknown === 1, alert.severity)) continue;
      const kind = decide(sent.get(claim), hash, severity);
      if (kind) plan.sends.push({ token: location.token, key, hash, severity, kind, alert, location });
    }
    if ((!location.baselined || arriving) && !failed) {
      plan.baselined.push({ token: location.token, location_id: location.location_id });
    }
  }
  return plan;
}
