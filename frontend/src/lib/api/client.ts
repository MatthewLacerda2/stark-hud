/**
 * The one place HTTP lives. Pages never call `fetch`; they go through the typed
 * `lib/api/<domain>.ts` wrappers, which call `request()` here. This keeps the
 * base URL and error shape in a single module.
 *
 * There is no auth: the board is open to anyone on the LAN by design.
 *
 * In production the app is served behind a reverse proxy, so the relative
 * `/api/v1` default just works. Point `VITE_API_URL` at the backend origin
 * (e.g. http://localhost:8000/api/v1) when running the dev server standalone.
 */
const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";

/**
 * Where a path on the API lives.
 *
 * `request()` uses it, and so does everything the browser fetches by putting a
 * URL in an attribute rather than by calling `fetch` — a picture's `src`, a
 * track's bytes, the background video. Those are still API calls; they are just
 * made by the element instead of by us, which is exactly how fourteen of them
 * came to spell `/api/v1` themselves and stayed behind when `VITE_API_URL`
 * moved the JSON. See `lib/api/media.ts` for the ones that do.
 */
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

/** A non-2xx response, carrying the HTTP status and the backend's detail. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body } = options;
  // A file goes as itself. Everything else this board sends is JSON, and a file
  // cannot be: a film is gigabytes, `JSON.stringify` would refuse it, and
  // base64 inside a field would be a third more bytes held in memory twice
  // over. `fetch` streams a Blob, so the body crosses as the file it already
  // is and the backend writes it to disk a chunk at a time. Its content type is
  // left unset on purpose — the browser fills one in from the file.
  const raw = body instanceof Blob;
  const headers: Record<string, string> = {};
  if (body !== undefined && !raw) headers["Content-Type"] = "application/json";

  const response = await fetch(apiUrl(path), {
    method,
    headers,
    body: raw
      ? (body as Blob)
      : body === undefined
        ? undefined
        : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await detail(response));
  }
  // 204 No Content (e.g. DELETE) has no body to parse.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Pull FastAPI's `{ detail }` off an error response, falling back to status. */
async function detail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}
