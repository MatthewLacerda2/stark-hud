"""The agent's shaping: what a source printed, folded into a panel.

The fetching half is not here — it shells out and opens sockets — but this is
where a collector's output becomes what the board is sent, and it is the half
that decides whether a panel is right.
"""

from tools.agent import Source, interpret


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
