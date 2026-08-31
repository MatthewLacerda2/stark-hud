import type { TextPayload } from "@/lib/schemas/board";

// Relative to the tile, not the page: a "lg" text in a small cell should not
// overflow it, and in a full-width banner it should fill it.
const SIZES: Record<TextPayload["size"], string> = {
  sm: "text-node-sm",
  md: "text-node",
  lg: "text-node-lg",
  xl: "text-node-xl",
};

/** Free-standing text with no card around it. */
export function Text({ payload }: { payload: TextPayload }) {
  return (
    <div className="flex size-full items-center justify-center p-2">
      <p
        className={`${SIZES[payload.size]} wrap-break-word whitespace-pre-wrap text-center text-foreground`}
      >
        {payload.text}
      </p>
    </div>
  );
}
