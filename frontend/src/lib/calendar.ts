/**
 * How a month lays out on a grid, and what its columns are called.
 *
 * Kept out of the component for the reason `lib/gantt.ts` is: this is
 * arithmetic about a calendar rather than about how one is drawn, and
 * arithmetic is worth testing without a DOM to hang it in.
 *
 * Weeks start on Sunday. `Date.getDay()` is already Sunday-relative, so that is
 * the week this needs no code at all to produce — a Monday-first board would.
 */

/** One cell of the grid: a day of this month, or a blank before the 1st. */
export type Day = number | null;

/** A month, shaped for a seven-column grid. */
export interface Month {
  /** Sunday-first, blanks first, one entry per cell that gets drawn. */
  days: Day[];
  /** Weeks spanned, so the grid can divide the widget's height by it. */
  weeks: number;
}

/** The month `when` falls in, as the cells to draw. */
export function monthOf(when: Date): Month {
  const year = when.getFullYear();
  const month = when.getMonth();
  const blank = new Date(year, month, 1).getDay();
  // Day zero of the next month is the last day of this one, which is the whole
  // of the leap-year question and none of the arithmetic.
  const length = new Date(year, month + 1, 0).getDate();

  const days: Day[] = Array.from({ length: blank }, () => null);
  for (let day = 1; day <= length; day += 1) days.push(day);

  // No trailing blanks. A grid stops where its cells stop, and padding the last
  // week would only add empty boxes indistinguishable from the ones before the
  // 1st — which are there to push the 1st onto the right weekday and have a job.
  return { days, weeks: Math.ceil((blank + length) / 7) };
}

/**
 * The seven weekday initials, in whatever language the board is in.
 *
 * Taken from `Intl` rather than a table here, so the letters follow the board
 * wherever its language goes — S M T W T F S in English, D S T Q Q S S in
 * Portuguese — instead of seven more strings to keep in step in every locale
 * file, in an alphabet whoever adds the next locale may not read.
 */
export function initials(locale: string): string[] {
  const narrow = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
  // 1 January 2023 was a Sunday, which is where this board's week starts.
  return Array.from({ length: 7 }, (_, at) =>
    narrow.format(new Date(2023, 0, 1 + at)),
  );
}
