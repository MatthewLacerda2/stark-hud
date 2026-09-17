/**
 * The look menu: it lists every dial, shows what the board is drawing with, and
 * gets out of the way.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { LookMenu } from "@/components/board/look-menu";
import { BLOOM_DIALS } from "@/lib/bloom";
import { DEPTH_DIALS } from "@/lib/depth";
import { TAPE_DIALS } from "@/lib/vhs";
import "@/i18n";

const GROUPS = [TAPE_DIALS, BLOOM_DIALS, DEPTH_DIALS];

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

function open(search: string, onClose = vi.fn()) {
  const host = document.createElement("div");
  document.body.append(host);
  act(() => {
    createRoot(host).render(
      <LookMenu
        at={{ x: 10, y: 10 }}
        groups={GROUPS}
        search={search}
        onTurn={vi.fn()}
        onReset={vi.fn()}
        onClose={onClose}
      />,
    );
  });
  return host;
}

describe("the look menu", () => {
  it("has a row for every dial of every look", () => {
    const rows = open("").querySelectorAll("label");
    const dials = GROUPS.reduce((n, group) => n + 1 + group.parts.length, 0);
    expect(rows).toHaveLength(dials);
  });

  it("shows what the board is actually drawing with", () => {
    const text = open("?bloom=0.6").textContent ?? "";
    expect(text).toContain("0.60");
  });

  it("shuts on Escape", () => {
    const onClose = vi.fn();
    open("", onClose);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("shuts on a press outside it, and not on one inside", () => {
    const onClose = vi.fn();
    const host = open("", onClose);
    act(() => {
      host
        .querySelector("label")!
        .dispatchEvent(new Event("pointerdown", { bubbles: true }));
    });
    expect(onClose).not.toHaveBeenCalled();
    act(() => {
      document.body.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    });
    expect(onClose).toHaveBeenCalled();
  });
});
