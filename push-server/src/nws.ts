import { parseAlerts, zonesFromPoint, type NwsAlert } from "./alerts";

const BASE = "https://api.weather.gov";

function nwsGet(userAgent: string, path: string): Promise<Response> {
  return fetch(BASE + path, { headers: { "User-Agent": userAgent, Accept: "application/geo+json" } });
}

/** UGC zones for a point, or [] when NWS doesn't cover it (outside the US). */
export async function zonesFor(userAgent: string, latitude: number, longitude: number): Promise<string[]> {
  const response = await nwsGet(userAgent, `/points/${latitude.toFixed(4)},${longitude.toFixed(4)}`);
  if (response.status === 404) return [];
  if (!response.ok) throw new Error(`NWS points HTTP ${response.status}`);
  return zonesFromPoint(await response.json());
}

export async function activeAlerts(userAgent: string, zones: string[]): Promise<NwsAlert[]> {
  const response = await nwsGet(userAgent, `/alerts/active?status=actual&zone=${zones.join(",")}`);
  if (!response.ok) throw new Error(`NWS alerts HTTP ${response.status}`);
  return parseAlerts(await response.json());
}
