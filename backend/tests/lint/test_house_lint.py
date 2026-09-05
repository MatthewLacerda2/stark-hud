"""Tests proving the custom house linter behaves as specified."""

from pathlib import Path

from lint import house_lint


def test_too_long_file_fails():
    source = "\n".join(f"x = {i}" for i in range(house_lint.MAX_FILE_LINES + 5))
    violations = house_lint.check_source(Path("app/big.py"), source)
    assert any("file has" in v for v in violations)


def test_data_file_marker_exempts():
    body = "\n".join(f"x = {i}" for i in range(house_lint.MAX_FILE_LINES + 5))
    source = f"{house_lint.DATA_FILE_MARKER}\n{body}"
    violations = house_lint.check_source(Path("app/data.py"), source)
    assert violations == []


def test_long_handler_fails():
    lines = ["@router.get('/x')", "def handler():"]
    lines += [f"    a{i} = {i}" for i in range(house_lint.MAX_HANDLER_LINES + 1)]
    source = "\n".join(lines)
    violations = house_lint.check_source(Path("api/v1/x.py"), source)
    assert any("handler 'handler'" in v for v in violations)


def test_long_test_fails():
    lines = ["def test_big():"]
    lines += [f"    a{i} = {i}" for i in range(house_lint.MAX_TEST_LINES + 1)]
    source = "\n".join(lines)
    violations = house_lint.check_source(Path("tests/test_x.py"), source)
    assert any("test 'test_big'" in v for v in violations)


def test_tests_dir_exempt_from_file_length():
    source = "\n".join(f"x = {i}" for i in range(house_lint.MAX_FILE_LINES + 5))
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

    assert house_lint.layer_of(Path("/srv/backend/services/board.py"), root) == "services"
    assert house_lint.layer_of(Path("/srv/backend/main.py"), root) is None
    assert house_lint.layer_of(Path("/elsewhere/thing.py"), root) is None
