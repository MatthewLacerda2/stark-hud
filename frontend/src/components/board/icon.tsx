import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Bug,
  Check,
  Clock,
  Cpu,
  Download,
  Flame,
  GitBranch,
  HardDrive,
  Info,
  Mail,
  MessageSquare,
  Rocket,
  Terminal,
  Upload,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";
import type { ComponentType, CSSProperties } from "react";
import { cn } from "@/lib/utils";

/**
 * The GitHub mark, drawn here because lucide dropped its brand icons.
 *
 * The path is the official one, taken verbatim from simple-icons rather than
 * traced by hand. Sized in `em` like every lucide glyph, so it lines up with
 * the text beside it whatever the widget is scaled to.
 */
function GithubMark({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
      className={className}
      style={style}
    >
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  );
}

/**
 * The Claude mark, drawn here for the same reason the GitHub one is: lucide has
 * no brand icons, and a session announcing itself on this board should be able
 * to say which one it is.
 *
 * The path is the official one, taken verbatim from simple-icons rather than
 * traced by hand.
 */
function ClaudeMark({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
      className={className}
      style={style}
    >
      <path d="m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z" />
    </svg>
  );
}

// A closed set, named the same on both sides. Importing every lucide icon to
// support names nobody picks would cost the whole library in the bundle.
export const NAMED: Record<
  string,
  ComponentType<{ className?: string; style?: CSSProperties }>
> = {
  bell: Bell,
  check: Check,
  info: Info,
  "alert-triangle": AlertTriangle,
  "alert-circle": AlertCircle,
  "x-circle": XCircle,
  terminal: Terminal,
  "git-branch": GitBranch,
  github: GithubMark,
  claude: ClaudeMark,
  download: Download,
  upload: Upload,
  cpu: Cpu,
  "hard-drive": HardDrive,
  mail: Mail,
  "message-square": MessageSquare,
  clock: Clock,
  zap: Zap,
  flame: Flame,
  bug: Bug,
  rocket: Rocket,
  wrench: Wrench,
};

// A picture is given a little more room than a glyph: a photograph cropped to
// the size of a line of text reads as a smudge.
const GLYPH = "size-[1.2em] shrink-0";
const IMAGE = "size-[1.4em] shrink-0 rounded object-cover";
// Markup arrives with whatever `width` and `height` its author gave it, and a
// 24-pixel icon beside text scaled to the widget would be a speck. The rule
// beats the attributes, so the drawing fills the box we give it either way.
const MARKUP = `${GLYPH} inline-block [&>svg]:size-full`;

/** Markup, rather than a name or a path. The three forms are told apart the same
 * way the backend tells them apart, so neither side can drift into the other. */
function isMarkup(name: string): boolean {
  return name.trimStart().startsWith("<svg");
}

/**
 * An icon on a widget: a named glyph, a picture on this machine, or SVG markup.
 *
 * Notifications used to be the only thing that could point at a picture, and
 * every other widget could only name a glyph. There is no reason for that split
 * — an icon is an icon — so all three live here and any widget takes any of them.
 *
 * A picture is fetched by the id of whatever holds it, which is what `src` is
 * for: a filesystem path never appears in a URL.
 *
 * Markup is written into the page as-is, and the only thing that makes that safe
 * is that it was rebuilt from an allowlist in `schemas/svg.py` before it was
 * stored. Nothing is sanitised here — this renders the sanitised value, and the
 * board has no other way for markup to arrive.
 *
 * A glyph is drawn in whatever colour it inherits unless `color` says
 * otherwise, so a caller that lets a widget decide its icons needs no colour at
 * all. Markup follows, as far as it painted itself with `currentColor`. A
 * picture ignores it: a photograph is not tinted by asking.
 */
export function Icon({
  name,
  src,
  fallback: Fallback,
  className,
  color,
}: {
  name: string | null;
  /** Where the picture is served from, when `name` is a path. Markup needs none:
   * it is the icon, not a handle on one. */
  src?: string;
  /** What to draw when nothing was named, for callers that have a default. */
  fallback?: ComponentType<{ className?: string; style?: CSSProperties }>;
  className?: string;
  /** Overrides the colour the glyph would inherit. */
  color?: string;
}) {
  if (name && isMarkup(name)) {
    return (
      <span
        aria-hidden
        className={cn(MARKUP, className)}
        style={color ? { color } : undefined}
        dangerouslySetInnerHTML={{ __html: name }}
      />
    );
  }
  if (name?.startsWith("/") && src) {
    return <img src={src} alt="" className={cn(IMAGE, className)} />;
  }
  const Glyph = (name && NAMED[name]) || Fallback;
  return Glyph ? (
    <Glyph
      className={cn(GLYPH, className)}
      style={color ? { color } : undefined}
    />
  ) : null;
}
