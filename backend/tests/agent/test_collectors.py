"""What the collectors make of what they read.

None of this runs `nvidia-smi`, `gh` or `tmux`, and none of it reads `/proc`:
most of what a collector does cannot be asserted on a machine without those.
What can be asserted is the half that has actually had the bugs in it — given
this text, produce these rows — which is why each collector now has a `parse`
or a `row` beside the part that goes out and gets it.
"""

from tools.collectors import alerts, cpu, github_commits, gpu, mem, temps, tmux_sessions, trm_run

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


def test_cpu_puts_the_threads_of_one_core_side_by_side():
    """This machine enumerates them 0,4 — opposite spokes, so one core would
    draw as two spikes on opposite sides of the ring instead of one lobe."""
    split = {str(n): f"{n % 4},{n % 4 + 4}" for n in range(8)}
    rows = [{"core": str(n), "use": 0.0} for n in range(8)]
    assert [row["core"] for row in cpu.paired(rows, split)] == list("04152637")


def test_cpu_leaves_the_order_alone_when_there_is_no_topology_to_read():
    """A container publishes no sibling map, and kernel order is the fallback."""
    rows = [{"core": str(n), "use": 0.0} for n in range(4)]
    assert cpu.paired(rows, {}) == rows


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


DF = """\
Filesystem     Type 1024-blocks      Used Available Capacity Mounted on
/dev/sdb2      ext4   229695416 152000000  66000000      71% /
/dev/sda1      ext4   977272000 900000000  27000000      97% /mnt/d_drive
tmpfs          tmpfs    8000000   8000000         0     100% /run/user/1000
"""

FAILED = """\
sshd.service loaded failed failed OpenSSH Daemon
backup.timer loaded failed failed Nightly backup
"""

JOURNAL = """\
{"_SYSTEMD_UNIT": "kernel", "MESSAGE": "probe failed"}
{"_SYSTEMD_UNIT": "kernel", "MESSAGE": "probe failed again"}
{"SYSLOG_IDENTIFIER": "gdm", "MESSAGE": "no control file"}
not json at all
"""


def test_a_full_disk_is_announced_and_a_comfortable_one_is_not():
    """The gauges already say 71%. An inbox is for what somebody should act on."""
    rows = alerts.full(DF)

    assert [row["title"] for row in rows] == ["/mnt/d_drive is 97% full"]
    assert rows[0]["level"] == "error"


def test_a_tmpfs_at_a_hundred_per_cent_is_not_news():
    """It is memory wearing a disk's clothes, and it is always like that."""
    assert not [row for row in alerts.full(DF, limit=99) if "run/user" in row["title"]]


def test_a_disk_filling_further_keeps_the_same_key():
    """Otherwise every extra per cent is a fresh announcement about one fact."""
    fuller = DF.replace("97%", "98%")

    assert alerts.full(DF)[0]["key"] == alerts.full(fuller)[0]["key"]


def test_every_failed_unit_gets_its_own_line():
    rows = alerts.failed(FAILED, "system")

    assert [row["title"] for row in rows] == [
        "sshd.service has failed",
        "backup.timer has failed",
    ]
    assert all(row["level"] == "error" for row in rows)


def test_a_kernel_that_is_still_installed_is_not_a_reason_to_restart():
    assert alerts.stale_kernel("6.17.1-arch1", ["6.17.1-arch1"]) == []
    assert alerts.stale_kernel("", []) == []


def test_a_kernel_no_longer_on_disk_asks_for_a_restart():
    rows = alerts.stale_kernel("6.17.1-arch1", ["6.18.0-arch1"])

    assert rows[0]["key"] == "reboot"
    assert "6.17.1-arch1" in rows[0]["body"]


def test_errors_are_grouped_by_who_logged_them():
    """Twenty-four identical complaints are one thing to know, not twenty-four."""
    rows = alerts.noisy(JOURNAL)

    assert rows[0]["title"] == "kernel logged 2 errors"
    assert rows[0]["body"] == "probe failed again"


def test_a_single_error_is_not_pluralised():
    assert "1 error" in alerts.noisy(JOURNAL)[1]["title"]
    assert "1 errors" not in alerts.noisy(JOURNAL)[1]["title"]


def test_nothing_upgradable_says_nothing():
    """An empty inbox line is worse than no line: it costs a look and pays nothing."""
    assert alerts.waiting("") == []
    assert alerts.waiting("chromium 150.0-1 -> 151.0-1")[0]["key"] == "updates"


