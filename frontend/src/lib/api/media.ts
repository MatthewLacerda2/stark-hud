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
 */

import { apiUrl } from "@/lib/api/client";

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
