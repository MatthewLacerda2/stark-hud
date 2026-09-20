"""What the process table makes of what it read.

Nothing here reads /proc or runs nvidia-smi. What is asserted is the half that
has had the bugs in it: what `pmon` printed turned into figures, and a pile of
per-pid readings turned into one ordered row per program.
"""

from collectors import processes

# Two graphics clients and one compute client, which is what a desktop with a
# browser on it looks like. `gnome-shell` has no figure for `ccpm`; the columns
# are read by position and a short line must not shift them.
PMON = """\
# gpu         pid   type     fb   ccpm    command
# Idx           #    C/G     MB     MB    name
    0       5673     G     96      0    gnome-shell
    0       5925     G      2      0    Xwayland
    0       6472   C+G    180      0    stark-hud-chrom
"""


def live(token, pid, name, ticks=0, ram=0):
    """One process as `sample` hands it over."""
    return {token: {"pid": pid, "name": name, "ticks": ticks, "ram": ram}}


def test_pmon_is_read_by_position():
    """The header names the columns but nothing separates them, so position is all there is."""
    assert processes.holders(PMON) == {"5673": 96, "5925": 2, "6472": 180}


def test_a_dash_is_not_a_zero():
    """The driver having no figure for a process is not the process holding none."""
    assert processes.holders("    0       7000     G      -      -    something") == {}


def test_processes_of_one_name_are_added_up():
    """Fifty chromium processes are one answer to "what is using the memory"."""
    rows = processes.heaviest(
        {
            **live("1:1", "1", "chromium", ram=200 * 1024**2),
            **live("2:1", "2", "chromium", ram=300 * 1024**2),
        },
        {},
        {},
        0,
        (16 * 1024**3, 6 * 1024**3),
        16,
    )
    assert rows == [{"name": "chromium", "cpu": "", "gpu": "", "ram": "500 MB"}]


def test_video_memory_is_weighed_against_the_card_and_not_against_the_ram():
    """Nearly filling a small card outranks a modest share of a large RAM."""
    rows = processes.heaviest(
        {
            # The trainer holds a tenth of the RAM the editor does, and nearly
            # the whole card.
            **live("1:1", "1", "trainer", ram=1 * 1024**3),
            **live("2:1", "2", "editor", ram=10 * 1024**3),
        },
        {"1": 5 * 1024},
        {},
        0,
        (64 * 1024**3, 6 * 1024**3),
        16,
    )
    assert [row["name"] for row in rows] == ["trainer", "editor"]


def test_the_first_pass_after_a_restart_leaves_the_cpu_column_blank():
    """With no earlier reading there is no window to divide by, and no figure to give."""
    rows = processes.heaviest(
        live("1:1", "1", "thing", ticks=5000), {}, {}, 0, (16 * 1024**3, 6 * 1024**3), 16
    )
    assert rows[0]["cpu"] == ""


def test_cpu_is_the_share_of_the_whole_machine_over_the_window():
    """One core fully busy is one core's worth of the machine, not 100% of it."""
    rows = processes.heaviest(
        live("1:1", "1", "thing", ticks=processes.TICKS * 10),
        {},
        {"1:1": 0},
        10.0,
        (16 * 1024**3, 6 * 1024**3),
        16,
    )
    assert rows[0]["cpu"] == f"{100 / processes.CORES:.0f}%"


def test_a_counter_that_went_backwards_is_not_a_burst():
    """A pid read differently between runs would otherwise read as CPU nobody spent."""
    rows = processes.heaviest(
        live("1:1", "1", "thing", ticks=10),
        {},
        {"1:1": 99999},
        10.0,
        (16 * 1024**3, 6 * 1024**3),
        16,
    )
    assert rows[0]["cpu"] == ""


def test_only_the_heaviest_are_kept():
    """The table has a fixed number of lines, and the rest is not worth a row."""
    many = {}
    for n in range(20):
        many.update(live(f"{n}:1", str(n), f"p{n}", ram=n * 1024**2))
    rows = processes.heaviest(many, {}, {}, 0, (16 * 1024**3, 6 * 1024**3), 3)
    assert [row["name"] for row in rows] == ["p19", "p18", "p17"]


def test_nothing_at_all_draws_no_figure():
    """A column of zeroes is noise; an empty cell says the same thing quietly."""
    assert processes.gigabytes(0) == ""
    assert processes.percent(0) == ""


def test_a_trace_of_cpu_is_not_nothing():
    """Rounding a live process to "0%" says it stopped, which is a different claim."""
    assert processes.percent(0.2) == "<1%"


def test_memory_is_written_the_way_somebody_would_say_it():
    """Megabytes up to a gigabyte, then gigabytes with one decimal."""
    assert processes.gigabytes(500 * 1024**2) == "500 MB"
    assert processes.gigabytes(int(1.7 * 1024**3)) == "1.7 GB"
