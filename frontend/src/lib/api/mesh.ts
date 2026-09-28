/** The model file behind a mesh widget. */

import { ApiError, apiUrl } from "@/lib/api/client";

/**
 * The bytes of one widget's model, exactly as they are on disk.
 *
 * Addressed by the widget's id, never by the path it holds — the path stays on
 * the server, the way a picture's does. Bytes rather than JSON, so this does not
 * go through `request()`; the error shape is the same.
 *
 * A 404 here is not only "no such widget": it is also how the board says the
 * file has gone, and asking is what sets that in motion. The backend removes
 * the widget and broadcasts it, so the socket takes this widget off the board a
 * moment after this rejects.
 */
export async function getModel(id: string): Promise<ArrayBuffer> {
  const response = await fetch(apiUrl(`/mesh/${id}`), { cache: "no-store" });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Not JSON: the status text is all there is to say.
    }
    throw new ApiError(response.status, detail);
  }
  return response.arrayBuffer();
}
