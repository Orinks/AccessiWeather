export interface Registration {
  token: string;
  environment: "sandbox" | "production";
  enabled: boolean;
  severities: string[];
  notifyUnknown: boolean;
  events: string[];
  pirateWeatherKey: string | null;
  locations: { id: string; name: string; latitude: number; longitude: number }[];
}

export const MAX_LOCATIONS = 20;
const SEVERITIES = new Set(["extreme", "severe", "moderate", "minor"]);
export const EVENTS = ["discussion", "hwo", "sps", "precip_start", "precip_stop"];

export function validateRegistration(body: unknown): Registration | string {
  const b = body as Record<string, any> | null;
  if (!b || typeof b !== "object") return "body must be a JSON object";
  if (typeof b.token !== "string" || !/^[0-9a-fA-F]{64,200}$/.test(b.token)) return "invalid device token";
  if (b.environment !== "sandbox" && b.environment !== "production") return "invalid environment";
  if (!Array.isArray(b.locations) || b.locations.length > MAX_LOCATIONS) return "invalid locations";
  const locations: Registration["locations"] = [];
  for (const l of b.locations) {
    if (
      typeof l?.id !== "string" || l.id.length > 64 ||
      typeof l.name !== "string" || l.name.length > 200 ||
      typeof l.latitude !== "number" || Math.abs(l.latitude) > 90 ||
      typeof l.longitude !== "number" || Math.abs(l.longitude) > 180
    ) return "invalid location";
    locations.push({ id: l.id, name: l.name, latitude: l.latitude, longitude: l.longitude });
  }
  const severities = Array.isArray(b.severities)
    ? b.severities.filter((s: unknown): s is string => typeof s === "string" && SEVERITIES.has(s.toLowerCase())).map((s: string) => s.toLowerCase())
    : [];
  const events = EVENTS.filter((name) => b.events?.[name] === true);
  const key = typeof b.pirateWeatherKey === "string" ? b.pirateWeatherKey.trim() : "";
  if (key.length > 200 || /[^A-Za-z0-9_-]/.test(key)) return "invalid Pirate Weather key";
  return {
    token: b.token.toLowerCase(),
    environment: b.environment,
    enabled: b.enabled === true,
    severities,
    notifyUnknown: b.notifyUnknown === true,
    events,
    pirateWeatherKey: key || null,
    locations,
  };
}

export const round4 = (value: number) => Math.round(value * 10_000) / 10_000;
