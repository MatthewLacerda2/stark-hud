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
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(apiUrl(path), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      detail(await response.text(), response.statusText),
    );
  }
  // 204 No Content (e.g. DELETE) has no body to parse.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Send a file, saying how much of it has gone while it goes.
 *
 * The file goes as itself, never as JSON: a film is gigabytes, `JSON.stringify`
 * would refuse it, and base64 inside a field would be a third more bytes held in
 * memory twice over. The body crosses as the file it already is and the backend
 * writes it to disk a chunk at a time. Its content type is left unset on
 * purpose — the browser fills one in from the file.
 *
 * `XMLHttpRequest` rather than `fetch`, and only here, because it is the one
 * thing in a browser that reports how much of a body has been sent. A film over
 * the LAN takes minutes, and "uploading" with no number on it for minutes reads
 * as stuck. `fetch` can stream a request body, but Chrome allows that only over
 * HTTP/2, and says nothing about progress even then.
 *
 * It rejects with the same `ApiError` as `request()` when the backend says no,
 * and with a plain `Error` when the request never got an answer at all.
 */
export function upload<T>(
  path: string,
  file: Blob,
  onProgress?: (fraction: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiUrl(path));
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(event.loaded / event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as T);
        return;
      }
      reject(
        new ApiError(xhr.status, detail(xhr.responseText, xhr.statusText)),
      );
    };
    xhr.onerror = () => reject(new Error("upload never reached the board"));
    xhr.send(file);
  });
}

/** Pull FastAPI's `{ detail }` off an error body, falling back to the status. */
function detail(body: string, fallback: string): string {
  try {
    const data = JSON.parse(body) as { detail?: unknown };
    return typeof data.detail === "string" ? data.detail : fallback;
  } catch {
    return fallback;
  }
}
