/**
 * The graph half of a flow: which rank each node belongs in, and which link has
 * to be cut for the question to have an answer at all.
 *
 * Split out of `lib/flow.ts` because it is a different subject — there is not a
 * fraction, a widget or an axis anywhere in here, only nodes and the links
 * between them. `flow.ts` turns what this says into boxes.
 */

import type { FlowPayload } from "@/lib/schemas/board";

/**
 * How far down the graph each node sits — longest path, not shortest.
 *
 * Longest, because a node drawn next to one of its own sources is a node with an
 * arrow pointing backwards into it. If `a` leads to both `b` and `c` and `c`
 * also leads to `b`, then `b` belongs after `c` and not beside it.
 *
 * The links that close a cycle are left out of this and drawn anyway — see
 * `forwards`. What is left is acyclic, so this drains and cannot hang.
 */
export function layer(payload: FlowPayload): Map<string, number> {
  const forward = forwards(payload);
  const rank = new Map(payload.nodes.map((node) => [node.id, 0]));
  const owed = new Map(payload.nodes.map((node) => [node.id, 0]));
  for (const targets of forward.values())
    for (const target of targets) owed.set(target, (owed.get(target) ?? 0) + 1);
  // Kahn's order, deepening each target as its last source is settled. `ready`
  // is walked with an index rather than shifted so it stays a plain queue.
  const ready = payload.nodes
    .filter((node) => owed.get(node.id) === 0)
    .map((node) => node.id);
  for (let at = 0; at < ready.length; at++) {
    const here = ready[at];
    for (const next of forward.get(here) ?? []) {
      rank.set(next, Math.max(rank.get(next) ?? 0, (rank.get(here) ?? 0) + 1));
      const left = (owed.get(next) ?? 0) - 1;
      owed.set(next, left);
      if (left === 0) ready.push(next);
    }
  }
  return rank;
}

/**
 * Every link that leads forwards, by source. The ones that close a cycle are
 * left out — a retry loop is an ordinary flow and must neither hang the layering
 * nor vanish from the drawing, so it is cut here and drawn like any other.
 *
 * **Depth-first, from the nodes in the order the payload lists them, following
 * each node's outgoing links in the order the payload lists them.** A link that
 * reaches a node still open on the stack is the one that closes the loop, and it
 * is that link that becomes the arrow pointing back. So the order decides which
 * arrow points back: in `clone -> build -> test -> ship` with a `test -> build`
 * besides, the walk reaches `build` from `clone` first and `test -> build` is
 * the one cut — which is the reading a person would give it too.
 */
function forwards(payload: FlowPayload): Map<string, string[]> {
  const out = new Map<string, string[]>(
    payload.nodes.map((node) => [node.id, []]),
  );
  for (const link of payload.links) out.get(link.source)?.push(link.target);
  const kept = new Map<string, string[]>(
    payload.nodes.map((node) => [node.id, []]),
  );
  const open = new Set<string>();
  const seen = new Set<string>();
  // An explicit stack rather than recursion: this is read on every render of a
  // screen nobody is sitting in front of, and a long enough chain would take the
  // whole board down with it.
  for (const root of payload.nodes) {
    if (seen.has(root.id)) continue;
    const stack = [{ id: root.id, at: 0 }];
    seen.add(root.id);
    open.add(root.id);
    while (stack.length > 0) {
      const top = stack[stack.length - 1];
      const next = (out.get(top.id) ?? [])[top.at++];
      if (next === undefined) {
        open.delete(top.id);
        stack.pop();
      } else if (!open.has(next)) {
        kept.get(top.id)?.push(next);
        if (!seen.has(next)) {
          seen.add(next);
          open.add(next);
          stack.push({ id: next, at: 0 });
        }
      }
    }
  }
  return kept;
}
