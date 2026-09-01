import { Scrolling } from "@/components/board/scrolling";

/** Text that scrolls itself when it does not fit, and sits still when it does. */
export function ScrollingText({
  text,
  className = "",
  color,
}: {
  text: string;
  className?: string;
  /** Overrides the inherited colour. The inner element owns `style` already. */
  color?: string;
}) {
  return (
    <Scrolling content={text} className={className} color={color}>
      <p className="wrap-break-word whitespace-pre-wrap">{text}</p>
    </Scrolling>
  );
}
