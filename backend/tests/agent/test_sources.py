"""The sources file: what it declares, and what happens when it is edited.

This is the half of the agent that changed when the file moved to `state/`.
Editing it has to land on the television without a restart, and a bad save has
to cost a line in the log rather than the board — both of which are cheap to
prove here and impossible to prove by looking at the screen.

The modules are imported the way they are on the host, where `agent.py` is run
as a script and finds `sources.py` beside it (`backend/pytest.ini` puts `tools/`
on the path for exactly that).
"""

from agent import EXAMPLE_CONFIG, configured
from sources import JOB, PANEL, Declared, Source, expand, fault

CPU = """
[[source]]
name = "cpu"
command = "true"
every = 3
panel = { kind = "chart" }
"""

CPU_AND_MEM = (
    CPU
    + """
[[source]]
name = "mem"
command = "true"
panel = { kind = "chart" }
"""
)


def _file(tmp_path, text):
    """A sources file holding this."""
    path = tmp_path / "sources.toml"
    path.write_text(text)
    return path


def test_a_source_added_to_the_file_is_running_a_second_later(tmp_path):
    """The point of the whole thing: a new panel is a save, not a restart."""
    declared = Declared(_file(tmp_path, CPU))
    assert [source.name for source in declared.refresh()] == ["cpu"]

    _file(tmp_path, CPU_AND_MEM)

    assert [source.name for source in declared.refresh()] == ["cpu", "mem"]


def test_an_untouched_file_is_not_re_read(tmp_path):
    """Looked at every second, so it has to be free when nothing has changed."""
    declared = Declared(_file(tmp_path, CPU))
    first = declared.refresh()

    assert declared.refresh() is first
    assert declared.refresh()[0] is first[0]


def test_a_reload_keeps_the_history_a_chart_has_been_filling(tmp_path):
    """A saved file must not blank a line that has been drawing for an hour."""
    path = _file(tmp_path, CPU.replace("every = 3", "every = 3\nhistory = 4"))
    declared = Declared(path)
    declared.refresh()[0].payload([{"t": 1}])
    path.write_text(CPU.replace("every = 3", "every = 3\nhistory = 4") + "\n# edited\n")

    assert declared.refresh()[0].payload([{"t": 2}])["data"] == [{"t": 1}, {"t": 2}]


def test_a_reload_does_not_announce_what_was_already_announced(tmp_path):
    """An inbox that repeats itself every time somebody edits a line is worse."""
    alerts = '[[source]]\nname = "alerts"\ncommand = "true"\nnotifications = true\n'
    path = _file(tmp_path, alerts)
    declared = Declared(path)
    declared.refresh()[0].news([{"title": "/ is 91% full"}])
    path.write_text(alerts + "\n# edited\n")

    assert declared.refresh()[0].news([{"title": "/ is 91% full"}]) == []


def test_a_source_nobody_edited_keeps_its_place_in_the_schedule(tmp_path):
    """Else editing one line makes every other source run again at once."""
    path = _file(tmp_path, CPU_AND_MEM)
    declared = Declared(path)
    declared.refresh()[0].due = 900.0
    path.write_text(CPU_AND_MEM.replace('name = "mem"', 'name = "ram"') + "\n# edited\n")

    cpu, ram = declared.refresh()
    assert (cpu.due, ram.due) == (900.0, 0.0)


def test_half_a_save_leaves_the_last_good_sources_running(tmp_path):
    """A file is not written atomically, and a blank television is not a
    reasonable answer to catching one mid-write."""
    path = _file(tmp_path, CPU)
    declared = Declared(path)
    declared.refresh()
    path.write_text("[[source]]\nname = ")

    assert [source.name for source in declared.refresh()] == ["cpu"]


def test_a_source_that_could_not_work_rejects_the_save_it_arrived_in(tmp_path):
    """All or nothing: half a board is the hardest kind of wrong to notice."""
    path = _file(tmp_path, CPU)
    declared = Declared(path)
    declared.refresh()
    path.write_text(CPU + '\n[[source]]\nname = "nothing"\nevery = 5\n')

    assert [source.name for source in declared.refresh()] == ["cpu"]


def test_what_makes_a_source_unusable_is_said_plainly():
    assert fault({"name": "x", "panel": {}}) is None
    assert fault({"name": "x", "command": "true"}) is None
    assert "no name" in fault({"command": "true"})
    assert "no command" in fault({"name": "x", "notifications": True})


def test_a_command_with_no_panel_is_a_job_and_one_with_a_panel_is_not():
    """How a watcher in state/ gets to be a source like any other."""
    assert Source({"name": "trm", "command": "true"}).kind == JOB
    assert Source({"name": "cpu", "command": "true", "panel": {}}).kind == PANEL


def test_a_job_that_is_still_running_is_left_alone(tmp_path):
    """A render takes minutes; a second one on top of it would take longer."""
    job = Source({"name": "slow", "command": "sleep 3"})
    job.start(tmp_path)
    started = job.process
    job.start(tmp_path)

    assert job.process is started
    started.kill()
    started.wait()


def test_a_job_that_finished_is_started_again(tmp_path):
    job = Source({"name": "quick", "command": "true"})
    job.start(tmp_path)
    first = job.process
    first.wait()
    job.start(tmp_path)

    assert job.process is not first
    job.process.wait()


def test_a_command_is_told_where_the_kit_and_this_instance_are(tmp_path):
    """Neither is knowable to whoever wrote the config."""
    command = expand("python3 {state}/watch.py {collectors}/cpu.py", tmp_path)

    assert command.startswith(f"python3 {tmp_path}/watch.py ")
    assert command.endswith("tools/collectors/cpu.py")


def test_a_named_config_is_the_one_that_runs(tmp_path):
    assert configured(tmp_path / "other.toml") == tmp_path / "other.toml"


def test_the_shipped_example_is_a_board_a_fresh_clone_can_run():
    """With no state/ there is nothing else to run, so this has to stay valid."""
    declared = Declared(EXAMPLE_CONFIG)
    names = [source.name for source in declared.refresh()]

    assert "cpu" in names
    assert all(fault(source.spec) is None for source in declared.sources)


def test_a_file_that_vanishes_leaves_the_board_as_it_was(tmp_path):
    """Deleting it is the one thing that must not clear the television."""
    path = _file(tmp_path, CPU)
    declared = Declared(path)
    declared.refresh()
    path.unlink()

    assert [source.name for source in declared.refresh()] == ["cpu"]


def test_a_source_declaring_no_page_leaves_the_board_to_say_where_its_panel_goes():
    """The compatibility claim, against the file a fresh clone actually runs.

    Every source written before a source could name a page leaves it out, and a
    source that leaves it out sends nothing — so the board decides for it,
    exactly as the board always did.
    """
    declared = Declared(EXAMPLE_CONFIG).refresh()
    quiet = [source for source in declared if "page" not in source.spec]

    assert quiet and all(source.page == "" for source in quiet)
    assert [source.name for source in declared if source.page] == ["disk"]


def test_a_page_written_with_spaces_around_it_is_the_page_without_them(tmp_path):
    """A name is a name. Two pages differing by a typed space is a panel lost."""
    declared = Declared(_file(tmp_path, CPU.replace("every = 3", 'page = " machine "')))

    assert declared.refresh()[0].page == "machine"
