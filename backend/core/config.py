"""Application settings loaded from the environment and `.env`."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    Values come from environment variables first, then a local `.env` file.
    Unknown keys are ignored so the same `.env` can serve multiple services.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The board is a fixed grid: the TV cannot scroll, so anything that does not
    # fit on screen would stay invisible forever. Items are placed in cells,
    # never in pixels; the browser derives cell size from the viewport.
    #
    # 32x18 is 16:9 doubled, so a cell is square on a 1080p panel and a half-cell
    # nudge is still a visible amount of screen.
    GRID_COLS: int = Field(default=32, ge=1, le=96)
    GRID_ROWS: int = Field(default=18, ge=1, le=54)

    CORS_ORIGINS: str = "*"

    # Where the board is kept between runs. Empty means keep nothing, which is
    # what the tests want. The extension is ours; the contents are plain JSON,
    # so the file can be edited, copied, or swapped for another board.
    STATE_FILE: str = "state/board.hud"

    # How long the board may be ahead of the file on disk. Every change is
    # written whole, so this is a batching window, not a risk window: a power
    # cut loses at most this many seconds of the screen.
    STATE_FLUSH_SECONDS: float = 5.0

    # The board's voice, which is bought from ElevenLabs a sentence at a time.
    #
    # The key is never in this repository: it comes from the environment, and
    # docker-compose passes it through from a `.env` that git ignores. Empty is
    # a working configuration — the board simply cannot speak, and says so when
    # something asks it to.
    ELEVENLABS_API_KEY: str = ""

    # Daniel, sold as "Steady Broadcaster": a British male reading voice, which
    # is what a line announced across a room wants. A voice labelled English
    # reads every language the model does, so this one says a Portuguese line
    # too; there is no reason to swap it per language. George
    # (onwK4e9ZLuTAKqWW03F9, Daniel) is the fallback if this one is ever withdrawn.
    # Chosen by ear over Daniel: a steady broadcaster reads a line correctly,
    # a storyteller reads it like someone in the room said it.
    ELEVENLABS_VOICE_ID: str = "JBFqnCBsd6RMkjVDRZzb"

    # Flash costs half of `eleven_multilingual_v2` per character and reads the
    # same languages. This account is on the free tier, so "upgrading" this line
    # doubles what every sentence the board says takes out of the month.
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"

    # How the voice reads a line: the vendor's own `voice_settings`, which the
    # board used to leave unsent, so every sentence went out at whatever
    # ElevenLabs happens to default to this month. Named here instead, because a
    # board whose voice changes tone on its own is one nobody trusts.
    #
    # Every value below is the vendor's own default except the speed, so writing
    # them down changes nothing anybody can hear today. The ranges are the
    # vendor's too, and they are checked here on purpose: a value out of range is
    # a backend that refuses to start and says which field is wrong, rather than
    # a 422 at the moment somebody wanted a sentence read out.
    #
    # Two things to know before tuning any of these, both measured against the
    # real API rather than assumed:
    #
    #   * The vendor caches a line on its text, its voice and its model — and the
    #     cache key does not include these settings. A sentence the board has
    #     already said comes back byte-identical however these numbers change:
    #     instantly, and as far as the character counter shows, free. So change a
    #     value, hear no difference, and the conclusion is not "the setting is
    #     broken" — it is "that sentence is a recording". Tune on a line the
    #     board has never said, or nothing will ever seem to work.
    #   * `speed` is honoured by `eleven_flash_v2_5`, whatever one assumes about
    #     a cheap model ignoring the finer fields. The same sentence came back
    #     0.975s at 1.0 and 1.440s at 0.7 — the ratio that was asked for, to
    #     within noise. It is not a dead setting waiting to be cleaned away.
    ELEVENLABS_STABILITY: float = Field(default=0.5, ge=0.0, le=1.0)
    ELEVENLABS_SIMILARITY_BOOST: float = Field(default=0.75, ge=0.0, le=1.0)
    ELEVENLABS_STYLE: float = Field(default=0.0, ge=0.0, le=1.0)
    ELEVENLABS_USE_SPEAKER_BOOST: bool = True

    # The one value that is not the vendor's. At 1.0 this voice reads a shade
    # fast for a room, and five percent slower is the whole of the difference.
    # Outside 0.7-1.2 the vendor refuses the request, so that is the bound.
    ELEVENLABS_SPEED: float = Field(default=0.95, ge=0.7, le=1.2)

    # Where a spoken line is kept until the browser has fetched it. Under the
    # state directory because that is the one place the backend owns and the one
    # volume it can write to. Relative here, like `STATE_FILE` and for the same
    # reason: it is right for a backend run from `backend/`, and the container
    # points it at the mounted volume instead — see `docker-compose.yml`.
    SPEECH_DIR: str = "state/speech"

    # How many spoken lines are kept before the oldest are deleted. Deleting one
    # the moment it is broadcast would race the browser that has not fetched it
    # yet; keeping every one fills a disk on a machine nobody logs into. A
    # hundred-character line is a few seconds of MP3, so this ceiling is a
    # megabyte or two and never grows past it.
    SPEECH_KEEP: int = Field(default=20, ge=1)

    # Where a file handed over by a browser lands. Beside the board file and the
    # spoken lines, because that is the one directory this backend owns and the
    # one volume it can write to. Relative here like `STATE_FILE` and `SPEECH_DIR`,
    # and absolute in the container for the same reason — see `docker-compose.yml`.
    #
    # It is also the only directory on this machine the board ever deletes from.
    # A media queue mostly holds paths a session named — an album somewhere on a
    # disk full of them — and those are somebody's files. These are ours: they
    # arrived with no name on this machine and nothing but a widget refers to
    # them, so when no widget does, nothing does. See `services.uploads`.
    UPLOAD_DIR: str = "state/uploads"

    # How long an uploaded file nothing refers to is left alone before a sweep
    # may delete it.
    #
    # Receiving a file and playing it are two calls: the bytes land, and then
    # something puts the path into a queue. In between, the file is referenced by
    # nobody and is indistinguishable from one whose widget has just been taken
    # off the board. Without this window, removing any media widget in that gap
    # would delete a file that was a second away from being played. Five minutes
    # is far longer than the gap and far shorter than anybody notices the disk.
    UPLOAD_GRACE_SECONDS: float = Field(default=300.0, ge=0)

    # Driving the board by typing at it, which is bought from Google a prompt at
    # a time. Empty is a working configuration, exactly like the voice above:
    # the bar refuses in one sentence and everything else on the board carries
    # on. Never in this repository — the environment passes it in.
    GEMINI_API_KEY: str = ""

    # Which model a prompt goes to when the bar did not say. A setting rather
    # than a literal because the right answer is a measurement — how long each
    # one takes to answer with all fifty tool declarations attached — and the
    # point of this whole path is speed, so it should be changeable by whoever
    # takes that measurement without touching code.
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    # How many times round the call-tools-and-ask-again loop before giving up.
    # A ceiling and not a target: almost everything typed at this board is one
    # or two calls, and a model that has not finished by the fourth turn is
    # looping rather than working. Without it a confused model can spend the
    # account.
    GEMINI_MAX_ROUNDS: int = Field(default=4, ge=1, le=10)

    # A ceiling on what the model may write back. It is only ever writing tool
    # calls — there is no answer to render anywhere — so this is small on
    # purpose: it is the runaway that costs money, not the work.
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=2048, ge=256)

    # How long one prompt may take, end to end, before the browser is told it
    # failed. Well past what any of these models needs, and short enough that a
    # stuck request does not leave the bar hanging with nothing to say.
    GEMINI_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance."""
    return Settings()
