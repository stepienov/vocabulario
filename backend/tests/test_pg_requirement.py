"""REQUIRE_PG_TESTS: CI nie może być zielone, gdy testy `pg` się nie wykonały."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_CONFTEST = Path(__file__).with_name("conftest.py")


def _run(tmp_path: Path, body: str, *, require: str | None, url: str | None):
    # parents[2] kopii conftest to katalog bez .env, więc adres bierze się tylko z env.
    tests_dir = tmp_path / "repo" / "backend" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "conftest.py").write_text(_CONFTEST.read_text(encoding="utf-8"), encoding="utf-8")
    (tests_dir / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    pg: database test\n", encoding="utf-8"
    )
    (tests_dir / "test_sample.py").write_text(body, encoding="utf-8")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"REQUIRE_PG_TESTS", "TEST_DATABASE_URL", "DATABASE_URL"}
    }
    env["PYTHONIOENCODING"] = "utf-8"
    if require is not None:
        env["REQUIRE_PG_TESTS"] = require
    if url is not None:
        env["TEST_DATABASE_URL"] = url
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-rs"],
        cwd=tests_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    return proc.returncode, proc.stdout + proc.stderr


_ONE_PG_TEST = "import pytest\n\n@pytest.mark.pg\ndef test_db():\n    pass\n"
_CLOSED_PORT_URL = "postgresql+asyncpg://nobody@127.0.0.1:1/closed_test"


def test_without_requirement_missing_database_only_skips(tmp_path):
    code, out = _run(tmp_path, _ONE_PG_TEST, require=None, url=None)
    assert code == 0, out
    assert "1 skipped" in out
    assert "did not verify the database" in out


def test_required_without_database_url_stops_before_tests(tmp_path):
    code, out = _run(tmp_path, _ONE_PG_TEST, require="1", url=None)
    assert code == 3, out
    assert "TEST_DATABASE_URL is not set" in out
    assert "passed" not in out


def test_required_with_unreachable_database_stops_before_tests(tmp_path):
    code, out = _run(tmp_path, _ONE_PG_TEST, require="1", url=_CLOSED_PORT_URL)
    assert code == 3, out
    assert "connection failed" in out
    assert "nobody" not in out


def test_unknown_requirement_value_is_rejected(tmp_path):
    code, out = _run(tmp_path, _ONE_PG_TEST, require="ture", url=None)
    assert code == 4, out
    assert "REQUIRE_PG_TESTS must be 1 or 0" in out


@pytest.mark.pg
def test_required_fails_when_a_pg_test_skips_itself(tmp_path):
    body = (
        "import pytest\n\n"
        "@pytest.mark.pg\ndef test_runs():\n    pass\n\n"
        "@pytest.mark.pg\ndef test_gives_up():\n    pytest.skip('placeholder')\n"
    )
    code, out = _run(tmp_path, body, require="1", url=os.environ["DATABASE_URL"])
    assert code == 1, out
    assert "1 passed, 1 skipped" in out
    assert "SKIPPED/XFAIL test_sample.py::test_gives_up" in out
    assert "test_sample.py::test_runs" not in out.split("did not pass", 1)[1]


@pytest.mark.pg
def test_required_fails_when_no_pg_test_is_selected(tmp_path):
    body = "def test_plain():\n    pass\n"
    code, out = _run(tmp_path, body, require="1", url=os.environ["DATABASE_URL"])
    assert code == 3, out
    assert "no tests marked pg were selected" in out


@pytest.mark.pg
def test_required_passes_when_every_pg_test_runs(tmp_path):
    code, out = _run(tmp_path, _ONE_PG_TEST, require="1", url=os.environ["DATABASE_URL"])
    assert code == 0, out
    assert "1 passed" in out
