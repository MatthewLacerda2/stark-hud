"""The agent's shaping: what a source printed, folded into a panel.

The fetching half is not here — it shells out and opens sockets — but this is
where a collector's output becomes what the board is sent, and it is the half
that decides whether a panel is right. What the file declaring those sources
does when it is edited is `test_sources.py`.
"""

from agent import Board, tick
from sources import Source, interpret


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


class _Spy(Board):
    """A board that writes nothing down but what it was asked to do."""

    def __init__(self):
        super().__init__("http://nowhere")
        self.written: list[tuple[str, dict]] = []

    def call(self, method, path, body=None):
        self.written.append((path, body or {}))
        return None


def test_a_static_widget_is_written_without_running_anything(tmp_path):
    """The inbox is fed over the socket: this entry only keeps it on the board."""
    board = _Spy()
    source = Source({"name": "inbox", "panel": {"kind": "inbox"}, "place": {"x": 1}})

    tick(board, [source], tmp_path, 0.0)

    assert board.written == [("/board/items/by-key/inbox", {"payload": {"kind": "inbox"}, "x": 1})]


def test_a_job_writes_its_own_widgets_and_the_agent_writes_none(tmp_path):
    """The agent starts a watcher and gets out of its way."""
    board = _Spy()
    job = Source({"name": "trm", "command": "true"})

    tick(board, [job], tmp_path, 0.0)
    job.process.wait()

    assert board.written == []


def test_a_panel_declaring_no_page_says_nothing_about_pages(tmp_path):
    """The board decides, exactly as it did before a source could say.

    Which means the default page, not the one showing: nothing that writes by
    key is looking at the television. See `tests/api/v1/test_by_key.py`.
    """
    board = _Spy()

    tick(board, [_source(place={"x": 1})], tmp_path, 0.0)

    assert "page" not in board.written[0][1]


def test_a_panel_that_declares_a_page_is_written_to_it(tmp_path):
    """A reading worth keeping, on a screen the ordinary board never gives up."""
    board = _Spy()

    tick(board, [_source(page="machine")], tmp_path, 0.0)

    assert board.written[0][1]["page"] == "machine"
