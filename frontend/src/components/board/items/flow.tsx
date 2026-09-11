import { useTranslation } from "react-i18next";
import type { FlowLink, FlowNode, FlowPayload } from "@/lib/schemas/board";
import { Icon } from "@/components/board/icon";
import { useContainerSize } from "@/hooks/use-container-size";
import { carriesAlpha } from "@/lib/colour";
import type { Box, Point, Route } from "@/lib/flow";
import { arrows, cells, layout, midpoint, roomy } from "@/lib/flow";

/**
 * How solid a box's interior is when its colour did not say.
 *
 * *Wash areas, never marks.* A box is an area, so its fill is a wash and the
 * board's video goes on moving behind it — a pane of smoked glass. Its outline
 * and its word are marks and are drawn at full strength on top, in their own
 * layer, so turning the glass down does not take the word down with it. A
 * colour that states its own alpha has already answered this.
 */
const WASH = 0.28;

/**
 * The house line weight, as a fraction of the widget's shorter side.
 *
 * One weight for the whole widget: an outline and an arrow are the same ink and
 * a diagram drawn in two thicknesses reads as two diagrams. Against the shorter
 * side because a line has no axis of its own and needs one chosen for it — the
 * same call `scorsese_core::shape` makes for `stroke_width`, and picking the
 * same one twice is one fewer thing to remember.
 */
const STROKE = 1 / 70;

/** The thinnest a line may get. Below a pixel a browser draws a ghost of one. */
const MIN_STROKE = 1.6;

/** How long a head is, and how far its base spreads, as multiples of the line. */
const HEAD_LENGTH = 4.2;
const HEAD_SPREAD = 1.7;

/** How far a label sits off its arrow, as a multiple of the line's thickness. */
const LABEL_LIFT = 2.6;

/**
 * A diagram of boxes and arrows: *this leads to that*.
 *
 * The one thing no other widget on this board can say. A deployment, a morning
 * routine, the shape of a pipeline, a decision with two ways out.
 *
 * **No card.** `mesh.tsx` is the precedent: this returns bare content and never
 * writes `widget-surface`, which is applied per widget rather than by
 * `board-grid.tsx`. A flow's boxes are panes of glass on the board itself, so
 * the background video runs *between* them and not only around the whole thing.
 * A title and an icon are content the way a gantt's are; a flow with neither
 * draws no chrome at all, which is what a diagram usually wants.
 *
 * Nothing here is interactive: no click, no hover, no selection, no per-box
 * handle. The television has no pointer and the sofa has no keyboard. The
 * widget drags as a widget, the way every widget does; its insides do not.
 *
 * Clipped, never scrolled — nobody can scroll this screen.
 */
export function Flow({
  id,
  payload,
  cols,
  rows,
}: {
  id: string;
  payload: FlowPayload;
  /** How many cells the widget spans. They decide which side is the longer one
   * for an unplaced flow, and how long an arrow really is when a label asks. */
  cols: number;
  rows: number;
}) {
  const { t } = useTranslation();
  // Real pixels, for the two things fractions cannot express: a head that is
  // not stretched by the widget's aspect, and a corner radius that stays
  // circular. A viewBox of 0..1 with `preserveAspectRatio: none` would distort
  // both, which is the classic bug in this feature.
  const { ref, width, height } = useContainerSize();
  const laid = layout(payload, cols, rows);
  const stroke = Math.max(MIN_STROKE, Math.min(width, height) * STROKE);

  return (
    <div ref={ref} className="relative size-full overflow-hidden widget-text">
      {payload.title || payload.icon ? (
        <h3 className="absolute inset-x-0 top-0 z-10 flex items-center gap-2 truncate text-node font-semibold tracking-tight">
          <Icon name={payload.icon} src={`/api/v1/media/${id}/icon`} />
          {payload.title}
        </h3>
      ) : null}
      {payload.nodes.map((node) => (
        <Node
          key={node.id}
          node={node}
          box={laid.boxes.get(node.id)}
          width={width}
          height={height}
          stroke={stroke}
        />
      ))}
      {/* One layer over every box, because an arrow is a mark and a box is an
          area: the mark goes on top. An arrow told to meet a `center` crosses
          its box for exactly that reason, which is what naming `center` asks
          for. */}
      {width > 0 ? (
        <svg
          className="pointer-events-none absolute inset-0 size-full"
          viewBox={`0 0 ${width} ${height}`}
          aria-hidden
        >
          {arrows(payload, laid).map(({ link, run }) => (
            <Arrow
              // A pair is unique — the backend refuses two arrows between the
              // same two boxes — and the separator is a byte no id can hold,
              // so 'a b' to 'c' and 'a' to 'b c' stay two different keys.
              key={`${link.source}\u0000${link.target}`}
              link={link}
              run={run}
              width={width}
              height={height}
              cols={cols}
              rows={rows}
              stroke={stroke}
            />
          ))}
        </svg>
      ) : null}
      {payload.nodes.length === 0 ? (
        <p className="text-node-sm opacity-60 italic">{t("flow.empty")}</p>
      ) : null}
    </div>
  );
}

