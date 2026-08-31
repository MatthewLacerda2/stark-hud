import { useState } from "react";
import type { ImagePayload } from "@/lib/schemas/board";
import { Missing } from "@/components/board/items/missing";

/** An image read from a local path. The item id is the handle, not the path. */
export function Image({ id, payload }: { id: string; payload: ImagePayload }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Missing path={payload.path} />;
  return (
    <img
      src={`/api/v1/media/${id}`}
      alt={payload.alt ?? ""}
      onError={() => setFailed(true)}
      className="size-full rounded-xl object-cover"
    />
  );
}
