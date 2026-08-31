"""Notifications: an inbox, not tiles.

Several sessions announce into the same place, and one tile on the board shows
them the way a phone does — icon, title, body, when.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NotifyLevel = Literal["info", "success", "warn", "error"]

# A closed set rather than every lucide icon: the whole library would defeat
# tree-shaking for the sake of names nobody picks, and a short vocabulary is
# easier for a caller to choose from correctly.
ICONS = frozenset(
    {
        "bell",
        "check",
        "info",
        "alert-triangle",
        "alert-circle",
        "x-circle",
        "terminal",
        "git-branch",
        "download",
        "upload",
        "cpu",
        "hard-drive",
        "mail",
        "message-square",
        "clock",
        "zap",
        "flame",
        "bug",
        "rocket",
        "wrench",
    }
)


class NotificationCreate(BaseModel):
    """What a caller announces."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str | None = None
    # A name from ICONS, or an absolute path to a local image. Anything else is
    # refused rather than quietly dropped, so a typo is visible.
    icon: str | None = None
    level: NotifyLevel = "info"
    source: str | None = None
    # Colours for this one entry, as CSS the browser understands. Left out, the
    # text is white: an inbox where every line picks its own colour is a mess,
    # so colour is for the rare line that has to stand out.
    title_color: str | None = None
    body_color: str | None = None


class Notification(NotificationCreate):
    """One as stored and broadcast."""

    id: str
    created_at: datetime


class Inbox(BaseModel):
    """Everything still inside the window, newest first."""

    notifications: list[Notification]
    retention_hours: float = Field(description="How long one is kept before it drops out")
