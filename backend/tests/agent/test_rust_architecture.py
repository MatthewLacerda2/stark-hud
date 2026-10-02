"""The architecture collector: the two readers, and the reduction between them.

Small trees written into `tmp_path`, never the real repositories: those move
every day, and a test that read them would be asserting this week's code.
"""

from pathlib import Path

from collectors import rust_architecture as ra
from collectors import rust_layout


def _write(root: Path, files: dict[str, str]) -> Path:
    """A checkout holding these files."""
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def _package(name: str, deps: str = "", dev: str = "") -> str:
    """A crate's manifest with these dependency lines."""
    return f'[package]\nname = "x-{name}"\n[dependencies]\n{deps}\n[dev-dependencies]\n{dev}\n'


def test_crates_are_joined_by_their_path_dependencies(tmp_path):
    """`path` and `workspace = true` both count; a dev-dependency does not."""
    root = _write(
        tmp_path,
        {
            "Cargo.toml": '[workspace]\n[workspace.dependencies]\nx-core = { path = "crates/core" }\n',
            "crates/core/Cargo.toml": _package("core"),
            "crates/render/Cargo.toml": _package("render", "x-core.workspace = true"),
            "crates/cli/Cargo.toml": _package(
                "cli", 'x-render = { path = "../render" }', 'x-golden = { path = "../golden" }'
            ),
            "crates/golden/Cargo.toml": _package("golden", 'x-core = { path = "../core" }'),
        },
    )

    graph = ra.crates(root, skip={"golden"})

    assert graph == {"render": {"core": 1}, "core": {}, "cli": {"render": 1}}


def test_a_crate_joined_to_nothing_and_a_hidden_copy_are_left_out(tmp_path):
    """A tool beside the project is not part of it, nor is a worktree inside it."""
    root = _write(
        tmp_path,
        {
            "a/Cargo.toml": _package("a", 'x-b = { path = "../b" }'),
            "b/Cargo.toml": _package("b"),
            "tools/lint/Cargo.toml": _package("lint"),
            ".claude/worktrees/q/a/Cargo.toml": _package("a", 'x-b = { path = "../b" }'),
        },
    )

    assert set(ra.crates(root, skip=set())) == {"a", "b"}


def test_one_crate_is_read_as_its_top_level_modules(tmp_path):
    """Plain and grouped `crate::` paths count, comments and tests do not."""
    root = _write(
        tmp_path,
        {
            "Cargo.toml": _package("game"),
            "src/api/mod.rs": "use crate::scene::World;\nuse crate::{audio::Mixer, time};\n",
            "src/scene/mod.rs": "// see crate::api for the caller\n#[cfg(test)]\nuse crate::api;\n",
            "src/scene/scene_tests.rs": "use crate::api::Thing;\n",
            "src/audio/mod.rs": "",
            "src/time/mod.rs": "",
            "src/bin/tool.rs": "use crate::api;\n",
        },
    )

    graph = ra.read(root, skip=set())

    assert graph == {
        "api": {"scene": 1, "audio": 1, "time": 1},
        "scene": {},
        "audio": {},
        "time": {},
    }


def test_an_arrow_another_path_already_implies_is_dropped():
    """`api → scene → components` says `api → components` already."""
    graph = {"api": {"scene": 1, "components": 1}, "scene": {"components": 1}, "components": {}}

    assert ra.reduce(graph) == {("api", "scene"), ("scene", "components")}


def test_a_cycle_survives_the_reduction_as_a_cycle():
    """Inside a cycle only the arrows that keep it a cycle are left."""
    graph = {
        "a": {"b": 1, "c": 1},
        "b": {"c": 1},
        "c": {"a": 1},
        "d": {"a": 1, "b": 1},
    }

    kept = ra.reduce(graph)

    assert {("a", "b"), ("b", "c"), ("c", "a")} <= kept
    assert ("a", "c") not in kept
    # Into the cycle once is enough: from there everything in it is reached.
    assert len([e for e in kept if e[0] == "d"]) == 1


