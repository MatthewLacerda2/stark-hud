"""MCP tools that put things on the board."""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import (
    BoxPayload,
    ChartPayload,
    ImagePayload,
    NotePayload,
    NotificationPayload,
    TextPayload,
    VideoPayload,
)


def register(server: MCPServer) -> None:
    """Attach the content tools to the server."""

    @server.tool()
    async def add_note(
        text: str,
        color: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
    ) -> str:
        """Put a sticky note on the board.

        Omit x and y and the board picks a free slot; omit w and h for a default
        size. Coordinates are grid cells (the grid is 12x8), never pixels.

        Leave `color` alone unless asked. The board is a TV in a dim room, so
        tiles are dark by convention — a pale note is a lamp pointed at whoever
        is watching, and white text on it is unreadable.
        """
        return await add(NotePayload(text=text, color=color), x, y, w, h)

    @server.tool()
    async def add_text(
        text: str,
        size: str = "md",
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
    ) -> str:
        """Put bare text on the board, with no card behind it.

        Size is one of sm, md, lg, xl. Use lg or xl for something meant to be
        read from across the room.
        """
        if size not in {"sm", "md", "lg", "xl"}:
            return f"Not added: size must be sm, md, lg or xl (got {size!r})"
        return await add(TextPayload(text=text, size=size), x, y, w, h)

    @server.tool()
    async def add_box(
        label: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
    ) -> str:
        """Put a labelled container on the board.

        Other items can name it as their parent with set_parent. Colours are CSS
        strings; leave them out to use the theme.
        """
        return await add(BoxPayload(label=label, fill=fill, stroke=stroke), x, y, w, h)

    @server.tool()
    async def add_image(
        path: str,
        alt: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        parent_id: str | None = None,
    ) -> str:
        """Show a local image file.

        The path must exist on the machine running the board. If the file later
        moves, the tile shows a "file not found" placeholder instead of breaking.
        """
        return await add(ImagePayload(path=path, alt=alt), x, y, w, h, parent_id)

    @server.tool()
    async def add_video(
        path: str,
        autoplay: bool = True,
        loop: bool = False,
        muted: bool = True,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        parent_id: str | None = None,
    ) -> str:
        """Show a local video file.

        Muted by default: several tiles playing sound at once is unusable. Only
        unmute when the video is the point of the board right now.
        """
        payload = VideoPayload(path=path, autoplay=autoplay, loop=loop, muted=muted)
        return await add(payload, x, y, w, h, parent_id)

    @server.tool()
    async def add_chart(
        chart: str,
        data: list[dict[str, float | int | str]],
        x_key: str,
        series: list[str],
        title: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
    ) -> str:
        """Draw a chart from data you supply inline.

        The board never fetches or polls: send the numbers. `chart` is line, bar,
        pie or area. `x_key` names the field on the x axis and `series` names the
        fields to plot. To update a chart, remove it and add it again.
        """
        if chart not in {"line", "bar", "pie", "area"}:
            return f"Not added: chart must be line, bar, pie or area (got {chart!r})"
        payload = ChartPayload(chart=chart, data=data, x_key=x_key, series=series, title=title)
        return await add(payload, x, y, w, h)

    @server.tool()
    async def notify(
        message: str,
        level: str = "info",
        source: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
    ) -> str:
        """Announce something on the board.

        The notice stays until someone removes it, so several finished sessions
        can pile up and be read in one glance. Level is info, success, warn or
        error. Put your session or project name in `source` so a human can tell
        which of several Claudes is talking.
        """
        if level not in {"info", "success", "warn", "error"}:
            return f"Not added: level must be info, success, warn or error (got {level!r})"
        payload = NotificationPayload(message=message, level=level, source=source)
        return await add(payload, x, y, w, h)
