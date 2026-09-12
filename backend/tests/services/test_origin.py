"""How a call is rendered, how much of it survives, and how many get through.

All of it is arithmetic on strings and one window over a clock, so none of it
needs a board, a socket or a browser. What it looks like on the television is
checked by looking at the television.
"""

from services.origin import CHARS, Burst, call, request


def test_a_call_reads_as_a_call_and_not_as_a_wire_format() -> None:
    """The reference is a terminal echoing a command, not a JSON body."""
    text = call("add_gantt", {"title": "Tonight", "hours": 4})
    assert text == 'add_gantt(title="Tonight", hours=4)'


def test_a_tool_called_with_nothing_still_reads_as_a_call() -> None:
    """Empty parentheses, because that is what somebody would have typed."""
    assert call("board_status", {}) == "board_status()"


def test_a_five_hundred_line_payload_comes_out_short() -> None:
    """Scrolled in two seconds a long one is a grey blur that reads as a fault.

    So the content is cut before the animation ever sees it. The clock is fixed;
    this is the part that gives.
    """
    rows = [{"label": f"row {n}", "start": n, "end": n + 1} for n in range(500)]
    text = call("add_gantt", {"rows": rows, "title": "a long day"})

    assert len(text) <= CHARS
    assert "…" in text
    assert "\n" not in text


def test_the_arguments_after_an_enormous_one_survive_it() -> None:
    """The names are most of what makes this read as a call, and they come last.

    Without a budget per argument, a chart with two hundred points would spend
    the whole line before reaching `title`, and every call would look the same.
    """
    points = [{"x": n, "y": n * 3} for n in range(200)]
    text = call("add_chart", {"points": points, "title": "cpu", "max": 100})

    assert text.startswith("add_chart(points=[")
    assert 'title="cpu"' in text
    assert "max=100" in text


def test_a_request_is_one_line_whatever_shape_it_arrived_in() -> None:
    """A body somebody pretty-printed is still one call, and a call is one line."""
    body = b'{\n  "payload": {\n    "kind": "note",\n    "text": "hi"\n  }\n}'
    text = request("PUT", "/api/v1/board/items/by-key/cpu", body)
    flat = '{ "payload": { "kind": "note", "text": "hi" } }'

    assert text == f"PUT /api/v1/board/items/by-key/cpu {flat}"


def test_a_request_with_no_body_is_just_the_line() -> None:
    """No trailing space where a body would have been."""
    assert request("POST", "/api/v1/board/items", b"") == "POST /api/v1/board/items"


def test_the_cap_drops_rather_than_delays() -> None:
    """`arrange` and a board being rebuilt make several widgets in one breath.

    A queue would show the extras after the widgets they describe, which is
    worse than not showing them: texture that arrives late reads as a fault.
    """
    burst = Burst(most=3, seconds=2.0)

    assert [burst.allows(t) for t in (0.0, 0.1, 0.2)] == [True, True, True]
    assert [burst.allows(t) for t in (0.3, 0.4, 1.9)] == [False, False, False]
    # And the dropped ones are gone, not waiting: what gets through at 2.5 is
    # the one asking at 2.5, and the window is back to three.
    assert [burst.allows(t) for t in (2.5, 2.6, 2.7, 2.8)] == [True, True, True, False]


def test_a_quiet_board_is_never_capped() -> None:
    """One widget a minute is not a burst, however long the board has been up."""
    burst = Burst(most=3, seconds=2.0)
    assert [burst.allows(t) for t in (0.0, 60.0, 120.0, 180.0)] == [True] * 4
