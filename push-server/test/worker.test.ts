import { describe, expect, it } from "vitest";
import { alertKey, buildPayload, contentHash, decide, isActive, parseAlerts, wants, zonesFromPoint, type NwsAlert } from "../src/alerts";
import { base64url, isDeadToken, pemToDer, signProviderToken } from "../src/apns";
import { planNotifications, type LocationRow } from "../src/plan";
import { validateRegistration } from "../src/register";

const feature = (props: Record<string, unknown>) => ({ properties: { id: "urn:a1", event: "Flood Warning", severity: "Severe", urgency: "Expected", headline: "Flood Warning until 6 PM", geocode: { UGC: ["NYZ072"] }, sent: "2026-10-16T10:00:00-04:00", messageType: "Alert", references: [], ...props } });
const alert = (props: Record<string, unknown> = {}): NwsAlert => parseAlerts({ features: [feature(props)] })[0];
const token = "a".repeat(64);
const location = (over: Partial<LocationRow> = {}): LocationRow => ({ token, location_id: "L1", name: "Home", zones: "NYZ072,NYC061", baselined: 1, environment: "production", severities: "extreme,severe", notify_unknown: 0, ...over });

describe("alerts", () => {
  it("parses NWS features and skips malformed ones", () => {
    const alerts = parseAlerts({ features: [feature({}), { properties: { id: 5 } }, {}] });
    expect(alerts).toHaveLength(1);
    expect(alerts[0].ugc).toEqual(["NYZ072"]);
  });

  it("keys updates by the earliest referenced alert", () => {
    const a = alert({ id: "urn:a3", references: [
      { identifier: "urn:a2", sent: "2026-10-16T11:00:00-04:00" },
      { identifier: "urn:a1", sent: "2026-10-16T14:30:00Z" },
    ] });
    expect(alertKey(a)).toBe("urn:a1");
    expect(alertKey(alert())).toBe("urn:a1");
  });

  it("decides new, updated and escalated", () => {
    expect(decide(undefined, "h", 4)).toBe("new");
    expect(decide({ content_hash: "h", severity: 4 }, "h", 4)).toBeNull();
    expect(decide({ content_hash: "h", severity: 4 }, "x", 4)).toBe("updated");
    expect(decide({ content_hash: "h", severity: 3 }, "x", 4)).toBe("escalated");
  });

  it("filters by the device's severities", () => {
    expect(wants("extreme,severe", false, "Severe")).toBe(true);
    expect(wants("extreme,severe", false, "Minor")).toBe(false);
    expect(wants("", true, "Unknown")).toBe(true);
    expect(wants("extreme", false, "Unknown")).toBe(false);
  });

  it("drops cancelled and ended alerts", () => {
    const now = Date.parse("2026-10-16T12:00:00Z");
    expect(isActive(alert({ messageType: "Cancel" }), now)).toBe(false);
    expect(isActive(alert({ ends: "2026-10-16T11:00:00Z", expires: "2026-10-16T10:00:00Z" }), now)).toBe(false);
    expect(isActive(alert({ ends: "2026-10-16T13:00:00Z" }), now)).toBe(true);
  });

  it("hashes content so edits change it", async () => {
    expect(await contentHash(alert())).toBe(await contentHash(alert({ id: "urn:other" })));
    expect(await contentHash(alert())).not.toBe(await contentHash(alert({ headline: "Extended" })));
  });

  it("formats pushes like the app's local notifications", () => {
    const loc = { id: "L1", name: "Home" };
    expect((buildPayload("new", alert(), loc).aps as any).alert).toEqual({ title: "Severe alert: Flood Warning", subtitle: "Home", body: "Flood Warning until 6 PM" });
    expect((buildPayload("updated", alert(), loc).aps as any).alert.title).toBe("Updated alert: Flood Warning");
    expect((buildPayload("escalated", alert(), loc).aps as any).alert.title).toBe("Escalated to Severe: Flood Warning");
    expect(buildPayload("new", alert(), loc)).toMatchObject({ alertID: "urn:a1", locationID: "L1" });
    expect((buildPayload("new", alert(), loc).aps as any)["interruption-level"]).toBe("time-sensitive");
    expect((buildPayload("new", alert({ severity: "Moderate" }), loc).aps as any)["interruption-level"]).toBeUndefined();
  });

  it("reads forecast, county and fire zones from /points", () => {
    expect(zonesFromPoint({ properties: { forecastZone: "https://api.weather.gov/zones/forecast/NYZ072", county: "https://api.weather.gov/zones/county/NYC061", fireWeatherZone: "https://api.weather.gov/zones/fire/NYZ212" } })).toEqual(["NYZ072", "NYC061", "NYZ212"]);
    expect(zonesFromPoint({})).toEqual([]);
  });
});

