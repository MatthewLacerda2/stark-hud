// Whole class names, never built by interpolation: Tailwind reads the source as
// text, and a utility it cannot see spelled out is a utility it never emits.
const WALLS = [
  "glass-wall glass-wall-n",
  "glass-wall glass-wall-s",
  "glass-wall glass-wall-e",
  "glass-wall glass-wall-w",
];

/**
 * A widget as a pane of glass: a face, and four walls running back from it.
 *
 * The face sits where the widget always was, so nothing about its size or place
 * changes, and the walls go *behind* it rather than lifting it forward — a pane
 * lifted towards the camera grows, and grown panes would close the gutters
 * between them. Looked at straight on, a wall is edge-on and is nothing. Lean
 * the board and they open, and that opening is most of what makes the pane read
 * as an object.
 *
 * Drawn first inside the widget, so what the widget draws lands on the glass
 * rather than under it. Everything here is decoration and nothing is hit: a
 * pointer goes straight through to the widget.
 */
export function Slab() {
  return (
    <>
      {WALLS.map((wall) => (
        <div key={wall} aria-hidden className={wall} />
      ))}
      <div aria-hidden className="glass-face" />
    </>
  );
}
