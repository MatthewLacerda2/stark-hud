/** The geometry behind a mesh widget. */

import { request } from "@/lib/api/client";
import type { Wireframe } from "@/lib/schemas/board";

/**
 * The points and lines of one widget's model.
 *
 * Addressed by the widget's id, never by the path it holds — the path stays on
 * the server, the way a picture's does.
 *
 * A 404 here is not only "no such widget": it is also how the board says the
 * file has gone, and asking is what sets that in motion. The backend removes
 * the widget and broadcasts it, so the socket takes this widget off the board a
 * moment after this rejects.
 */
export function getWireframe(id: string): Promise<Wireframe> {
  return request<Wireframe>(`/mesh/${id}`);
}
