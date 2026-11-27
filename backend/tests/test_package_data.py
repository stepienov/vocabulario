import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def test_every_runtime_asset_is_declared_as_package_data():
    # The Docker image runs from site-packages, so undeclared assets are missing in production.
    config = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["app"]
    declared = {path for pattern in patterns for path in APP.glob(pattern) if path.is_file()}
    assets = {
        path
        for path in APP.rglob("*")
        if path.is_file() and path.suffix not in {".py", ".pyc"} and "__pycache__" not in path.parts
    }
    assert sorted(p.relative_to(APP).as_posix() for p in assets - declared) == []
