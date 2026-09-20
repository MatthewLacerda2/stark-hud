"""MCP tools for groups: making one, folding it, opening it again.

A group is a handful of widgets on one page that fold into a shelf together. A
whole board's worth of layout is a page instead — see ``hud_mcp/pages.py``.

A group is asked for by name, like everything else on this board. Nothing
appears on the television to make one grabbable or to switch between them — the
room has no pointer, and a handle drawn for one would be a handle nobody there
can use.
"""

from mcp.server.mcpserver import MCPServer

from core.refusal import BoardRefusal
from hud_mcp.common import describe
from repositories import board as repo
from schemas.board import GroupPayload, ItemCreate, ItemRead
from services import board as service
from services import groups
from services.groups import NoRoomError


def _found(item_id: str) -> ItemRead | str:
    """The widget with this id or key, or a line saying it is not there."""
    item = repo.get(item_id) or repo.get_by_key(item_id)
    return item if item is not None else f"No item {item_id}. Call list_items to see what is there."


def register(server: MCPServer) -> None:
    """Attach the group tools to the server."""

    async def _refold(group: ItemRead, shut: bool) -> str:
        """Fold or unfold, and say what the board looks like afterwards.

        The one event carrying the whole board goes out from ``services.groups``,
        which is where the several widgets a fold moves actually move.
        """
        try:
            turned = await (groups.fold(group) if shut else groups.unfold(group))
        except BoardRefusal as exc:
            return str(exc)
        held = len(groups.members(turned))
        return f"{'Folded' if shut else 'Unfolded'} {describe(turned)} — {held} widgets inside"

    @server.tool()
    async def group_items(item_ids: list[str], description: str | None = None) -> str:
        """Put several widgets in a group, so they can be folded away together.

        A group is a widget that holds widgets. Open, which is how it starts, it
        takes up no room and nothing on the board moves: the widgets are exactly
        where they were. Fold it with `fold_group` and they come off the board,
        replaced by one small widget showing the icons of what is inside.

        This is for putting a handful of things down together on the board
        that is up: fold the training widgets away, use the room for something
        else, unfold them later. A whole screenful of a different subject is a
        **page**, not a group — see `show_page`.

        Everything joins the group's page along with the group, and a group and
        its widgets move between pages as one. A group holds widgets, never
        other groups.
        """
        if not item_ids:
            return "Nothing to group: name the widgets that go in it."
        found = [_found(i) for i in item_ids]
        missing = [f for f in found if isinstance(f, str)]
        if missing:
            return missing[0]
        wanted = [f for f in found if isinstance(f, ItemRead)]

        # Two calls and so two events, which is the one place on this board that
        # happens: the group appears, and then the board it changed goes out
        # whole. Both are true and they arrive in the same tick. A group nothing
        # could be put into is taken off again the same way it was put on, so a
        # refused grouping leaves the television as it found it.
        group = await service.create(ItemCreate(payload=GroupPayload(), description=description))
        try:
            await groups.gather(group, wanted)
        except BoardRefusal as exc:
            await service.remove(group)
            return str(exc)
        return f"Grouped {len(wanted)} widgets into {describe(repo.get(group.id) or group)}"

    @server.tool()
    async def fold_group(group_id: str) -> str:
        """Close a group: its widgets come off the board and it takes their place.

        The room they were using is free again, and the group draws where they
        were. Refused if something has since taken that corner — nothing on this
        board is ever shoved aside to make space.
        """
        group = _found(group_id)
        return group if isinstance(group, str) else await _refold(group, True)

    @server.tool()
    async def unfold_group(group_id: str) -> str:
        """Open a group: its widgets come back exactly where they were.

        Refused if something has moved into the room they left, which names what
        is in the way so you can move it first.
        """
        group = _found(group_id)
        return group if isinstance(group, str) else await _refold(group, False)

    @server.tool()
    async def add_to_group(group_id: str, item_ids: list[str]) -> str:
        """Put more widgets into a group that already exists.

        The group has to be open: moving a widget into one that is folded would
        take it off the board with nothing having made way for that, and nobody
        in the room would see it happen. A widget on another page joins this
        one's page as it joins the group.
        """
        group = _found(group_id)
        if isinstance(group, str):
            return group
        found = [_found(i) for i in item_ids]
        missing = [f for f in found if isinstance(f, str)]
        if missing:
            return missing[0]
        try:
            joined = await groups.gather(group, [f for f in found if isinstance(f, ItemRead)])
        except BoardRefusal as exc:
            return str(exc)
        return f"{len(joined)} widgets are now in {group.id}"

    @server.tool()
    async def remove_from_group(item_ids: list[str]) -> str:
        """Take widgets out of whatever group they are in, leaving them on the board."""
        found = [_found(i) for i in item_ids]
        missing = [f for f in found if isinstance(f, str)]
        if missing:
            return missing[0]
        try:
            loose = await groups.scatter([f for f in found if isinstance(f, ItemRead)])
        except NoRoomError as exc:
            return str(exc)
        return f"{len(loose)} widgets are in no group now"
