import { useState } from "react";
import type { VideoPayload } from "@/lib/schemas/board";
import { Missing } from "@/components/board/items/missing";

/** A video read from a local path, muted by default so a wall of widgets is bearable. */
export function Video({ id, payload }: { id: string; payload: VideoPayload }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Missing path={payload.path} />;
  return (
    <video
      src={`/api/v1/media/${id}`}
      autoPlay={payload.autoplay}
      loop={payload.loop}
      muted={payload.muted}
      playsInline
      onError={() => setFailed(true)}
      className="size-full rounded-xl object-cover"
    />
  );
}
