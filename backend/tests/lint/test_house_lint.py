"""Tests proving the custom house linter behaves as specified.

Every rule is reached through `house_lint.check_source`, which is what the gate
runs, rather than through the module each rule now lives in: the point of a rule
is what the linter says about a file, and which of the two modules holds it is
this file's business and not the rule's.
"""

from pathlib import Path

from lint import boundaries, house_lint, limits


def test_too_long_file_fails():
    source = "\n".join(f"x = {i}" for i in range(limits.MAX_FILE_LINES + 5))
    violations = house_lint.check_source(Path("app/big.py"), source)
    assert any("file has" in v for v in violations)


def test_data_file_marker_exempts():
    body = "\n".join(f"x = {i}" for i in range(limits.MAX_FILE_LINES + 5))
    source = f"{limits.DATA_FILE_MARKER}\n{body}"
    violations = house_lint.check_source(Path("app/data.py"), source)
    assert violations == []


def test_a_docstring_that_explains_the_marker_is_not_the_marker():
    """The hole this linter fell into itself: the scan was a substring search,
    and the sentence documenting the escape hatch *was* the escape hatch, so the
    one file exempt from the length rule was the file that enforces it."""
    prose = f'"""Rule 1 exempts a file carrying a ``{limits.DATA_FILE_MARKER}`` marker."""'
    body = "\n".join(f"x = {i}" for i in range(limits.MAX_FILE_LINES + 5))
    violations = house_lint.check_source(Path("lint/rules.py"), f"{prose}\n{body}")
    assert any("file has" in v for v in violations)


def test_the_marker_has_to_be_the_whole_line():
    """A comment that mentions the marker in passing is prose too."""
    body = "\n".join(f"x = {i}" for i in range(limits.MAX_FILE_LINES + 5))
    mention = f"# set by {limits.DATA_FILE_MARKER} elsewhere"
    violations = house_lint.check_source(Path("app/data.py"), f"{mention}\n{body}")
    assert any("file has" in v for v in violations)


def test_the_marker_below_the_header_does_not_exempt():
    """Fifteen lines, so it is a decision at the top of a file and not a line
    buried where the next reader will not see it."""
    body = "\n".join(f"x = {i}" for i in range(limits.MAX_FILE_LINES + 5))
    late = "\n".join(["x = 0"] * 20 + [limits.DATA_FILE_MARKER, body])
    violations = house_lint.check_source(Path("app/data.py"), late)
    assert any("file has" in v for v in violations)


def test_long_handler_fails():
    lines = ["@router.get('/x')", "def handler():"]
    lines += [f"    a{i} = {i}" for i in range(limits.MAX_HANDLER_LINES + 1)]
    source = "\n".join(lines)
    violations = house_lint.check_source(Path("api/v1/x.py"), source)
    assert any("handler 'handler'" in v for v in violations)


def test_long_test_fails():
    lines = ["def test_big():"]
    lines += [f"    a{i} = {i}" for i in range(limits.MAX_TEST_LINES + 1)]
    source = "\n".join(lines)
    violations = house_lint.check_source(Path("tests/test_x.py"), source)
    assert any("test 'test_big'" in v for v in violations)


def test_tests_dir_exempt_from_file_length():
    source = "\n".join(f"x = {i}" for i in range(limits.MAX_FILE_LINES + 5))
    violations = house_lint.check_source(Path("tests/test_huge.py"), source)
    assert all("file has" not in v for v in violations)


def test_clean_input_passes():
    source = "@router.get('/ok')\ndef ok():\n    return 1\n"
    violations = house_lint.check_source(Path("api/v1/ok.py"), source)
    assert violations == []


def test_a_repository_reaching_up_into_services_fails():
    """The one rule the whole layered stack rests on."""
    source = "from services import board\n"
    violations = house_lint.check_source(Path("repositories/board.py"), source, "repositories")

    assert any("is above it" in v for v in violations)


def test_schemas_may_not_reach_the_repository():
    source = "import repositories.board\n"
    violations = house_lint.check_source(Path("schemas/board.py"), source, "schemas")

    assert any("schemas/ imports repositories/" in v for v in violations)


