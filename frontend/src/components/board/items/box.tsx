import type { BoxPayload } from "@/lib/schemas/board";

/** A container. Children sit on the grid themselves; this draws the frame. */
export function Box({
  payload,
  children,
}: {
  payload: BoxPayload;
  children?: React.ReactNode;
}) {
  return (
    <div
      className="flex size-full flex-col rounded-xl border-2 border-border p-4"
      style={{
        backgroundColor: payload.fill ?? undefined,
        borderColor: payload.stroke ?? undefined,
      }}
    >
      {payload.label ? (
        <span className="mb-2 text-caption uppercase text-muted-foreground">
          {payload.label}
        </span>
      ) : null}
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
