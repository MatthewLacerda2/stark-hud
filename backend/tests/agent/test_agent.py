"""The agent's shaping: what a source printed, folded into a panel.

The fetching half is not here — it shells out and opens sockets — but this is
where a collector's output becomes what the board is sent, and it is the half
that decides whether a panel is right.
"""

from tools.agent import Board, Source, interpret, tick


def _source(**spec) -> Source:
    """A declared source, with whatever the test cares about."""
    return Source({"name": "panel", "panel": {"kind": "note"}, **spec})


def test_output_that_is_not_json_is_the_text_of_a_note():
    """A collector printing a sentence is a note saying it, not a blank panel."""
    assert interpret("nvidia-smi unavailable") == "nvidia-smi unavailable"


def test_a_json_path_reaches_into_somebody_else_s_response():
    """A URL source rarely answers with the rows at the top level."""
    assert interpret('{"data": {"rows": [1, 2]}}', "data.rows") == [1, 2]


def test_a_json_path_that_is_not_there_is_a_failure_and_not_an_empty_panel():
    """None leaves the last good contents on the board rather than blanking it."""
    assert interpret('{"data": {}}', "data.rows", "panel") is None


def test_a_chart_gets_its_rows_in_data():
    """The source prints content; the config already says what kind it is."""
    panel = _source(panel={"kind": "chart", "chart": "bar"}).payload([{"use": 1}])
    assert panel["data"] == [{"use": 1}]


def test_a_list_gets_strings_and_a_feed_gets_entries():
    """Where the content lands is the one thing that differs by kind."""
    assert _source(panel={"kind": "list"}).payload(["a", "b"])["items"] == ["a", "b"]
    entries = [{"title": "t", "source": "s", "at": "now"}]
    assert _source(panel={"kind": "feed"}).payload(entries)["entries"] == entries


def test_text_split_into_lines_when_the_panel_is_a_list():
    """A collector that prints lines and a list panel mean the obvious thing."""
    assert _source(panel={"kind": "list"}).payload("a\nb")["items"] == ["a", "b"]


def test_history_turns_a_one_row_source_into_a_series():
    """The agent remembers, so a collector never has to."""
    source = _source(panel={"kind": "chart", "chart": "line"}, history=3)
    for value in range(1, 5):
        panel = source.payload([{"t": value}])
    assert panel["data"] == [{"t": 2}, {"t": 3}, {"t": 4}]


def test_a_feed_is_replaced_rather_than_accumulated():
    """History on a feed would only fight whoever is polling it."""
    source = _source(panel={"kind": "feed"}, history=5)
    source.payload([{"title": "first"}])
    assert source.payload([{"title": "second"}])["entries"] == [{"title": "second"}]


def test_a_source_with_nothing_to_run_is_left_as_the_config_wrote_it():
    """The inbox is fed over the socket; it only needs to exist and stay put."""
    assert _source(panel={"kind": "inbox", "title": "Inbox"}).payload([]) == {
        "kind": "inbox",
        "title": "Inbox",
    }


def _announcer() -> Source:
    """A source whose rows are notifications rather than a panel."""
    return Source({"name": "alerts", "notifications": True})


DISK = {"key": "full:/", "title": "/ is 91% full", "level": "warn"}


def test_the_first_time_something_is_wrong_it_is_announced():
    assert _announcer().news([DISK]) == [{"title": "/ is 91% full", "level": "warn"}]


def test_the_agent_s_own_bookkeeping_does_not_go_to_the_board():
    """The notification model forbids fields it does not know, so `key` is a 422."""
    assert "key" not in _announcer().news([DISK])[0]


def test_something_still_wrong_is_not_announced_again():
    """An inbox that repeats itself every five minutes is one nobody reads."""
    source = _announcer()
    source.news([DISK])

    assert source.news([DISK]) == []


def test_a_title_that_moves_is_still_the_same_news():
    """Three packages and four packages are one fact, so the key identifies it."""
    source = _announcer()
    source.news([{"key": "updates", "title": "3 packages can be upgraded"}])

    assert source.news([{"key": "updates", "title": "4 packages can be upgraded"}]) == []


def test_a_problem_that_clears_and_returns_is_news_again():
    """Remembering forever would silence the second time a disk filled up."""
    source = _announcer()
    source.news([DISK])
    source.news([])

    assert source.news([DISK]) != []


def test_a_row_with_no_key_falls_back_to_its_title():
    source = _announcer()
    source.news([{"title": "sshd.service has failed"}])

    assert source.news([{"title": "sshd.service has failed"}]) == []


class _Board(Board):
    """A board that remembers what it was told instead of saying it."""

    def __init__(self, up: list[dict] | None = None) -> None:
        super().__init__("http://board/api/v1")
        self.up = up or []
        self.calls: list[tuple[str, str]] = []

    def call(self, method: str, path: str, body: dict | None = None):
        self.calls.append((method, path))
        return self.up if method == "GET" else None


def _transient(**spec) -> Source:
    """A source whose widget only exists while it has something to put in it."""
    return Source({"name": "trm_curve", "transient": True, "panel": {"kind": "chart"}, **spec})


def test_a_transient_source_with_nothing_to_say_takes_its_widget_down():
    """An empty frame saying "no data" where a training run used to be is worse
    than no widget: the subject is gone, so the widget should be."""
    board = _Board([{"key": "trm_curve", "id": "abc"}])
    tick(board, [_transient(command="echo []")], 0.0)

    assert ("DELETE", "/board/items/abc") in board.calls


def test_a_widget_that_is_already_down_is_not_chased():
    """The ordinary case while nothing is training, and it costs one GET."""
    board = _Board()
    tick(board, [_transient(command="echo []")], 0.0)

    assert [method for method, _ in board.calls] == ["GET"]


def test_a_transient_source_with_rows_is_written_like_any_other_panel():
    """Having something to say is the whole of the difference."""
    board = _Board()
    tick(board, [_transient(command="echo [7]")], 0.0)

    assert board.calls == [("PUT", "/board/items/by-key/trm_curve")]


def test_a_panel_is_created_with_its_note_and_then_left_alone():
    """A widget that comes and goes loses whatever was set on it by hand the
    first time it comes down, so the note is declared beside the panel."""
    source = Source(
        {
            "name": "trm_curve",
            "panel": {"kind": "chart"},
            "place": {"x": 23, "y": 4},
            "description": "what this is, and what feeds it",
        }
    )

    assert source.made == {"x": 23, "y": 4, "description": "what this is, and what feeds it"}