def test_descending_the_stack_is_fine():
    """A service reading its repository is the shape the whole thing is built in."""
    source = "from repositories import board\nfrom schemas.board import ItemRead\n"

    assert house_lint.check_source(Path("services/board.py"), source, "services") == []


def test_a_file_outside_the_stack_may_import_anything():
    """main.py wires the layers together and tests reach wherever they need to."""
    source = "from api.v1 import board\nfrom repositories import board as repo\n"

    assert house_lint.check_source(Path("main.py"), source, None) == []


def test_the_layer_is_found_whether_the_root_is_relative_or_absolute():
    """A check that inspects nothing passes, which is worse than one that fails."""
    root = Path("/srv/backend")

    assert boundaries.layer_of(Path("/srv/backend/services/board.py"), root) == "services"
    assert boundaries.layer_of(Path("/srv/backend/main.py"), root) is None
    assert boundaries.layer_of(Path("/elsewhere/thing.py"), root) is None


def test_a_surface_may_not_reach_the_socket_hub():
    """Rule 5: announcing a change belongs to the service that makes it.

    Nothing can check for a broadcast that was never written, so what is checked
    is that there is one place left in the stack to write one.
    """
    source = "from core.hub import hub\n"
    violations = house_lint.check_source(Path("api/v1/board.py"), source, "api")

    assert any("services/events.py may do" in v for v in violations)


def test_the_events_module_is_the_one_that_may():
    """And it is the only file in the stack that can, named rather than inferred."""
    source = "from core.hub import hub\n"
    violations = house_lint.check_source(Path("services/events.py"), source, "services")

    assert violations == []


def test_outside_the_stack_still_holds_the_socket():
    """main.py owns the websocket route and the tests listen on it."""
    assert house_lint.check_source(Path("main.py"), "import core.hub\n", None) == []


def test_a_surface_may_read_a_repository_directly():
    """Rule 6: every read in api/ and hud_mcp/ today is a handler fetching its widget."""
    source = "from repositories import board as repo\n\ndef f():\n    return repo.get_by_key(k)\n"

    assert house_lint.check_source(Path("api/v1/board.py"), source, "api") == []


def test_a_surface_may_not_write_to_a_repository():
    """The half of the layering worth enforcing: a write carries rules and an event."""
    source = "from repositories import board as repo\n\ndef f():\n    repo.add(item)\n"
    violations = house_lint.check_source(Path("api/v1/board.py"), source, "api")

    assert any("write through services/" in v for v in violations)


def test_the_module_need_not_be_called_repo():
    """The alias is resolved from the import, not assumed, and a dotted name works too."""
    plain = "from repositories import board\n\ndef f():\n    board.set_ink(c)\n"
    dotted = "import repositories.board\n\ndef f():\n    repositories.board.remove(i)\n"

    assert house_lint.check_source(Path("hud_mcp/layout.py"), plain, "hud_mcp")
    assert house_lint.check_source(Path("api/v1/mesh.py"), dotted, "api")


def test_a_write_imported_by_name_is_caught_at_the_import():
    """``from repositories.board import add`` leaves a call check nothing to see."""
    source = "from repositories.board import add, get\n"
    violations = house_lint.check_source(Path("hud_mcp/groups.py"), source, "hud_mcp")

    assert len(violations) == 1
    assert "repositories.add" in violations[0]


def test_an_unfamiliar_repository_function_is_stopped_not_waved_through():
    """Why the rule is an allowlist: the function nobody has written yet fails safe.

    A denylist of write-ish names would pass this, and the boundary would move
    without anyone deciding that it should.
    """
    source = "from repositories import board as repo\n\ndef f():\n    repo.archive(i)\n"

    assert house_lint.check_source(Path("api/v1/board.py"), source, "api")


def test_services_write_to_repositories_for_a_living():
    """Only the surfaces are checked; below them writing to the store is the job."""
    source = "from repositories import board as repo\n\ndef f():\n    repo.add(item)\n"

    assert house_lint.check_source(Path("services/board.py"), source, "services") == []
