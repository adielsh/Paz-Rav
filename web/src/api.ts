import { currentIdToken } from "./auth";

/** fetch() that attaches the current Firebase ID token — a no-op header when signed
 * out or when auth is disabled (ALLOWED_EMAIL unset), so it's safe to use everywhere. */
export async function authedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await currentIdToken();
  if (!token) return fetch(url, options);
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, { ...options, headers });
}
