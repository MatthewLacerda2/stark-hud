"""MCP tools that move, remove, and report on what is already there."""

from typing import cast

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from core.refusal import BoardRefusal
from hud_mcp.common import DESTRUCTIVE, carried, describe, room_wanted
from repositories import board as repo
from schemas.board import Arrangement, Change, ItemUpdate
from services import arrange as arrange_service
from services import board as service
from services.board import SlotTakenError
from services.placement import NoRoomError, cells, size


def register(server: MCPServer) -> None:
    """Attach the layout and inspection tools to the server."""

    async def _patch(item_id: str, data: ItemUpdate, verb: str) -> str:
        """Apply an update and describe the result.

        The television is told inside ``services.board.update``, which is why
        nothing here says anything about it.
        """
        item = repo.get(item_id)
        if item is None:
            return f"No item {item_id}. Call list_items to see what is there."
        try:
            updated = await service.update(item, data)
        except SlotTakenError as exc:
            return f"Not {verb}: {exc}"
        line = f"{verb.capitalize()} {describe(updated)}"
        # Only a move or a resize can come to stand in a fold's room. A restyle
        # cannot, and the same note on every set_style would be noise.
        if any(v is not None for v in (data.x, data.y, data.w, data.h)):
            line += room_wanted([updated.id])
        return line

    @server.tool()
    async def move_item(item_id: str, x: float, y: float) -> str:
        """Move an item, in columns and rows. Fails if something is already there."""
        return await _patch(item_id, ItemUpdate(x=x, y=y), "moved")

    @server.tool()
    async def arrange(changes: list[dict]) -> str:
        """Change several widgets at once, judged by the arrangement it produces.

        Use this whenever more than one widget has to end up somewhere. Two
        widgets swapping places is the case it exists for: each has to go where
        the other still is, which is illegal at every moment in between and
        perfectly legal at the end, and on a full board there is nowhere to park
        one of them — so one at a time the swap is not slow, it is impossible.

        Each change names a widget by id or by key and says where it **ends up**,
        not what to do to it: `{"target": "cpu", "x": 4, "y": 2, "w": 8,
        "h": 3}`. Anything left out is left alone, so a change says only what
        changes. `{"target": "...", "remove": true}` takes a widget off the
        board — the one verb here, because being gone is not a place. `color`,
        `border`, `scale` and `flat` are accepted too. There is no add: a new
        widget has no id to name yet, and no `parent_id` or page — which group
        and which page a widget is on are trades, made by `add_to_group` and
        `move_to_page`, not fields an arrangement writes.

        `{"target": "training", "folded": false}` opens a group and `true`
        closes one, in the same batch as everything else: "move the calendar
        half a column left, take the video off, and open the training widgets"
        is one call and one cut on the television rather than three with the
        room watching in between. A group folds where its widgets are, unless
        the same entry names a place of its own. If something is still standing
        in the room an unfold needs back, nothing in the batch happens and the
        refusal names every blocker and how far into that room it is.

        An arrangement may name widgets on a page that is not showing, and each
        page it touches has to end up a board somebody could turn back to.

        Name each widget once. Two entries for one widget is two answers to
        where it ends up.

        All of it happens or none of it does. A refusal names the two widgets
        that would have been in the same place, so you can work out what to send
        instead — and the board comes back as it now stands, so you do not have
        to ask.
        """
        try:
            # Pydantic turns the dicts into Changes on the way in; the cast says so.
            batch = Arrangement(changes=cast(list[Change], [dict(c) for c in changes]))
            items = await arrange_service.rearrange(batch.changes)
        except ValidationError as exc:
            return f"Not rearranged: {exc.error_count()} bad change(s) — {exc.errors()[0]['msg']}"
        except BoardRefusal as exc:
            return str(exc)
        board = "Rearranged:\n" + "\n".join(describe(i) for i in items)
        return board + room_wanted([c.target for c in batch.changes])

    @server.tool()
    async def resize_item(item_id: str, w: float, h: float) -> str:
        """Resize an item, in columns and rows. Fails if it would overlap or overflow."""
        return await _patch(item_id, ItemUpdate(w=w, h=h), "resized")

    @server.tool()
    async def set_style(
        item_id: str,
        color: str | None = None,
        border: str | None = None,
        scale: float | None = None,
        flat: bool | None = None,
    ) -> str:
        """Change how a widget looks. Everything is optional; only what you pass moves.

        There is no background to set: every widget is drawn straight on the
        board's video, except media and images, which cover it with a picture.

        `color` is the widget's **text** colour, and every colour on this board
        is written the same way. Name one of the board's own — `foreground`,
        `muted-foreground`, `accent`, `destructive`, `success`, `warning`,
        `info`, `chart-1` to `chart-6` — and it follows the theme wherever the
        theme goes. Pass hex when you mean one particular colour and nothing
        else. An eight-digit hex carries alpha — `#ffffff80` — so the text can be
        made to read through rather than over the video the board sits on.

        Prefer a name. A widget in `destructive` still says something is wrong
        after the palette moves; the hex that colour happens to be today does
        not, and a board where every session picked its own red stops looking
        like one board.

        `border` draws a line around the widget in whatever colour is given.
        Almost nothing wants one — a board of outlined rectangles is a form
        rather than a view — so this is for the widget that needs an edge of its
        own; pass an eight-digit hex if you want the line itself faint.

        `scale` multiplies the text inside, 0.25 to 4. Type already grows with
        the widget; this moves the whole range.

        `flat` takes the widget's glass off: no lit edge, no thickness, just
        what it draws, straight on the video. `true` takes it off and `false`
        puts it back. Every widget is a pane by default and most should stay
        one — this is for the widget that already carries a picture of its own,
        a film or a photograph or a chart with its own frame, where the edge
        reads as a frame around a frame.

        It is not `border` by another name. A border is a line somebody chose
        the colour of; `flat` is whether the widget has thickness at all. And it
        only ever takes away — a board flattened at the browser stays flat
        whatever a widget asks for.
        """
        if scale is not None and not 0.25 <= scale <= 4:
            return f"Not set: scale must be between 0.25 and 4 (got {scale})"
        if color is None and border is None and scale is None and flat is None:
            return "Nothing to set: pass at least one of color, border, scale or flat"
        update = ItemUpdate(color=color, border=border, scale=scale, flat=flat)
        return await _patch(item_id, update, "restyled")

    @server.tool()
    async def set_description(item_id: str, description: str = "") -> str:
        """Leave a note on a widget for whoever drives this board next.

        Nobody ever sees it on the TV. It is context a later session cannot get
        back by looking: what this widget is for, what it is waiting on, what
        its number means, that it should be updated after Friday. Write down
        what you would have to explain to yourself in a week.

        It is kept on the widget, not in what the widget shows, so a panel that
        is rewritten every few seconds keeps its note. It comes back with
        list_items, on the same line as the widget, which is where you will find
        one somebody else left.

        Pass nothing, or an empty string, to take the note off. Find the id with
        list_items.
        """
        return await _patch(item_id, ItemUpdate(description=description), "described")

    @server.tool()
    async def remove_item(item_id: str) -> str:
        """Delete an item.

        Removing a group does not delete what it held: its widgets go back on
        the board where they were, which is also why a folded group can only be
        removed while there is still room for them.
        """
        item = repo.get(item_id)
        if item is None:
            return f"No item {item_id}; nothing removed."
        try:
            await service.remove(item)
        except NoRoomError as exc:
            return str(exc)
        return f"Removed {item_id}"

    @server.tool(annotations=DESTRUCTIVE)
    async def clear_board() -> str:
        """Remove every widget on every page. There is no undo and nothing is saved.

        The whole board, not the page that is showing: a page is where a widget
        is, not a board of its own to be emptied.
        """
        removed = await service.clear()
        return f"Cleared the board ({removed} items removed)"

    @server.tool()
    async def list_items() -> str:
        """List every widget, oldest first, whatever page it is on.

        A widget on a page that is not showing says so on its line. It is listed
        anyway because it still exists and still takes writes by key — a panel
        has to be findable by whatever feeds it, wherever the board is turned.
        """
        items = repo.list_items()
        if not items:
            return "The board is empty."
        return "\n".join(describe(item) for item in items)

    @server.tool()
    async def board_status() -> str:
        """Report how much room is left before you try to add something.

        Worth calling first when adding several items, or anything large.
        """
        status = service.status()
        free = status.largest_free_rect
        largest = (
            f"{size(free.w, free.h)} at ({cells(free.x)},{cells(free.y)})" if free else "nothing"
        )
        return (
            f"Board {size(status.cols, status.rows)}, {status.item_count} items. "
            f"{cells(status.cells_used)}/{cells(status.cells_total)} cells used, "
            f"{cells(status.cells_free)} free. Largest free rectangle: {largest}."
            # Counted on the page that is showing, because that is the board:
            # every other page has the whole grid to itself and takes none of
            # this one. Saying which page, and what else is here, is the
            # difference between a board with space and a board you have not
            # turned to yet.
            f"{carried()}"
        )