describe("planNotifications", () => {
  const byZone = (a: NwsAlert) => new Map(a.ugc.map((z) => [z, [a]]));

  it("baselines a new location without pushing", () => {
    const a = alert();
    const plan = planNotifications([location({ baselined: 0 })], byZone(a), new Map(), new Map([[a.id, "h"]]), new Set());
    expect(plan.sends).toHaveLength(0);
    expect(plan.baselineRecords).toEqual([{ token, key: "urn:a1", hash: "h", severity: 4 }]);
    expect(plan.baselined).toEqual([{ token, location_id: "L1" }]);
  });

  it("pushes Extreme and Severe alerts already active where a current location arrived", () => {
    const severe = alert();
    const moderate = alert({ id: "urn:a2", severity: "Moderate" });
    const zones = new Map([["NYZ072", [severe, moderate]]]);
    const plan = planNotifications([location({ baselined: 2, severities: "extreme,severe,moderate" })], zones, new Map(), new Map([[severe.id, "h"], [moderate.id, "m"]]), new Set());
    expect(plan.sends.map((s) => [s.kind, s.key])).toEqual([["new", "urn:a1"]]);
    expect(plan.baselineRecords.map((r) => r.key)).toEqual(["urn:a2"]);
    expect(plan.baselined).toEqual([{ token, location_id: "L1" }]);
  });

  it("does not baseline when the location's zones failed to load", () => {
    const plan = planNotifications([location({ baselined: 0 })], new Map(), new Map(), new Map(), new Set(["NYC061"]));
    expect(plan.baselined).toHaveLength(0);
  });

  it("sends each alert once per device, under its first matching location", () => {
    const a = alert();
    const plan = planNotifications([location(), location({ location_id: "L2", name: "Work" })], byZone(a), new Map(), new Map([[a.id, "h"]]), new Set());
    expect(plan.sends.map((s) => [s.kind, s.location.name])).toEqual([["new", "Home"]]);
  });

  it("skips alerts already sent with the same content and unwanted severities", () => {
    const a = alert();
    const sent = new Map([[`${token}|urn:a1`, { token, alert_key: "urn:a1", content_hash: "h", severity: 4 }]]);
    expect(planNotifications([location()], byZone(a), sent, new Map([[a.id, "h"]]), new Set()).sends).toHaveLength(0);
    const minor = alert({ severity: "Minor" });
    expect(planNotifications([location()], byZone(minor), new Map(), new Map([[minor.id, "h"]]), new Set()).sends).toHaveLength(0);
  });
});

describe("registration", () => {
  const body = { token, environment: "production", enabled: true, severities: ["Severe", "bogus"], notifyUnknown: false, locations: [{ id: "L1", name: "Home", latitude: 40.7, longitude: -74 }] };

  it("accepts a valid body and normalizes severities", () => {
    expect(validateRegistration(body)).toMatchObject({ token, severities: ["severe"], enabled: true });
  });

  it("rejects bad tokens, environments and too many locations", () => {
    expect(validateRegistration({ ...body, token: "xyz" })).toBe("invalid device token");
    expect(validateRegistration({ ...body, environment: "dev" })).toBe("invalid environment");
    expect(validateRegistration({ ...body, locations: Array(21).fill(body.locations[0]) })).toBe("invalid locations");
    expect(validateRegistration(null)).toBe("body must be a JSON object");
  });
});

describe("apns", () => {
  it("signs an ES256 provider token that verifies, even from a .p8 pasted with spaces", async () => {
    const pair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
    const der = await crypto.subtle.exportKey("pkcs8", pair.privateKey);
    const b64 = btoa(String.fromCharCode(...new Uint8Array(der)));
    const pem = `-----BEGIN PRIVATE KEY----- ${b64.match(/.{1,64}/g)!.join(" ")} -----END PRIVATE KEY-----`;
    expect(new Uint8Array(pemToDer(pem))).toEqual(new Uint8Array(der));
    const jwt = await signProviderToken({ APNS_KEY_P8: pem, APNS_KEY_ID: "ABC123DEFG", APNS_TEAM_ID: "GANLL6R3Q9", APNS_TOPIC: "t" }, 1_700_000_000);
    const [h, c, s] = jwt.split(".");
    expect(JSON.parse(atob(h.replace(/-/g, "+").replace(/_/g, "/")))).toEqual({ alg: "ES256", kid: "ABC123DEFG" });
    expect(JSON.parse(atob(c))).toEqual({ iss: "GANLL6R3Q9", iat: 1_700_000_000 });
    const sig = Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "==".slice(0, (4 - (s.length % 4)) % 4)), (ch) => ch.charCodeAt(0));
    expect(await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, pair.publicKey, sig, new TextEncoder().encode(`${h}.${c}`))).toBe(true);
    expect(base64url("hi?")).toBe("aGk_");
  });

  it("treats unregistered and bad tokens as dead", () => {
    expect(isDeadToken({ status: 410, reason: "Unregistered" })).toBe(true);
    expect(isDeadToken({ status: 400, reason: "BadDeviceToken" })).toBe(true);
    expect(isDeadToken({ status: 429, reason: "TooManyRequests" })).toBe(false);
  });
});
