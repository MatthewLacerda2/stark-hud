import type { Item } from "@/lib/schemas/board";
import { KindIcon } from "@/components/board/kind-icon";
import { cn } from "@/lib/utils";

/** How many sleeves are drawn in full before the rest go behind them. */
const FACING = 3;

/**
 * A folded group: the icons of what is inside, stacked like sleeves on a shelf.
 *
 * An open group draws nothing at all — its widgets are on the board — so this
 * component is only ever the closed one.
 *
 * Three are shown and a fourth sits behind them, blurred, however many there
 * really are. That is deliberate: a count is a number to read, and this is a
 * television across a room. What it says is *what kind of things are in here,
 * and that there are several*, which is the whole of what anybody can use from
 * the sofa. Five widgets or twenty, it looks the same and takes the same room.
 *
 * Nothing is labelled. A group is asked for by name through a tool, never
 * picked up off the screen, so a caption would be chrome for a pointer that
 * does not exist in the room.
 */
export function Group({ holds }: { holds: Item[] }) {
  const facing = holds.slice(0, FACING);
  const behind = holds.length > FACING;

  return (
    <div className="flex size-full items-center justify-center gap-[6cqw] rounded-xl widget-surface widget-edge p-[8cqw] widget-text">
      {behind ? (
        <div className="relative size-[22cqw] shrink-0 opacity-40 blur-[2px]">
          <KindIcon kind={holds[FACING].payload.kind} />
        </div>
      ) : null}
      {facing.map((item, index) => (
        <div
          key={item.id}
          className={cn(
            "size-[26cqw] shrink-0",
            // The nearest sleeve is the one in front: they read as a stack
            // rather than a row because they do not all sit at the same weight.
            index === 0
              ? "opacity-100"
              : index === 1
                ? "opacity-80"
                : "opacity-60",
          )}
        >
          <KindIcon kind={item.payload.kind} />
        </div>
      ))}
    </div>
  );
}
