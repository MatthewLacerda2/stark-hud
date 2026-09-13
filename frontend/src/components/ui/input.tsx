import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A single line of text somebody types.
 *
 * The first one in this project, because until now nothing on this board took
 * typing: the television has no keyboard and every widget is read, not filled
 * in. It exists so `no-hand-rolled-form-control` has something to point at —
 * the rule is what stops a second, slightly different input appearing the next
 * time somebody needs one.
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "min-w-0 flex-1 bg-transparent text-h3 text-foreground outline-none",
        "placeholder:text-muted-foreground disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
