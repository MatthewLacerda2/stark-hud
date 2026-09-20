import { Cell, PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";
import type { ChartPayload } from "@/lib/schemas/board";
import { ChartContainer } from "@/components/ui/chart";
import { Icon } from "@/components/board/icon";
import {
  crossed,
  pick,
  SWEEP_MS,
  toConfig,
} from "@/components/board/items/chart-marks";
import { cn } from "@/lib/utils";

// The part of the ring the value has not reached: white, kept see-through so the
// video still moves behind it. Solid white would glare on a television in a dim
// room and compete with the mark sitting inside the ring. Every widget here sits
// on the same dark video, so there is nothing for this to vary with.
const UNFILLED = "#ffffff40";

// The most rings one gauge draws. Four is a target, five is a pattern, and a
// widget full of concentric circles stops being readings and becomes a texture.
const MAX_RINGS = 3;

// Where the rings start, and how much room that leaves in the middle, by how
// many there are.
//
// Both ends have to move together and that is the whole of the design here.
// Three rings in the single ring's 28% band would be 9% of the radius each,
// which is a hairline from a sofa; widening the band to fix that takes the
// middle away. So the band grows and the hole shrinks, and what stops the hole
// shrinking too far is that it still has to hold an icon and a word.
//
// The hole is the largest square that fits inside the inner circle, which is
// the inner radius over root two: 72 gives 50, and 50 is the number that was
// already there. One ring is therefore today's gauge exactly, not a rounding of
// it — that is a requirement rather than a nicety, because this is the gauge
// learning to be three rather than a redesign of it.
//
// Tailwind reads these as whole strings. A size built by interpolation is a
// class the build never sees and the browser resolves to nothing.
const BANDS = [
  { inner: "72%", hole: "size-[50cqmin]", small: false },
  { inner: "60%", hole: "size-[42cqmin]", small: true },
  { inner: "50%", hole: "size-[35cqmin]", small: true },
];

// `cqmin` needs a container sized in both axes, which the widget's own
// `@container` is not, so the gauge declares one of its own.
const SIZED = { containerType: "size" } as const;
const HOLE = "flex flex-col justify-center overflow-hidden";

/**
 * A gauge: one number, drawn as a ring, with what it is about inside it.
 *
 * The ring is a whole circle and always was — the value decides how far round
 * the bar goes, not how much circle there is, so the track behind it can close
 * the loop and the reading is a proportion you can see from the sofa.
 *
 * Up to three of them, concentric, sharing their edges. Three readings that
 * belong together used to cost three widgets and half the board's width, and a
 * ring does not need the middle of its circle — so the second one goes inside
 * the first. The first row is the outer ring, in the order they arrived, which
 * leaves the ordering with whoever sent the data instead of having a ring swap
 * places when a number moves.
 *
 * The middle says who the gauge is rather than repeating what the ring already
 * shows: an icon, a short label, and under them whatever the row's `x_key`
 * spelled out — "3.7 de 15.6 GB", which is the sentence its collector wrote and
 * not a number we round. Any of the three may be missing; the value never is.
 *
 * With more than one ring that spelled-out reading is not drawn. Three sentences
 * do not fit in a hole that just got smaller, and each ring already carries its
 * own proportion — which is the argument the gauge makes for not repeating its
 * own number in the first place. The title stops naming a reading and starts
 * naming the set: "Machine" rather than "RAM".
 *
 * With an icon the two of them are a pair, aligned from the left so they read as
 * one thing and a long label runs out to the right instead of shoving the icon
 * about. With no icon there is nothing to pair with, so the label is centred in
 * the hole like the number used to be.
 */
export function Gauge({ id, payload }: { id: string; payload: ChartPayload }) {
  const rows = payload.data.slice(0, MAX_RINGS);
  const band = BANDS[Math.max(rows.length, 1) - 1] ?? BANDS[0];
  const ceiling = payload.max ?? 100;
  // Left alignment exists so an icon and a label read as one unit from the same
  // edge. On its own, either of them is just a thing in the middle of a ring,
  // and pushing it left only looks like a mistake.
  const paired = Boolean(payload.icon && payload.title);
  // Only a single ring spells its reading out. See the note above the component.
  const reading = rows.length === 1 ? String(rows[0][payload.x_key] ?? "") : "";
  // Read per ring rather than once, so the memory ring can turn at its own
  // threshold while the one beside it stays the board's white.
  const arc = (at: number) =>
    crossed(payload.thresholds, Number(rows[at][payload.series[0]])) ??
    pick(payload.colors, at);

  // Recharts lays its rows out from the middle outwards, so the row that should
  // be the outer ring has to go in last. Reversed here rather than in the
  // payload: `arc` still reads by the caller's own index, so the first row keeps
  // the first colour wherever it ends up being drawn.
  const drawn = rows.map((_, at) => rows.length - 1 - at);

  return (
    <div className="relative size-full" style={SIZED}>
      <ChartContainer
        config={toConfig(payload.series, payload.colors)}
        className="size-full"
      >
        <RadialBarChart
          data={drawn.map((at) => rows[at])}
          // The whole circle, with the axis below deciding where the bar stops.
          // Made the arc's own extent, the track had only the bar's sweep to
          // paint and the rest of the ring did not exist.
          startAngle={90}
          endAngle={-270}
          innerRadius={band.inner}
          outerRadius="100%"
          // The arc is the whole widget, so it gets the whole widget. Recharts
          // otherwise keeps five pixels of margin all round and shaves a tenth
          // off the ring for the gap between bars, which is a gap between one
          // bar and itself. Both come back as radius.
          margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
          barCategoryGap={0}
        >
          <PolarAngleAxis
            type="number"
            domain={[0, ceiling]}
            tick={false}
            axisLine={false}
          />
          <RadialBar
            dataKey={payload.series[0]}
            // An inline style, not the `fill` attribute it looks like it should
            // be. ChartContainer ships shadcn's
            // `[&_.recharts-radial-bar-background-sector]:fill-muted`, and any
            // CSS declaration beats an SVG presentation attribute — so the
            // attribute form was overwritten with the muted grey every time, and
            // no value passed here had ever reached the screen. A style wins.
            background={{ style: { fill: payload.unfilled ?? UNFILLED } }}
            cornerRadius={999}
            fill={arc(drawn[0])}
            // The ring sweeps to each new reading rather than cutting to it:
            // it is the one part of a gauge that says the number is live. How
            // long that takes is `SWEEP_MS`, decided in `chart-marks.ts`
            // beside the radar's, because a board where two things move has to
            // have them move alike.
            animationDuration={SWEEP_MS}
          >
            {/* One cell per ring, so each takes its own colour and its own
                threshold. A single ring needs none — `fill` above is already
                its colour, and adding a Cell would change what today's gauge
                puts in the DOM for no gain. */}
            {rows.length > 1
              ? drawn.map((at) => <Cell key={at} fill={arc(at)} />)
              : null}
          </RadialBar>
        </RadialBarChart>
      </ChartContainer>
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div
          className={cn(
            HOLE,
            band.hole,
            paired ? "items-start" : "items-center",
          )}
        >
          {payload.icon || payload.title ? (
            <span
              className={cn(
                "flex w-full min-w-0 items-center gap-[0.3em] widget-text",
                // Alone in the ring, the word takes the room the icon would
                // have had. Beside one it is sized to sit next to something.
                //
                // And with rings inside rings it takes the smaller size either
                // way, because the hole shrank to make room for them and the
                // type did not: "Machine" in the three-ring hole came out as
                // "Ma…", which names nothing. Measured on the board at 5 by 5,
                // which is the size these actually get used at.
                payload.icon || band.small
                  ? "text-gauge-label"
                  : "text-gauge-label-alone",
                paired ? "justify-start" : "justify-center",
              )}
            >
              {payload.icon ? (
                <span
                  className={cn(
                    "flex shrink-0",
                    // Beside a label the mark matches it; alone it is measured
                    // against the ring instead, so it keeps its share of the
                    // circle at every size the widget is dragged to.
                    payload.title ? undefined : "text-gauge-mark",
                  )}
                >
                  <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
                </span>
              ) : null}
              {payload.title ? (
                <span className="truncate">{payload.title}</span>
              ) : null}
            </span>
          ) : null}
          {reading ? (
            <span
              className={cn(
                "w-full truncate text-gauge-reading text-muted-foreground",
                paired ? "text-left" : "text-center",
              )}
            >
              {reading}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
