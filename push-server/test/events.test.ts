import { describe, expect, it } from "vitest";
import { decryptText, encryptText } from "../src/crypto";
import { discussionChange, hwoChange, minutelyChange, parsePirate, spsBody, spsChange } from "../src/events";
import { validateRegistration } from "../src/register";

const AFD = (changed: string) => `AREA FORECAST DISCUSSION\n\n.WHAT HAS CHANGED...\n${changed}\n\n&&\n`;

describe("product events", () => {
  it("baselines, then summarizes forecast discussion changes", () => {
    const first = discussionChange(null, "2026-10-16T10:00:00Z", AFD("Colder Friday."));
    expect(first.event).toBeNull();
    const second = discussionChange(first.next, "2026-10-16T16:00:00Z", AFD("Rain arrives earlier."));
    expect(second.event?.body("Home")).toBe("The Area Forecast Discussion for Home was updated by the National Weather Service. Rain arrives earlier.");
    expect(discussionChange(second.next, "2026-10-16T22:00:00Z", AFD("No significant changes.")).event).toBeNull();
  });

  it("rate-limits Hazardous Weather Outlook updates", async () => {
    const now = Date.parse("2026-10-16T12:00:00Z");
    const a = await hwoChange(null, "t1", "Outlook one", "OKX", now);
    const b = await hwoChange(a.next, "t2", "Outlook two with a new line about storms", "OKX", now);
    expect(b.event?.title).toBe("Hazardous Weather Outlook Updated");
    expect((await hwoChange(b.next, "t3", "Outlook three", "OKX", now + 60_000)).event).toBeNull();
  });

  it("announces only new Special Weather Statements", () => {
    const now = Date.now();
    const a = spsChange(null, ["s1"], now);
    expect(a.newest).toBeNull();
    expect(spsChange(a.next, ["s2", "s1"], now).newest).toBe("s2");
    expect(spsChange(a.next, ["s1"], now).newest).toBeNull();
    expect(spsBody("HEADER\n\nShort.\n\nA strong thunderstorm will impact portions of the county through 5 PM.")).toBe(
      "A strong thunderstorm will impact portions of the county through 5 PM.",
    );
  });
});

describe("rain and Pirate Weather", () => {
  const now = Date.parse("2026-10-16T12:00:00Z") ;
  const points = (wetFrom: number) =>
    Array.from({ length: 60 }, (_, i) => ({ time: now / 1000 + i * 60, intensity: i >= wetFrom ? 0.5 : 0, probability: null, type: "rain" }));

  it("notifies when rain starts within the lead time, once", () => {
    const base = minutelyChange(null, points(40), now, 15, { start: true, stop: true });
    expect(base.event).toBeNull();
    const dry = minutelyChange("stopping:rain", points(8), now, 15, { start: true, stop: true });
    expect(dry.event?.title).toBe("Rain starting in 8 minutes");
    expect(dry.event?.body("Home")).toBe("Rain starting in 8 minutes for Home.");
    expect(minutelyChange(dry.signature, points(7), now, 15, { start: true, stop: true }).event).toBeNull();
  });

  it("notifies for the first rain start when the first check saw it beyond the lead time", () => {
    const early = minutelyChange(null, points(40), now, 15, { start: true, stop: true });
    expect(early).toEqual({ signature: "none", event: null });
    expect(minutelyChange(early.signature, points(8), now, 15, { start: true, stop: true }).event?.title).toBe("Rain starting in 8 minutes");
  });

  it("parses alerts with the app's IDs", () => {
    const { alerts, minutely } = parsePirate({
      alerts: [{ title: "Yellow Warning", severity: "moderate", time: 1700000000, expires: 1700003600, regions: ["London"] }, { title: "X", uri: "https://u" }],
      minutely: { data: [{ time: 1, precipIntensity: 0.2, precipType: "rain" }] },
    });
    expect(alerts.map((a) => a.id)).toEqual(["pirate-Yellow Warning-1700000000-0", "https://u"]);
    expect(alerts[0]).toMatchObject({ severity: "Moderate", areaDesc: "London" });
    expect(minutely[0]).toEqual({ time: 1, intensity: 0.2, probability: null, type: "rain" });
  });
});

describe("keys", () => {
  it("round-trips Pirate Weather keys through AES-GCM", async () => {
    const secret = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
    const sealed = await encryptText(secret, "pw-key_123");
    expect(sealed).not.toContain("pw-key");
    expect(await decryptText(secret, sealed)).toBe("pw-key_123");
  });

  it("accepts event switches and rejects odd keys", () => {
    const body = { token: "a".repeat(64), environment: "sandbox", enabled: true, locations: [], events: { hwo: true, sps: false, precip_start: true }, pirateWeatherKey: "abc" };
    expect(validateRegistration(body)).toMatchObject({ events: ["hwo", "precip_start"], pirateWeatherKey: "abc" });
    expect(validateRegistration({ ...body, pirateWeatherKey: "a/b" })).toBe("invalid Pirate Weather key");
  });
});
