import {
  BarChart3,
  Clock,
  Disc3,
  FileImage,
  Film,
  Inbox,
  List,
  Rss,
  Square,
  StickyNote,
  Timer,
  Type,
} from "lucide-react";
import type { ComponentType, CSSProperties } from "react";
import { cn } from "@/lib/utils";
import type { ItemKind } from "@/lib/schemas/board";

/**
 * What a kind of widget looks like when you cannot see the widget.
 *
 * A folded group draws these instead of what it holds, so this is the only
 * place a widget kind is drawn rather than rendered. A small closed set on
 * purpose: there are not many kinds, and one shape per kind is what makes a
 * shelf of them readable from across a room.
 */
const GLYPH: Record<
  ItemKind,
  ComponentType<{ className?: string; style?: CSSProperties }>
> = {
  note: StickyNote,
  text: Type,
  list: List,
  box: Square,
  image: FileImage,
  video: Film,
  media: Disc3,
  chart: BarChart3,
  inbox: Inbox,
  clock: Clock,
  countdown: Timer,
  feed: Rss,
  // A group never holds a group, so this is only ever the fallback a folded
  // group draws for itself when it is holding nothing at all.
  group: Square,
};

/** The glyph standing for a kind of widget. */
export function KindIcon({
  kind,
  className,
}: {
  kind: ItemKind;
  className?: string;
}) {
  const Glyph = GLYPH[kind];
  return <Glyph className={cn("size-full", className)} aria-hidden />;
}
