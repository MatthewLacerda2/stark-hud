import type { TextPayload } from "@/lib/schemas/board";

const SIZES: Record<TextPayload["size"], string> = {
  sm: "text-body",
  md: "text-h2",
  lg: "text-h1",
  xl: "text-display",
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
