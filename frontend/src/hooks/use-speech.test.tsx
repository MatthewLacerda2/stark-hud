/**
 * What the room hears when the board is told to say something.
 *
 * jsdom implements no media playback at all — `play` makes no sound and no
 * event ever fires by itself — so `Audio` is replaced with one that records
 * what it was asked to play and lets a test end it by hand. That is the only
 * honest way to ask the two questions worth asking here: that a line is played
 * from the URL the server sent, and that two lines arriving together are said
 * one after the other rather than on top of each other.
 */
import { act, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import type { Spoken } from "@/lib/schemas/board";
import { useSpeech } from "@/hooks/use-speech";
import { unduck, useDucked } from "@/lib/ducking";

/** Every player the hook has built, in the order it built them. */
let players: FakeAudio[] = [];

/** As much of an audio element as the hook ever touches. */
class FakeAudio {
  src: string;
  playing = false;
  private listeners = new Map<string, (() => void)[]>();

  constructor(src: string) {
    this.src = src;
    players.push(this);
  }

  addEventListener(name: string, handler: () => void): void {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), handler]);
  }

  play(): Promise<void> {
    this.playing = true;
    return Promise.resolve();
  }

  /** End the track, the way a real element does when it runs out. */
  finish(): void {
    this.playing = false;
    for (const handler of this.listeners.get("ended") ?? []) handler();
  }

  /** Fail it, the way one does when the file has already been deleted. */
  fail(): void {
    for (const handler of this.listeners.get("error") ?? []) handler();
  }
}

function line(id: string): Spoken {
  return {
    id,
    text: id,
    url: `/api/v1/speech/${id}`,
    created_at: "2026-09-02T12:00:00Z",
  };
}

const mounted: Root[] = [];

function Speaker({ lines }: { lines: Spoken[] }) {
  useSpeech(lines);
  return null;
}

function render(lines: Spoken[]): (next: Spoken[]) => void {
  const host = document.createElement("div");
  const root = createRoot(host);
  mounted.push(root);
  act(() => root.render(<Speaker lines={lines} />));
  return (next) => act(() => root.render(<Speaker lines={next} />));
}

beforeAll(() => {
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  globalThis.Audio = FakeAudio as unknown as typeof Audio;
});

beforeEach(() => {
  players = [];
});

afterEach(() => {
  act(() => mounted.forEach((root) => root.unmount()));
  mounted.length = 0;
});

describe("the board's voice", () => {
  it("plays a line from the URL the server sent", () => {
    render([line("a")]);
    expect(players).toHaveLength(1);
    expect(players[0].src).toBe("/api/v1/speech/a");
    expect(players[0].playing).toBe(true);
  });

  it("says two lines one after the other, not on top of each other", () => {
    const update = render([line("a")]);
    update([line("a"), line("b")]);

    // The second is waiting, not playing: overlapping them would make both
    // unintelligible, and nobody at the television can ask for a replay.
    expect(players).toHaveLength(1);
    act(() => players[0].finish());
    expect(players).toHaveLength(2);
    expect(players[1].src).toBe("/api/v1/speech/b");
  });

  it("moves on when a line will not play at all", () => {
    const update = render([line("a")]);
    update([line("a"), line("b")]);
    act(() => players[0].fail());
    // One line the board has already deleted must not leave it mute all evening.
    expect(players).toHaveLength(2);
  });

  it("never says the same line twice", () => {
    const update = render([line("a")]);
    act(() => players[0].finish());
    update([line("a")]);
    expect(players).toHaveLength(1);
  });
});

/**
 * What the music is being told while the board talks.
 *
 * The rule is not "quieter for each line" but "quieter for as long as there is
 * talking", so what these tests watch is every value the widget was handed, not
 * only the one it ended on: a run that dipped back up between two sentences and
 * down again would end in the right place having done the wrong thing.
 */
function Music({ heard }: { heard: boolean[] }) {
  const ducked = useDucked();
  useEffect(() => {
    heard.push(ducked);
  }, [ducked, heard]);
  return null;
}

function speakOver(lines: Spoken[]): {
  heard: boolean[];
  update: (next: Spoken[]) => void;
} {
  const heard: boolean[] = [];
  const host = document.createElement("div");
  const root = createRoot(host);
  mounted.push(root);
  const draw = (next: Spoken[]) => (
    <>
      <Music heard={heard} />
      <Speaker lines={next} />
    </>
  );
  act(() => root.render(draw(lines)));
  return { heard, update: (next) => act(() => root.render(draw(next))) };
}

describe("music while the board is talking", () => {
  // The rule is one value for the whole page, so it outlives a test that left
  // the board mid-sentence. Put it back, or the next test starts quiet.
  afterEach(unduck);

  it("steps back the moment there is something to say", () => {
    const { heard } = speakOver([line("a")]);
    expect(heard.at(-1)).toBe(true);
  });

  it("comes back once the last line has been said", () => {
    const { heard } = speakOver([line("a")]);
    act(() => players[0].finish());
    expect(heard.at(-1)).toBe(false);
  });

  it("stays back between two lines rather than pumping between them", () => {
    const { heard, update } = speakOver([line("a")]);
    update([line("a"), line("b")]);
    act(() => players[0].finish());

    expect(players).toHaveLength(2);
    // Once down, and still down. A song that came back up for the gap between
    // two sentences would be more distracting than either level on its own.
    expect(heard.filter((quiet) => quiet === false)).toHaveLength(1);
    expect(heard.at(-1)).toBe(true);
  });

  it("comes back when the line failed rather than ended", () => {
    const { heard } = speakOver([line("a")]);
    act(() => players[0].fail());
    // A file the board has already deleted must not leave the music quiet for
    // the rest of the evening.
    expect(heard.at(-1)).toBe(false);
  });

  it("is left alone when there is nothing to say", () => {
    const { heard } = speakOver([]);
    expect(heard).toEqual([false]);
  });
});
