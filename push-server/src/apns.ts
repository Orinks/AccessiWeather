export interface ApnsEnv {
  APNS_KEY_P8: string;
  APNS_KEY_ID: string;
  APNS_TEAM_ID: string;
  APNS_TOPIC: string;
}

export interface SendResult {
  status: number;
  reason?: string;
}

/** Accepts the .p8 text even when its newlines were pasted as spaces. */
export function pemToDer(pem: string): ArrayBuffer {
  const base64 = pem.replace(/-----(BEGIN|END) PRIVATE KEY-----/g, "").replace(/\s+/g, "");
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

export function base64url(data: ArrayBuffer | string): string {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function signProviderToken(env: ApnsEnv, issuedAt: number): Promise<string> {
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToDer(env.APNS_KEY_P8),
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"],
  );
  const header = base64url(JSON.stringify({ alg: "ES256", kid: env.APNS_KEY_ID.trim() }));
  const claims = base64url(JSON.stringify({ iss: env.APNS_TEAM_ID, iat: issuedAt }));
  const signature = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    key,
    new TextEncoder().encode(`${header}.${claims}`),
  );
  return `${header}.${claims}.${base64url(signature)}`;
}

export async function sendPush(
  env: ApnsEnv,
  providerToken: string,
  device: { token: string; environment: string },
  payload: unknown,
  options: { collapseId: string; expiration: number },
): Promise<SendResult> {
  const host = device.environment === "sandbox" ? "api.sandbox.push.apple.com" : "api.push.apple.com";
  const response = await fetch(`https://${host}/3/device/${device.token}`, {
    method: "POST",
    headers: {
      authorization: `bearer ${providerToken}`,
      "apns-topic": env.APNS_TOPIC,
      "apns-push-type": "alert",
      "apns-priority": "10",
      "apns-collapse-id": options.collapseId,
      "apns-expiration": String(options.expiration),
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (response.ok) return { status: response.status };
  let reason: string | undefined;
  try {
    reason = ((await response.json()) as { reason?: string }).reason;
  } catch {
    reason = undefined;
  }
  return { status: response.status, reason };
}

export function isDeadToken(result: SendResult): boolean {
  return (
    result.status === 410 ||
    (result.status === 400 && (result.reason === "BadDeviceToken" || result.reason === "DeviceTokenNotForTopic"))
  );
}

export function isProviderTokenError(result: SendResult): boolean {
  return result.status === 403 && (result.reason === "ExpiredProviderToken" || result.reason === "InvalidProviderToken");
}
