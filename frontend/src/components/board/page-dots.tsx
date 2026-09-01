/**
 * Which page the board is on, and a way to change it.
 *
 * Only drawn when there is more than one page: a single dot says nothing, and
 * on a TV that nobody touches, chrome that says nothing is noise.
 */
export function PageDots({
  page,
  pages,
  onPick,
}: {
  page: number;
  pages: number;
  onPick: (page: number) => void;
}) {
  if (pages < 2) return null;

  return (
    <div className="pointer-events-auto absolute inset-x-0 bottom-2 flex justify-center gap-2">
      {Array.from({ length: pages }, (_, i) => (
        <button
          key={i}
          type="button"
          aria-label={`Page ${i + 1}`}
          aria-current={i === page}
          onClick={() => onPick(i)}
          className={`size-2 rounded-full transition-opacity ${
            i === page ? "bg-foreground opacity-90" : "bg-foreground opacity-30"
          }`}
        />
      ))}
    </div>
  );
}
