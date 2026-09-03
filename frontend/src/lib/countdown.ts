import type { Countdown } from "@/lib/schemas/board";

/**
 * Reading a countdown: which band it is in, what order they go in, and the two
 * strings a row draws.
 *
 * All of it is a function of the entry and the current time, and none of it is
 * stored. The board keeps the datetimes because those are facts a browser
 * cannot know; how long is left is a reading, and this is where it is taken.
 *
 * No React and no DOM, so the arithmetic can be tested without a browser —
 * which is the standing lesson of #42, where the sums were right the whole time
 * and nothing tested the wiring. Both are tested here.
 */

const HALF_MINUTE = 30_000;
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** How long a finished thing stays on the board before it stops being drawn. */
export const KEEP_MS = 12 * HOUR;

/** Where an entry is in its own life. The order here is the order on screen. */
export type Phase = "happening" | "ahead" | "over";

/** When a thing is over: its end, or its start when it is a moment. */
function finish(entry: Countdown): number {
  return new Date(entry.end ?? entry.start).getTime();
}

export function phaseOf(entry: Countdown, now: number): Phase {
  if (now < new Date(entry.start).getTime()) return "ahead";
  return now < finish(entry) ? "happening" : "over";
}

/** The moment the clock is counting to: the start, or the end once it has begun. */
export function target(entry: Countdown, now: number): number {
  const start = new Date(entry.start).getTime();
  return now < start ? start : finish(entry);
}

const BANDS: Record<Phase, number> = { happening: 0, ahead: 1, over: 2 };

/**
 * What to draw, in the order to draw it.
 *
 * What is happening comes before what is still to happen, which comes before
 * what is over — because a widget dragged shorter loses rows off the bottom,
 * and the ones that survive should be the ones that matter.
 *
 * Within a band the nearest deadline leads, except among the finished, where
 * the most recently finished leads: the freshest is the one still worth a
 * glance. Anything finished longer ago than `KEEP_MS` is not drawn at all.
 */
export function ordered(entries: Countdown[], now: number): Countdown[] {
  return entries
    .filter((entry) => now - finish(entry) < KEEP_MS)
    .map((entry) => ({ entry, phase: phaseOf(entry, now) }))
    .sort((a, b) => {
      if (a.phase !== b.phase) return BANDS[a.phase] - BANDS[b.phase];
      const first = target(a.entry, now);
      const second = target(b.entry, now);
      return a.phase === "over" ? second - first : first - second;
    })
    .map(({ entry }) => entry);
}

function pad(value: number): string {
  return String(Math.floor(value)).padStart(2, "0");
}

/**
 * How long is left, as the widget says it.
 *
 * `HH:MM` normally, a leading `Nd` past a day, and `M:SS` inside the last
 * minute — seconds are noise on a screen nobody is standing at until they are
 * the only thing left to say. Nothing at all once it is over: there is no
 * reading to take, and the row goes quiet rather than showing a zero.
 */
export function remaining(entry: Countdown, now: number): string | null {
  const left = target(entry, now) - now;
  if (left <= 0) return null;
  if (left < MINUTE) return `0:${pad(left / 1000)}`;
  if (left < DAY) return `${pad(left / HOUR)}:${pad((left % HOUR) / MINUTE)}`;
  return `${Math.floor(left / DAY)}d ${pad((left % DAY) / HOUR)}:${pad((left % HOUR) / MINUTE)}`;
}

/**
 * Whether these have to be redrawn every second rather than every half minute.
 *
 * A minute and a half, not a minute: the slow tick is thirty seconds wide, so
 * asking exactly at the minute could arrive a tick late and the seconds would
 * start somewhere short of sixty. The switch has to happen before it matters.
 */
export function ticking(entries: Countdown[], now: number): boolean {
  return entries.some((entry) => {
    const left = target(entry, now) - now;
    return left > 0 && left < MINUTE + HALF_MINUTE;
  });
}

/**
 * A clock time, with the date in front of it when it is not today's.
 *
 * 24-hour, matching `lib/when.ts`, which chose it because two clock conventions
 * on one screen is worse than either.
 */
export function at(iso: string, now: number): string {
  const when = new Date(iso);
  const clock = when.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const today = new Date(now);
  const sameDay =
    when.getFullYear() === today.getFullYear() &&
    when.getMonth() === today.getMonth() &&
    when.getDate() === today.getDate();
  if (sameDay) return clock;
  const day = when.toLocaleDateString(undefined, { weekday: "short" });
  return `${day} ${clock}`;
}
