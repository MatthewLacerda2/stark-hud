"""The MCP tool for progress bars."""

from typing import cast, get_args

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import IconSide, ProgressPayload

SIDES: tuple[str, ...] = get_args(IconSide)


def register(server: MCPServer) -> None:
    """Attach the progress tool to the server."""

    @server.tool()
    async def add_progress(
        value: float,
        max: float = 100,
        min: float = 0,
        title: str | None = None,
        icon: str | None = None,
        icon_side: str = "start",
        min_label: str | None = None,
        max_label: str | None = None,
        color: str | None = None,
        unfilled: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        description: str | None = None,
    ) -> str:
        """Draw how far along something is, as a bar filling from left to right.

        A gauge laid flat, for a strip of board too short for a ring: a bar
        reads at one row and a bit tall. `value` sits between `min` and `max`;
        one outside them draws empty or full rather than being refused.

        The ends say where the bar is going, not where it is — the fill already
        says that. The right end shows `max`, and the left shows `min` only when
        it is not zero. `min_label` and `max_label` replace either number with
        text ("Friday", "67M tokens"); an empty string hides it.

        `title` sits above the bar and `icon` beside it, at the `start` or the
        `end` (start unless told). Both are optional, and whatever is left out
        gives its room to the bar.

        `color` is the fill, translucent white unless told otherwise; `unfilled`
        is the rest of the track, a fainter white — keep it translucent.

        To update it, write it again: as a panel by key, which is how something
        that keeps a bar moving should do it.
        """
        if icon_side not in SIDES:
            return f"Not added: icon_side must be start or end (got {icon_side!r})"
        try:
            payload = ProgressPayload(
                value=value,
                min=min,
                max=max,
                title=title,
                icon=icon,
                icon_side=cast(IconSide, icon_side),
                min_label=min_label,
                max_label=max_label,
                color=color,
                unfilled=unfilled,
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)
