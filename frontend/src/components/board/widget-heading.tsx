import { Icon } from "@/components/board/icon";
import { iconUrl } from "@/lib/api/media";
import { cn } from "@/lib/utils";

/**
 * How a widget introduces itself: an icon, a title, or the two of them.
 *
 * This was written out again in six widgets, which meant six copies of one
 * decision and six chances to miss one. It is one decision, so it lives here.
 *
 * The decision itself is the board's rule about chrome: the heading is what the
 * widget *says*, never a handle for grabbing it or a place to hang its name. So
 * there is nothing here but the icon and the title, and when a widget has
 * neither there is no heading at all — not an empty band holding its height.
 *
 * `className` is for where the heading sits, not for what it looks like: the
 * flow puts it over the diagram, the gantt lets it truncate. A caller that
 * reaches for a font or a colour through it is answering a question this
 * component is supposed to have already answered.
 *
 * The icon is fetched by the widget's id — a filesystem path never appears in a
 * URL — and the colours are the ones the widget was given, which is why they
 * arrive as `null` rather than as absent.
 */
export function WidgetHeading({
  id,
  icon,
  iconColor,
  title,
  titleColor,
  className,
}: {
  /** The widget's id, which is how its icon is addressed. */
  id: string;
  icon: string | null;
  iconColor?: string | null;
  title?: string | null;
  titleColor?: string | null;
  /** Where it sits. Not what it looks like. */
  className?: string;
}) {
  if (!icon && !title) return null;
  return (
    <h3
      className={cn(
        "flex shrink-0 items-center gap-2 text-node font-semibold tracking-tight",
        className,
      )}
      style={titleColor ? { color: titleColor } : undefined}
    >
      <Icon name={icon} src={iconUrl(id)} color={iconColor ?? undefined} />
      {title}
    </h3>
  );
}
