export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export async function api(
  path: string,
  org = "",
  data?: unknown,
  headers?: Record<string, string>,
) {
  const response = await fetch(API + path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(org ? { "X-Organization-ID": org } : {}),
      ...headers,
    },
    ...(data === undefined
      ? {}
      : { method: "POST", body: JSON.stringify(data) }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}). Check the form values.`,
    );
  }
  return response.json();
}
