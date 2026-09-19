/**
 * The card a chart is drawn on.
 *
 * shadcn's card ships a background of its own, and no widget on this board has
 * one: every widget sits straight on the video. It shipped once with the card's
 * colour showing, when the class that used to cover it was removed.
 */
import { describe, expect, it } from "vitest";
import {
  BARS,
  render,
  stubLayout,
} from "@/components/board/items/chart-render";

stubLayout();

describe("a chart's card", () => {
  it.each(["bar", "radial", "radar"] as const)(
    "has no background on a %s chart",
    async (chart) => {
      const host = await render({ ...BARS, chart });
      const card = host.querySelector('[data-slot="card"]');
      const classes = card?.className.split(/\s+/);
      expect(classes).toContain("bg-transparent");
      expect(classes).not.toContain("bg-card");
    },
  );
});
