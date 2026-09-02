/**
 * A widget acknowledging work that has not arrived yet.
 *
 * The two ways it ends are the point of the test. A session that writes what it
 * promised releases it, and a session that dies mid-thought does not: the board
 * is a television left running in a dim room, so anything that can be left lit
 * will eventually be left lit all night.
 *
 * jsdom runs no animations, so what is checked here is the state machine and
 * the classes it hands the stylesheet — the breath and the fade are CSS.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { WidgetWake } from "@/components/board/widget-wake";

const HOLD_MS = 11_000;
const SETTLE_MS = 520;

const mounted: Root[] = [];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(async () => {
  await act(async () => {
    mounted.forEach((root) => root.unmount());
  });
  mounted.length = 0;
  vi.useRealTimers();
});

async function wake() {
  vi.useFakeTimers();
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  mounted.push(root);

  const told = async (nonce: number) => {
    await act(async () => {
      root.render(<WidgetWake nonce={nonce} />);
    });
  };
  const after = async (ms: number) => {
    await act(async () => {
      vi.advanceTimersByTime(ms);
    });
  };
  /** What the widget is showing: nothing, the stroke, or the stroke leaving. */
  const showing = () => host.querySelector("div")?.dataset.wake ?? "nothing";
  return { told, after, showing };
}

describe("a widget told work is coming", () => {
  it("shows nothing until somebody says so", async () => {
    const { told, showing } = await wake();
    await told(0);

    expect(showing()).toBe("nothing");
  });

  it("acknowledges the moment it is told, with nothing written yet", async () => {
    const { told, showing } = await wake();
    await told(1);

    expect(showing()).toBe("awake");
  });

  it("settles by itself when the write never comes", async () => {
    const { told, after, showing } = await wake();
    await told(1);

    await after(HOLD_MS);
    expect(showing()).toBe("settling");
    await after(SETTLE_MS);
    expect(showing()).toBe("nothing");
  });

  it("holds again when the work runs long and it is woken twice", async () => {
    const { told, after, showing } = await wake();
    await told(1);
    await after(HOLD_MS - 1000);
    await told(2);

    // On the first wake's timer this would already be leaving.
    await after(1000);
    expect(showing()).toBe("awake");
  });

  it("releases into the answer when the write lands, and rests there", async () => {
    const { told, after, showing } = await wake();
    await told(1);
    await after(3000);

    // The write arriving is the wake going away: the board drops it from
    // `wakes`, so the count this widget is handed falls back to zero.
    await told(0);
    expect(showing()).toBe("settling");
    await after(SETTLE_MS);
    expect(showing()).toBe("nothing");

    // And it stays resting: no timer left over to light it again.
    await after(HOLD_MS);
    expect(showing()).toBe("nothing");
  });
});
