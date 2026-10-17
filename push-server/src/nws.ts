import { parseAlerts, zonesFromPoint, type NwsAlert } from "./alerts";
import { parsePirate } from "./events";

const BASE = "https://api.weather.gov";

function nwsGet(userAgent: string, path: string, accept = "application/geo+json"): Promise<Response> {
  return fetch(BASE + path, { headers: { "User-Agent": userAgent, Accept: accept } });
}

/** UGC zones and forecast office for a point; empty when NWS doesn't cover it (outside the US). */
export async function pointInfo(userAgent: string, latitude: number, longitude: number): Promise<{ zones: string[]; office: string }> {
  const response = await nwsGet(userAgent, `/points/${latitude.toFixed(4)},${longitude.toFixed(4)}`);
  if (response.status === 404) return { zones: [], office: "" };
  if (!response.ok) throw new Error(`NWS points HTTP ${response.status}`);
  const json = (await response.json()) as { properties?: { gridId?: unknown } };
  const office = typeof json.properties?.gridId === "string" ? json.properties.gridId : "";
  return { zones: zonesFromPoint(json), office };
}

export async function activeAlerts(userAgent: string, zones: string[]): Promise<NwsAlert[]> {
  const response = await nwsGet(userAgent, `/alerts/active?status=actual&zone=${zones.join(",")}`);
  if (!response.ok) throw new Error(`NWS alerts HTTP ${response.status}`);
  return parseAlerts(await response.json());
}

/** Newest first, like the app's productItems. */
export async function productList(userAgent: string, type: string, office: string): Promise<{ id: string; issuanceTime: string | null }[]> {
  const response = await nwsGet(userAgent, `/products/types/${type}/locations/${office}`, "application/ld+json");
  if (!response.ok) throw new Error(`NWS products HTTP ${response.status}`);
  const graph = ((await response.json()) as { "@graph"?: unknown })["@graph"];
  return Array.isArray(graph)
    ? graph
        .filter((p: any) => typeof p?.id === "string")
        .map((p: any) => ({ id: p.id, issuanceTime: typeof p.issuanceTime === "string" ? p.issuanceTime : null }))
    : [];
}

export async function productText(userAgent: string, id: string): Promise<string> {
  const response = await nwsGet(userAgent, `/products/${id}`, "application/ld+json");
  if (!response.ok) throw new Error(`NWS product HTTP ${response.status}`);
  const text = ((await response.json()) as { productText?: unknown }).productText;
  if (typeof text !== "string") throw new Error("NWS product without text");
  return text;
}

export async function pirateForecast(key: string, latitude: number, longitude: number) {
  const url = `https://api.pirateweather.net/forecast/${encodeURIComponent(key)}/${latitude},${longitude}?units=si&version=2&exclude=currently,hourly,daily,flags`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Pirate Weather HTTP ${response.status}`);
  return parsePirate(await response.json());
}