# The training run the board shows itself, with no one pointing it at one. What
# can be asserted here is everything except the looking: the rule that decides a
# run has earned a television, and the shaping of a metrics.csv into rows. Which
# process is on the card, and what /proc says it is running, cannot be.
RECIPE = {
    "ACCUMULATION_STEPS": 128,
    "BATCH_SIZE": 1,
    "MAX_SEQ_LEN": 512,
    "TRAIN_TOKEN_BUDGET": 67_108_864,
    "LATENT_DIM": 960,
    "CLIP_NORM": 1.0,
}

METRICS = """\
step,ce,grad_norm_avg,applied_grad_norm,val_ce,wall_clock
5,11.2801,25.3629,9.0884,,2026-09-15T22:47:40Z
20,10.1878,18.4210,4.4013,10.5832,2026-09-15T22:53:12Z
480,4.5579,5.9479,1.4027,4.6163,2026-09-16T01:57:12Z
"""


def test_a_run_too_small_or_too_short_does_not_get_the_television():
    """The rule is scale and duration. A smoke test and a toy ablation are work
    in progress, and nobody watches those from a sofa."""
    assert trm_run.worth_watching(RECIPE)
    assert not trm_run.worth_watching({**RECIPE, "TRAIN_TOKEN_BUDGET": 1_000_000})
    assert not trm_run.worth_watching({**RECIPE, "LATENT_DIM": 128})


def test_a_run_that_recorded_no_budget_is_refused_rather_than_guessed_at():
    """Without one there is no telling an hour of training from a minute of it,
    and the gauge has nothing to be a proportion of."""
    assert not trm_run.worth_watching({k: v for k, v in RECIPE.items() if "BUDGET" not in k})


def test_a_step_is_worth_what_the_run_s_own_recipe_says():
    """Those constants have been re-tuned before, and an old run's steps are
    worth what they were worth when it ran."""
    assert trm_run.tokens_per_opt_step(RECIPE) == 131_072
    assert trm_run.tokens_per_opt_step({}) == 0


def test_the_series_is_thinned_from_the_middle_and_not_from_the_start():
    """A month-long run has more rows than a widget has pixels. What it is about
    is where it started and where it is going, so the ends stay."""
    rows = [{"step": str(n)} for n in range(100)]
    thinned = trm_run.sample(rows, 10)

    assert len(thinned) == 10
    assert thinned[0]["step"] == "0"
    assert thinned[-1]["step"] == "99"


def test_a_run_shorter_than_the_sample_is_left_alone():
    rows = [{"step": "1"}, {"step": "2"}]
    assert trm_run.sample(rows, 60) == rows


def test_a_half_written_last_row_is_dropped_rather_than_drawn():
    """The trainer is appending to this file while it is read."""
    torn = METRICS + "485,4.51"
    assert len(trm_run.measurements(torn)) == 3
    assert trm_run.measurements("step,ce\n") == []


def test_the_curve_is_tokens_against_loss_and_carries_the_probe_forward():
    """val_ce is measured every few hundred steps; a measurement holds until it
    is taken again, and sixty separate points draw as nothing with dots off."""
    drawn = trm_run.curve(trm_run.measurements(METRICS), RECIPE)

    assert drawn[0] == {"tokens": 0.7, "train": 11.28}  # no probe yet, no key
    assert drawn[1] == {"tokens": 2.6, "train": 10.188, "held": 10.583}
    assert drawn[2]["tokens"] == 62.9


def test_the_gauge_spells_its_reading_out_and_never_passes_a_full_ring():
    """The ring carries the proportion, so the words carry what it cannot."""
    rows = trm_run.measurements(METRICS)
    overshot = {**RECIPE, "TRAIN_TOKEN_BUDGET": 20_000_000}

    assert trm_run.progress(rows, RECIPE)[0] == {"label": "62.9/67.1M", "pct": 93.8}
    assert trm_run.progress(rows, overshot)[0]["pct"] == 100.0


def test_the_gradient_norm_is_drawn_in_multiples_of_its_clip():
    """So the threshold the panel draws at 1 is the clip, whatever the clip is."""
    bars = trm_run.health(trm_run.measurements(METRICS), {**RECIPE, "CLIP_NORM": 2.0})

    assert [bar["norm"] for bar in bars] == [4.544, 2.201, 0.701]


def test_an_older_run_without_the_applied_norm_falls_back_to_the_average():
    """The column arrived later than some of the runs still on this disk."""
    older = METRICS.replace(",9.0884,", ",,")
    assert trm_run.health(trm_run.measurements(older), RECIPE)[0]["norm"] == 25.363


def test_constants_are_read_and_not_run():
    """Importing trm.config pulls JAX in and could touch the card, which is the
    one thing a board is never allowed to do."""
    read = trm_run.constants("LATENT_DIM = 960\nBUDGET = int(os.environ['X'])\nARCH = 'plain'\n")
    assert read == {"LATENT_DIM": 960}
