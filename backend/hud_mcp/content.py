"""MCP tools that put things on the board.

Every one of them takes an optional ``description``: a note about the widget
that only a session ever reads, never drawn on the TV. It is a parameter here
rather than a second call because the moment a session knows why a widget exists
is the moment it makes one, and a follow-up call is a call that gets skipped.
``set_description`` changes or clears it afterwards.
"""

from mcp.server.mcpserver import MCPServer

from hud_mcp.common import add
from schemas.board import (
    BoxPayload,
    ChartPayload,
    ClockPayload,
    FeedEntry,
    FeedPayload,
    ImagePayload,
    InboxPayload,
    ListEntry,
    ListPayload,
    NotePayload,
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
        description: str | None = None,
    ) -> str:
        """Put a sticky note on the board.

        Omit x and y and the board picks a free slot; omit w and h for a default
        size. Coordinates are grid cells (the grid is 12x8), never pixels.

        Leave `color` alone unless asked. The board is a TV in a dim room, so
        widgets are dark by convention — a pale note is a lamp pointed at whoever
        is watching, and white text on it is unreadable.
        """
        return await add(NotePayload(text=text, color=color), x, y, w, h, description=description)

    @server.tool()
    async def add_text(
        text: str,
        size: str = "md",
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put bare text on the board, with no card behind it.

        Size is one of sm, md, lg, xl. Use lg or xl for something meant to be
        read from across the room.
        """
        if size not in {"sm", "md", "lg", "xl"}:
            return f"Not added: size must be sm, md, lg or xl (got {size!r})"
        return await add(TextPayload(text=text, size=size), x, y, w, h, description=description)

    @server.tool()
    async def add_list(
        items: list[str | dict],
        title: str | None = None,
        icon: str | None = None,
        empty: str | None = None,
        title_color: str | None = None,
        icon_color: str | None = None,
        item_color: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put a heading and a list of lines on the board.

        Use this rather than a note full of newlines: the title and the entries
        are drawn at different sizes and weights, which a single string cannot
        express. `empty` is what to show when the list has nothing in it, and
        `icon` is drawn beside the heading — a name from the notification icon
        set, or an absolute path to a picture on this machine.

        An entry is a plain line of text, or `{"title": ..., "body": ...,
        "icon": ...}` when one line is not enough: `body` is a second, fainter
        line under the title, and `icon` is the same vocabulary as the widget's.
        A list of plain strings reads as running text; one rich entry turns them
        all into rows, so pick one shape and stay in it.

        Every part can be given a colour, and an entry may carry
        `title_color`, `body_color` and `icon_color` of its own. The rule is one
        sentence: an entry's own colour wins, then the widget-wide one
        (`title_color` for the heading and the icon beside it, `item_color` for
        anything inside an entry), then the widget's colour — which is what a
        list that names none of them gets, and usually what you want.
        """
        # A typo in an icon or a colour comes back as the sentence the validator
        # wrote, the same whether it was on the widget or on one of its entries.
        try:
            payload = ListPayload(
                title=title,
                icon=icon,
                items=[e if isinstance(e, str) else ListEntry(**e) for e in items],
                empty=empty,
                title_color=title_color,
                icon_color=icon_color,
                item_color=item_color,
            )
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(payload, x, y, w, h, description=description)

    @server.tool()
    async def add_box(
        label: str | None = None,
        fill: str | None = None,
        stroke: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put a labelled container on the board.

        Other items can name it as their parent with set_parent. Colours are CSS
        strings; leave them out to use the theme.
        """
        return await add(
            BoxPayload(label=label, fill=fill, stroke=stroke), x, y, w, h, description=description
        )

    @server.tool()
    async def add_image(
        path: str,
        alt: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        parent_id: str | None = None,
        description: str | None = None,
    ) -> str:
        """Show a local image file.

        The path must exist on the machine running the board. If the file later
        moves, the widget shows a "file not found" placeholder instead of breaking.
        """
        return await add(
            ImagePayload(path=path, alt=alt), x, y, w, h, parent_id, description=description
        )

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
        description: str | None = None,
    ) -> str:
        """Show a local video file.

        Muted by default: several widgets playing sound at once is unusable. Only
        unmute when the video is the point of the board right now.
        """
        payload = VideoPayload(path=path, autoplay=autoplay, loop=loop, muted=muted)
        return await add(payload, x, y, w, h, parent_id, description=description)

    @server.tool()
    async def add_chart(
        chart: str,
        data: list[dict[str, float | int | str]],
        x_key: str,
        series: list[str],
        title: str | None = None,
        max: float | None = None,
        unit: str | None = None,
        axes: str = "both",
        colors: list[str] | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Draw a chart from data you supply inline.

        The board never fetches or polls: send the numbers. `chart` is line, bar,
        pie or area. `x_key` names the field on the x axis and `series` names the
        fields to plot. To update a chart, remove it and add it again.

        `axes` says which axes a line, bar or area chart draws: both (the
        default), x, y or none. Leave it out unless the numbers read on their
        own without a scale — a pie has no axes and ignores it.

        `colors` is one CSS colour per series. An eight-digit hex carries alpha —
        `#33ccffaa` — which leaves the video behind the board showing through the
        marks.
        """
        if chart not in {"line", "bar", "pie", "area"}:
            return f"Not added: chart must be line, bar, pie or area (got {chart!r})"
        if axes not in {"both", "x", "y", "none"}:
            return f"Not added: axes must be both, x, y or none (got {axes!r})"
        payload = ChartPayload(
            chart=chart,
            data=data,
            x_key=x_key,
            series=series,
            title=title,
            max=max,
            unit=unit,
            axes=axes,
            colors=colors or [],
        )
        return await add(payload, x, y, w, h, description=description)

    @server.tool()
    async def add_inbox(
        title: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put the notification inbox on the board.

        One widget holds every notification, the way a phone's shade does. Make it
        taller to show more at once and wider to fit more of each line. There is
        no reason to have two.
        """
        return await add(InboxPayload(title=title), x, y, w, h, description=description)

    @server.tool()
    async def add_feed(
        entries: list[dict],
        title: str | None = None,
        empty: str | None = None,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put a feed of things that happened on the board, newest first.

        Each entry is `{"title": ..., "source": ..., "at": ...}`, where `title`
        is the line people read, `source` says where it came from, and `at` is
        an ISO timestamp. Only `title` is required.

        Use this for something you poll and rewrite whole — a feed is replaced
        on every refresh, not appended to. To announce that one thing finished,
        use notify instead: that goes in the inbox and stays.
        """
        try:
            rows = [FeedEntry(**entry) for entry in entries]
        except (TypeError, ValueError) as exc:
            return f"Not added: {exc}"
        return await add(
            FeedPayload(title=title, entries=rows, empty=empty),
            x,
            y,
            w,
            h,
            description=description,
        )

    @server.tool()
    async def add_clock(
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put a clock on the board: the time now, and the date under it.

        It takes no content and is never updated — the browser keeps its own
        time. Two rows tall it shows only the time; give it three or more for
        the date as well.
        """
        return await add(ClockPayload(), x, y, w, h, description=description)