/** One box, as a pane of glass with a word on it. */
function Node({
  node,
  box,
  width,
  height,
  stroke,
}: {
  node: FlowNode;
  box: Box | undefined;
  width: number;
  height: number;
  stroke: number;
}) {
  if (!box) return null;
  const colour = node.color ?? "currentColor";
  // A fraction of the box's own shorter side, worked out in pixels. A CSS
  // percentage is taken per axis, which on an oblong box gives elliptical
  // corners rather than round ones — the very thing the radius was defined
  // against the shorter side to avoid.
  const corner =
    node.shape === "ellipse"
      ? "50%"
      : `${node.radius * Math.min(box.w * width, box.h * height)}px`;

  return (
    <div
      className="absolute flex items-center justify-center overflow-hidden px-[1.5cqmin] text-center"
      style={{
        left: `${box.x * 100}%`,
        top: `${box.y * 100}%`,
        width: `${box.w * 100}%`,
        height: `${box.h * 100}%`,
        borderRadius: corner,
        border: `${stroke}px solid ${colour}`,
      }}
    >
      {/* The wash is its own layer, so turning the glass down does not take the
          word down with it. `opacity` on the box itself would fade both. */}
      <div
        className="absolute inset-0"
        style={{
          background: colour,
          opacity: carriesAlpha(colour) ? 1 : WASH,
        }}
      />
      <span className="relative text-node-sm leading-tight break-words">
        {node.text}
      </span>
    </div>
  );
}

/** One arrow: the line, the heads that say which way it goes, and its word. */
function Arrow({
  link,
  run,
  width,
  height,
  cols,
  rows,
  stroke,
}: {
  link: FlowLink;
  run: Route;
  width: number;
  height: number;
  cols: number;
  rows: number;
  stroke: number;
}) {
  const colour = link.color ?? "currentColor";
  const px = (at: Point) => ({ x: at.x * width, y: at.y * height });
  const start = px(run.start);
  const end = px(run.end);
  const path =
    run.control === null
      ? `M ${start.x} ${start.y} L ${end.x} ${end.y}`
      : `M ${start.x} ${start.y} C ${run.control.map((c) => `${px(c).x} ${px(c).y}`).join(" ")} ${end.x} ${end.y}`;
  // A direction is not a place, so it is scaled by the same two factors and
  // then made a unit again — otherwise a head on a wide widget aims along a
  // stretched version of the line it sits on.
  const aim = (of: Point) => steer(of.x * width, of.y * height);
  const along = cells(run.start, run.end, cols, rows);

  return (
    <g stroke={colour} fill={colour} strokeWidth={stroke}>
      <path d={path} fill="none" strokeLinecap="round" />
      {link.heads !== "none" ? (
        <Head at={end} aim={aim(run.atEnd)} thick={stroke} />
      ) : null}
      {link.heads === "both" ? (
        <Head at={start} aim={back(aim(run.atStart))} thick={stroke} />
      ) : null}
      {link.label && roomy(link.label, along) ? (
        <Label at={px(midpoint(run))} aim={aim(run.atEnd)} thick={stroke}>
          {link.label}
        </Label>
      ) : null}
    </g>
  );
}

/** One triangular head, tip on the endpoint and pointing along the curve.
 *
 * Along the curve's tangent and not along the straight line between the ends:
 * on a bowed arrow those differ by a visible angle, and a head aimed at the
 * wrong one looks like a mistake in the diagram rather than in the renderer. */
function Head({ at, aim, thick }: { at: Point; aim: Point; thick: number }) {
  const length = thick * HEAD_LENGTH;
  const spread = thick * HEAD_SPREAD;
  const base = { x: at.x - aim.x * length, y: at.y - aim.y * length };
  const side = { x: -aim.y * spread, y: aim.x * spread };
  const corners = [
    `${at.x},${at.y}`,
    `${base.x + side.x},${base.y + side.y}`,
    `${base.x - side.x},${base.y - side.y}`,
  ];
  return <polygon points={corners.join(" ")} stroke="none" />;
}

/** A word beside its arrow, never on it and never rotated with it.
 *
 * Off the line rather than over it, because the alternative is a plate of
 * background behind the word — chrome, on a widget whose whole look is the
 * video showing through. Horizontal whatever the arrow is doing: text turned
 * on its side is not read from a sofa, it is noticed. */
function Label({
  at,
  aim,
  thick,
  children,
}: {
  at: Point;
  aim: Point;
  thick: number;
  children: string;
}) {
  const lift = thick * LABEL_LIFT;
  return (
    <text
      x={at.x - aim.y * lift}
      y={at.y + aim.x * lift}
      textAnchor="middle"
      dominantBaseline="middle"
      stroke="none"
      className="text-node-sm"
    >
      {children}
    </text>
  );
}

/** The other way along a direction. A head at the start points back the way the
 * line came, so its direction is the leaving tangent reversed. */
function back(of: Point): Point {
  return { x: -of.x, y: -of.y };
}

/** A direction of length one, or a rightward one when there is no direction. */
function steer(dx: number, dy: number): Point {
  const length = Math.hypot(dx, dy);
  if (!Number.isFinite(length) || length <= 0) return { x: 1, y: 0 };
  return { x: dx / length, y: dy / length };
}
