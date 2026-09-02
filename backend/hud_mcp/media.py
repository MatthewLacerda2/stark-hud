"""MCP tools for the widget that plays things.

Every control lives here rather than on the screen, and that is the point: the
TV has no keyboard and no mouse, so a button drawn on the board is a button
nobody can press. A tool call is the only hand this widget has.

A track is a local file or a YouTube video, and these tools do not care which:
that is the point of it being one widget with two kinds of source rather than
two widgets that would each need a queue, a transport and a loop flag.

Four tools, not nine. `control_media` carries the five transport verbs in one
argument because they are mutually exclusive, take nothing but the widget, and
would otherwise be five entries in the tool list every session has to read —
the same reason `set_style` is one tool for four attributes. What is *not*
folded in is anything with a different shape: making the widget, replacing its
queue, and setting the flags that persist are three different sentences, and
running them together would mean a call that pauses and reorders an album at
once, which nobody means.
"""

from mcp.server.mcpserver import MCPServer

from core.hub import hub
from hud_mcp.common import add
from repositories import board as repo
from schemas.board import ItemRead, ItemUpdate, MediaPayload
from schemas.media import MEDIA_ACTIONS
from services import board as service
from services import media as media_service
from services.board import SlotTakenError


def _clock(seconds: float) -> str:
    """Somewhere in a track, written the way a person would say it."""
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _describe(payload: MediaPayload) -> str:
    """What the queue is on, in one clause a session can read back."""
    if not payload.tracks:
        return "an empty queue"
    track = payload.current
    place = f"{payload.index + 1} of {len(payload.tracks)}"
    verb = "playing" if payload.playing else "paused on"
    # Only when it is somewhere: "at 0:00" on every reply would be noise, and
    # this line is read by a session deciding what to do next.
    where = f" at {_clock(payload.seconds)}" if payload.seconds else ""
    return f"{verb} {track.title!r} ({place}){where}"


# What each action reads as once it has happened. Adding "ed" to the verb gave
# "stoped", "pauseed" and "nexted": English past tense is not a suffix, and this
# sentence is what the next session reads back.
DONE = {
    "play": "playing",
    "pause": "paused",
    "stop": "stopped",
    "next": "skipped to",
    "back": "went back on",
    "seek": "moved",
}


