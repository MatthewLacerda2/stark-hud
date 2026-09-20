/**
 * Where the browser fetches bytes that are not JSON.
 *
 * The other modules in `lib/api/` wrap `request()`: they ask for a shape and
 * get one back. These do not fetch anything — they hand back a URL for an
 * element to fetch, because a picture is loaded by an `<img>` and a video by a
 * `<video>`, and neither of those calls `fetch`. That made them look like they
 * were not API calls, and so fourteen widgets built their own `/api/v1/...`
 * while `client.ts` sat there being the one place that knows where the backend
 * is. It half-worked: `VITE_API_URL` moved the JSON and left every picture
 * pointing at whatever origin served the page.
 *
 * Everything here goes through `apiUrl`, so there is one base again.
 *
 * `uploadTrack` is the exception and runs the other way: it is the only call on
 * this board that hands the server a file rather than asking it for one. It
 * lives here because what it produces is the same thing everything else here
 * addresses — a file on the host that a widget can play.
 */

import { request, apiUrl } from "@/lib/api/client";

/** The picture a media or image widget holds, by the widget's id. */
export function mediaUrl(id: string): string {
  return apiUrl(`/media/${id}`);
}

/**
 * The icon a widget carries, or the one on the entry at `index` inside it.
 *
 * A filesystem path never appears in a URL: the icon is addressed by whatever
 * holds it, the same way a picture is.
 */
export function iconUrl(id: string, index?: number): string {
  return apiUrl(`/media/${id}/icon${index === undefined ? "" : `/${index}`}`);
}

/**
 * A track's bytes, or the picture beside it, with a stamp that changes when the
 * file does.
 *
 * The stamp is the whole reason this takes one. A track is addressed by the
 * widget's id and its place in the queue, so replacing a queue leaves index 0
 * sitting behind the identical URL over entirely different bytes — and the
 * browser, quite correctly, goes on playing the file it already has, right down
 * to reporting the old one's duration. A URL that changes when the file changes
 * is the one thing a cache cannot argue with.
 */
export function trackUrl(
  id: string,
  index: number,
  stamp: string | null,
  part: "" | "/art" = "",
): string {
  const url = apiUrl(`/media/${id}/track/${index}${part}`);
  return stamp ? `${url}?v=${stamp}` : url;
}

/** The video behind the whole board. Its own route, not an item's media. */
export function backgroundUrl(): string {
  return apiUrl("/media/background");
}

/** The icon on a notification, which is held by the notification, not a widget. */
export function notificationIconUrl(id: string): string {
  return apiUrl(`/notifications/${id}/icon`);
}

/** What the backend says about a file it has just taken, mirroring `schemas/uploads.py`. */
export interface Uploaded {
  /**
   * Where it landed on the host. This is the value a media queue holds: a
   * track is a path on the machine the board runs on, and an uploaded one is
   * no different, which is why nothing about the media widget had to change.
   */
  path: string;
  /** What it ended up being called, which is not always what was sent. */
  name: string;
  /** How much arrived — the one number that says the upload finished. */
  bytes: number;
}

/**
 * Hand the board a file, and get back a path a queue can hold.
 *
 * A file picker gives the page the file's *contents* and never a path, and the
 * browser is usually not even the machine the board runs on — so this is the
 * only way a person at a laptop can put something on the television.
 *
 * The file is the body. Not a `FormData`: a multipart body makes the backend
 * spool the whole film to a temporary file before it can be written where it
 * belongs, which is the same gigabytes twice on a machine with one disk. The
 * name travels in the query instead, encoded because a filename may contain
 * anything at all and is not to be trusted at either end.
 */
export function uploadTrack(file: File): Promise<Uploaded> {
  return request<Uploaded>(
    `/media/upload?name=${encodeURIComponent(file.name)}`,
    { method: "POST", body: file },
  );
}
