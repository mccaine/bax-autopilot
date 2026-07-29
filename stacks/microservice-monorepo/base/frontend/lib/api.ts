// Shared API client. Pages/components import this instead of hand-rolling fetch,
// so they never need to edit a shared file. Base-owned — do not edit in tasks.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}