def test_a_mutual_pair_is_one_arrow_with_two_heads(tmp_path):
    """And every box is an icon with no words, a plain one when the name is unknown."""
    flow = ra.flow({"scene": {"navigation": 1}, "navigation": {"scene": 1}, "zorp": {}})

    assert flow["links"] == [{"source": "navigation", "target": "scene", "heads": "both"}]
    assert [n["id"] for n in flow["nodes"]] == ["navigation", "scene", "zorp"]
    assert all(n["icon"].startswith("<svg") and "text" not in n for n in flow["nodes"])
    assert flow["nodes"][2]["icon"] == (ra.ICONS / f"{ra.FALLBACK}.svg").read_text().strip()


def test_every_glyph_the_table_names_is_vendored():
    """A name in the table with no file beside it would fail on the hour, not here."""
    for icon in {*ra.GLYPHS.values(), ra.FALLBACK}:
        assert (ra.ICONS / f"{icon}.svg").is_file(), icon


def test_a_part_sits_above_what_it_uses_and_a_cycle_is_cut_to_rank_it():
    """Dependents at the top, the foundation at the bottom, and no endless loop."""
    arrows = {("app", "scene"), ("scene", "nav"), ("nav", "scene"), ("scene", "core")}

    rows = rust_layout.ranks(["app", "core", "nav", "scene"], arrows)

    assert rows[0] == ["app"]
    assert rows[-1] in (["core"], ["core", "nav"], ["nav", "core"])
    assert sum(len(row) for row in rows) == 4


def test_placed_boxes_are_square_inside_the_widget_and_apart():
    """Each square at the widget's shape, inside 0-1, and none overlapping."""
    graph = {
        "api": {"scene": 1, "audio": 1},
        "scene": {"core": 1},
        "audio": {"core": 1},
        "core": {},
    }

    nodes = ra.flow(graph, aspect=0.9)["nodes"]

    boxes = [(n["x"], n["y"], n["w"], n["h"]) for n in nodes]
    assert all(abs(w * 0.9 - h) < 1e-3 for _, _, w, h in boxes)
    assert all(x >= 0 and y >= 0 and x + w <= 1 and y + h <= 1 for x, y, w, h in boxes)
    for i, (x, y, w, h) in enumerate(boxes):
        for x2, y2, w2, h2 in boxes[i + 1 :]:
            assert x + w <= x2 or x2 + w2 <= x or y + h <= y2 or y2 + h2 <= y


def test_a_title_gets_a_strip_above_the_boxes():
    """The project's name is drawn over the diagram, so no box may sit under it."""
    graph = {"api": {"core": 1}, "core": {}}

    drawn = ra.flow(graph, aspect=1.0, title="rusty")

    assert drawn["title"] == "rusty"
    assert min(n["y"] for n in drawn["nodes"]) >= ra.TITLE_ROOM
    assert max(n["y"] + n["h"] for n in drawn["nodes"]) <= 1


def test_a_box_grows_with_how_many_parts_use_it():
    """The foundation everyone uses is the largest box, a part nobody uses the smallest."""
    graph = {"app": {"api": 1, "core": 1}, "api": {"core": 1}, "core": {}}

    size = {n["id"]: n["h"] for n in ra.flow(graph, aspect=1.0)["nodes"]}

    assert size["core"] > size["api"] > size["app"]


def test_the_search_takes_an_arrow_out_of_a_box_it_ran_through():
    """Straight down a column, `top → bottom` would cross `middle`; it is moved aside."""
    arrows = {("top", "middle"), ("middle", "bottom"), ("top", "bottom"), ("top", "side")}

    _, crowded = rust_layout.place(["bottom", "middle", "side", "top"], arrows, aspect=1.0)

    assert ("bottom", "top") not in crowded


def test_an_arrow_that_cannot_avoid_a_crossing_is_drawn_thinner():
    """Two pairs wired across each other in two rows: whichever way, they cross."""
    graph = {"a": {"x": 1, "y": 1}, "b": {"x": 1, "y": 1}, "x": {}, "y": {}}

    links = ra.flow(graph, aspect=1.0)["links"]

    assert any(link.get("thickness") == rust_layout.THIN for link in links)
    assert all(link.get("thickness", 1) in (1, rust_layout.THIN) for link in links)
