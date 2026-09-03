"""What the collectors make of what they read.

None of this runs `nvidia-smi`, `gh` or `tmux`, and none of it reads `/proc`:
most of what a collector does cannot be asserted on a machine without those.
What can be asserted is the half that has actually had the bugs in it — given
this text, produce these rows — which is why each collector now has a `parse`
or a `row` beside the part that goes out and gets it.
"""

from tools.collectors import cpu, github_commits, gpu, mem, temps, tmux_sessions

PROC_STAT = """\
cpu  100 0 100 800 0 0 0 0 0 0
cpu0 10 0 10 80 0 0 0 0 0 0
cpu1 20 0 20 60 0 0 0 0 0 0
intr 1 2 3
"""

MEMINFO = """\
MemTotal:       16000000 kB
MemFree:          500000 kB
MemAvailable:    8000000 kB
Buffers:          100000 kB
"""


def test_cpu_skips_the_aggregate_line():
    """A bar for "all of them at once" would read as one more, always average."""
    assert sorted(cpu.parse(PROC_STAT)) == ["cpu0", "cpu1"]


def test_cpu_measures_the_window_and_not_the_uptime():
    """Busy is the difference between two readings, which is what htop shows."""
    first = {"cpu0": (100, 80)}
    second = {"cpu0": (200, 130)}
    assert cpu.busy(first, second) == [{"core": "0", "use": 50.0}]


def test_a_window_with_nothing_in_it_reads_as_idle():
    """Two readings a moment apart divide by zero otherwise."""
    assert cpu.busy({"cpu0": (100, 80)}, {"cpu0": (100, 80)}) == [{"core": "0", "use": 0.0}]


def test_memory_counts_the_cache_as_available():
    """Free memory on Linux is not memory you can have; available is."""
    row = mem.row(mem.parse(MEMINFO))
    assert row["use"] == 50.0
    assert row["size"] == "7.6/15.3 GB"


def test_memory_falls_back_when_the_kernel_is_too_old_for_available():
    """MemAvailable arrived in 3.14; without it, free is the only answer there is."""
    fields = mem.parse(MEMINFO)
    del fields["MemAvailable"]
    assert mem.row(fields)["use"] == 96.9


def test_the_gpu_gauge_says_what_it_was_asked_for():
    """One metric per call, because a gauge shows one number."""
    reading = "42, 4096, 8192"
    assert gpu.row(reading, "util") == {"label": "", "pct": 42.0}
    assert gpu.row(reading, "vram") == {
        "label": "",
        "size": "4.0/8 GB",
        "pct": 50.0,
    }


def test_a_temperature_that_could_not_be_read_is_left_out():
    """A zero on this chart is a cold CPU, which is a lie; a gap is the truth."""
    assert temps.row(51.0, None, "12:00:00") == {"t": "12:00:00", "cpu": 51.0}
    assert temps.row(None, None, "12:00:00") == {"t": "12:00:00"}


def test_hwmon_reports_thousandths_of_a_degree():
    """51000 is 51 degrees, and printing it raw once put the board in the sun."""
    assert temps.milli("51000\n") == 51.0


def test_no_tmux_sessions_is_an_empty_list_and_not_a_blank_line():
    """A list panel given [''] draws one empty row, which reads as a bug."""
    assert tmux_sessions.names("") == []
    assert tmux_sessions.names("one\ntwo\n") == ["one", "two"]


def test_a_commit_feed_takes_the_first_line_and_the_committer_date():
    """A rebased commit keeps the date it was written, which reads as time travel."""
    found = {
        "items": [
            {
                "commit": {
                    "message": "Fix the thing\n\nAnd why.",
                    "author": {"date": "2020-01-01T00:00:00Z"},
                    "committer": {"date": "2026-09-01T00:00:00Z"},
                },
                "repository": {"name": "stark-hud"},
            }
        ]
    }
    assert github_commits.entries(found) == [
        {
            "title": "Fix the thing",
            "source": "stark-hud",
            "at": "2026-09-01T00:00:00Z",
        }
    ]


def test_a_commit_missing_its_committer_costs_that_line_and_no_more():
    """Somebody else's JSON: one odd entry should not blank the whole panel."""
    found = {"items": [{"commit": {"message": "no date"}}, {"nothing": True}]}
    assert github_commits.entries(found) == []


def test_a_search_that_failed_is_not_an_empty_feed():
    """None means the call did not happen; the agent leaves the last good panel up."""
    assert github_commits.entries(None) == []
