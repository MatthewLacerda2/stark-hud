"""The measuring rig's half that can be tested without a browser.

`tools/perf/` starts Chromium, serves a bundle and reads `/proc`, and none of
that belongs in a test suite — the rig is deliberately outside `make check` for
exactly that reason. What is here is everything underneath: the websocket
framing both ends of it speak, the `/proc/<pid>/stat` field counting that is
the whole CPU measurement, the normalisation that decides whether two boards
drew the same picture, and the fixture board's promise to be the same board
twice.

Each of these has a wrong version that looks right. A frame length read from
the wrong byte, a stat line split from the left, a comparison that calls two
identical charts different because recharts numbered its clip paths
differently: all four produce a plausible number or a plausible diff, and none
of them would be noticed by running the rig.
"""

import io

from perf import board, cost, report, surfaces, wire


def _frame(payload: bytes, opcode: int, *, final: bool) -> bytes:
    """A frame with FIN under the test's control, which `wire.frame` never gives."""
    head = bytearray([(0x80 if final else 0x00) | opcode, len(payload)])
    return bytes(head) + payload


def test_the_handshake_answers_the_rfc_s_own_example():
    """If this drifts, every browser refuses the socket and nothing is measured."""
    assert wire.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_a_frame_survives_every_length_the_header_changes_shape_at():
    """125, 126 and 65536 are where the RFC switches to a longer length field."""
    for size in (0, 125, 126, 65535, 65536):
        payload = b"x" * size
        read = io.BytesIO(wire.frame(payload, mask=False))
        assert wire.read_message(read) == (wire.TEXT, payload)


def test_a_masked_frame_is_unmasked_by_the_other_end():
    """The rig masks writing to Chromium and does not writing to a browser."""
    read = io.BytesIO(wire.frame(b"hello", mask=True))
    assert wire.read_message(read) == (wire.TEXT, b"hello")


def test_a_message_split_across_frames_arrives_whole():
    """A screenshot is megabytes and Chromium may send it in pieces."""
    raw = _frame(b"one ", wire.TEXT, final=False) + _frame(b"two", 0x0, final=True)
    assert wire.read_message(io.BytesIO(raw)) == (wire.TEXT, b"one two")


def test_a_closed_socket_reads_as_nothing_rather_than_raising():
    assert wire.read_message(io.BytesIO(b"")) is None


def test_cpu_time_is_counted_past_a_process_name_full_of_punctuation():
    """`(Isolated Web Co)` is an ordinary chromium process name.

    Splitting this line from the left puts utime two fields out and reports a
    number that is wrong and looks fine.
    """
    stat = "42 (Isolated Web Co) S 1 42 42 0 -1 4194304 100 0 0 0 " + "1300 250 " + "0 " * 30
    assert cost.jiffies_in(stat) == 1550


def test_a_generated_clip_path_id_is_not_a_difference_in_the_picture():
    """Recharts numbers clip paths from a page-wide counter, not from the drawing."""
    before = surfaces.Surface(at=(0, 0, 10, 10), svg='<svg clip-path="url(#recharts3-clip)"/>')
    after = surfaces.Surface(at=(0, 0, 10, 10), svg='<svg clip-path="url(#recharts9-clip)"/>')
    assert surfaces.compare([before], [after]) == []


def test_a_mark_that_moved_is_reported_with_where_it_went():
    before = surfaces.Surface(at=(0, 0, 10, 10), svg="<svg/>")
    after = surfaces.Surface(at=(0, 4, 10, 10), svg="<svg/>")
    assert "moved" in surfaces.compare([before], [after])[0]


def test_a_board_that_drew_a_different_number_of_marks_is_a_difference():
    one = surfaces.Surface(at=(0, 0, 1, 1), svg="<svg/>")
    assert surfaces.compare([one], [one, one]) != []


def test_a_changed_path_is_reported_as_a_redraw():
    before = surfaces.Surface(at=(0, 0, 10, 10), svg='<path d="M0 0"/>')
    after = surfaces.Surface(at=(0, 0, 10, 10), svg='<path d="M0 1"/>')
    assert "redrew" in surfaces.compare([before], [after])[0]


def test_two_runs_of_the_fixture_board_see_the_same_numbers():
    """A sweep compares arms. A difference has to come from the code."""
    first, second = board.Board(), board.Board()
    for _ in range(5):
        first.advance()
        second.advance()
    assert first.items() == second.items()


def test_a_reading_slides_the_history_window_rather_than_growing_it():
    """A line chart carries a fixed window.

    A window that grew would make the board more expensive the longer a sweep
    ran, which is a rig measuring itself.
    """
    fixture = board.Board()
    for _ in range(10):
        fixture.advance()
    line = next(p for p in fixture.panels() if p["payload"]["chart"] == "line")
    assert len(line["payload"]["data"]) == board.HISTORY


def test_every_chart_kind_is_on_the_fixture_board():
    """Charts were the whole cost of the board, so they are what is measured.

    A kind missing from here is a kind no timing and no picture check covers.
    """
    kinds = {i["payload"]["chart"] for i in board.Board().panels()}
    assert kinds == {"line", "bar", "pie", "area", "radial", "radar"}


def test_four_rounds_that_disagree_are_reported_as_a_range():
    """A mean of four rounds looks more certain than four rounds are."""
    assert report.spread([20.1, 22.9, 21.0]) == "20.1 - 22.9 %"
    assert report.spread([]) == "-"


def test_the_baseline_names_the_floor_that_was_measured_wrong_once():
    """The 67 % floor was a video decoding behind `display:none`. Say so forever."""
    text = "\n".join(report.baseline_lines())
    assert "display:none" in text
    assert "3.3 %" in text