def register(server: MCPServer) -> None:
    """Attach the media tools to the server."""

    def _media(item_id: str) -> ItemRead | None:
        """The item with that id, when it is a media widget and not something else."""
        item = repo.get(item_id)
        return item if item is not None and item.payload.kind == "media" else None

    async def _write(item: ItemRead, payload: MediaPayload, verb: str) -> str:
        """Put a new payload on the widget, tell every board, and say what it is doing."""
        try:
            updated = service.update(item, ItemUpdate(payload=payload))
        except SlotTakenError as exc:
            return f"Not {verb}: {exc}"
        await hub.broadcast("item.updated", updated.model_dump(mode="json"))
        return f"{verb.capitalize()} {item.id}: {_describe(updated.payload)}"

    @server.tool()
    async def add_media(
        tracks: list[str],
        title: str | None = None,
        loop: bool = False,
        muted: bool = False,
        playing: bool = True,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
        description: str | None = None,
    ) -> str:
        """Put a player on the board with a queue in it, and start it.

        `tracks` is a list of absolute paths on the machine running the board.
        Each one may be a file, a directory, or a glob — a directory is expanded
        to every audio and video file inside it, sorted by filename, which is
        what track numbers in filenames are for. So a whole album is one string:
        pass `["/mnt/d_drive/Music/Some Album/CD1"]` and get its tracks in order.
        Spaces and apostrophes need no escaping; nothing here becomes a URL.

        An entry may also be a YouTube video, written any way you have it: a
        watch URL, a youtu.be link, or the bare eleven-character id. It is one
        track, played by YouTube's own player, and it may sit in the same queue
        as local files. Searching YouTube is not this board's job — find the id
        with yt-dlp and pass it in.

        Local files and YouTube are the same widget. Whichever it is, when a
        track ends the next one starts on its own — that is the whole point of
        it. `loop` says what happens after the last: start again from the top,
        or stop.

        Sound is on unless you mute it, unlike add_video. This widget is the one
        that is meant to be heard.

        A video draws video and nothing else: no title over it, no queue
        position under it. Audio draws its album art with the track's title
        above and the artist and album below, all read out of the file's own
        tags, so a well-ripped album needs nothing said about it here.

        Below four grid cells on either side it stops drawing a player and shows
        only the album art, because a player that small cannot be read from a
        sofa. It keeps playing.
        """
        try:
            queue = media_service.tracks_from(tracks)
        except ValueError as exc:
            return f"Not added: {exc}"
        if tracks and not queue:
            return f"Not added: nothing playable in {', '.join(tracks)}"
        payload = MediaPayload(tracks=queue, title=title, loop=loop, muted=muted, playing=playing)
        line = await add(payload, x, y, w, h, description=description)
        return line if line.startswith("Not added") else f"{line}, {_describe(payload)}"

    @server.tool()
    async def set_media_queue(
        item_id: str, tracks: list[str], start: int = 0, title: str | None = None
    ) -> str:
        """Replace what a player is holding, and go to `start` in the new queue.

        The same vocabulary as add_media: files, directories, globs, and YouTube
        links or ids, in any mixture. The old queue is gone — this is not add_to_list, because a queue is something you
        put on rather than something people keep adding to.

        `title` goes with the queue and is cleared unless you pass one, because a
        widget still captioned with the album that used to be in it is worse than
        one captioned with nothing. It is only ever drawn under audio, and only
        when the files themselves carry no album of their own.

        The new queue starts at the beginning of its first track: where the old
        one had got to was about a file that is no longer here.

        Find the id with list_items.
        """
        item = _media(item_id)
        if item is None:
            return f"No media widget {item_id}. Call list_items to see what is there."
        try:
            queue = media_service.tracks_from(tracks)
        except ValueError as exc:
            return f"Not queued: {exc}"
        index = min(max(start, 0), max(len(queue) - 1, 0))
        payload = item.payload.model_copy(
            update={"tracks": queue, "index": index, "seconds": 0.0, "title": title}
        )
        return await _write(item, payload, "queued")

    @server.tool()
    async def control_media(item_id: str, action: str, seconds: float = 0.0) -> str:
        """Drive a player: play, pause, stop, next, back or seek.

        This is the remote control. The board is a television with nothing to
        press, so these are only ever reachable as a call.

        `stop` is pause plus back to the top, so playing again plays the queue
        rather than the track it stopped on. `next` past the last track starts
        again from the top when the widget is looping and stops there when it is
        not — the same rule a track that simply ended follows, because it is the
        same rule.

        `seek` is the only one that reads `seconds`: it puts the widget that far
        into the track it is on, which is how you ask for the third hour of a
        film — `seconds=11160` is 3:06:00. The widget also keeps its own place as
        it plays, so a page that reloads and a server that restarts both come
        back where they were rather than at the beginning.

        Find the id with list_items, which also says what the widget reports it
        is actually doing.
        """
        item = _media(item_id)
        if item is None:
            return f"No media widget {item_id}. Call list_items to see what is there."
        if action not in MEDIA_ACTIONS:
            named = ", ".join(MEDIA_ACTIONS[:-1])
            return f"Not done: action must be {named} or {MEDIA_ACTIONS[-1]} (got {action!r})"
        if not item.payload.tracks:
            return f"Nothing to {action}: media widget {item_id} has an empty queue."
        moved = media_service.commanded(item.payload, action, seconds)
        return await _write(item, moved, DONE[action])

    @server.tool()
    async def set_media_mode(
        item_id: str,
        loop: bool | None = None,
        muted: bool | None = None,
        maximised: bool | None = None,
        captions: bool | None = None,
    ) -> str:
        """Change how a player behaves, rather than what it is doing right now.

        Everything is optional; only what you pass moves, the way set_style
        works.

        `loop` decides what happens when the queue runs out: start again from the
        top, or stop. `maximised` gives the widget the whole board and takes it
        back again — the widget keeps its slot on the grid and returns to it, so
        this is undone by passing false, not by moving anything.

        `captions` is YouTube's subtitles, off unless asked for, and it is read
        when a video's player is built — so turn it on before the video, not
        halfway through it. There is no equivalent for a local file: nothing on
        this board carries a subtitle track.

        `maximised` is not fullscreen. Fullscreen belongs to a browser and is
        only ever granted to somebody clicking something, so it is a control on
        the widget for whoever has a mouse, and no call can reach it.
        """
        item = _media(item_id)
        if item is None:
            return f"No media widget {item_id}. Call list_items to see what is there."
        asked = {"loop": loop, "muted": muted, "maximised": maximised, "captions": captions}
        given = {name: value for name, value in asked.items() if value is not None}
        if not given:
            return "Nothing to set: pass at least one of loop, muted, maximised or captions"
        payload = item.payload.model_copy(update=given)
        said = ", ".join(f"{name}={str(value).lower()}" for name, value in given.items())
        return await _write(item, payload, f"set {said} on")
