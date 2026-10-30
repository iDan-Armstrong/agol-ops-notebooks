"""Keep the committed notebooks honest: valid, in sync with their source, and thin."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO = Path(__file__).parents[1]
NOTEBOOKS = sorted((REPO / "notebooks").glob("*.ipynb"))


def test_notebooks_exist() -> None:
    names = {p.name for p in NOTEBOOKS}
    assert {"content_audit.ipynb", "scheduled_layer_refresh.ipynb",
            "hosted_layer_qa.ipynb"} <= names


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_is_valid_and_outputs_stripped(path: Path) -> None:
    nb = json.loads(path.read_text())
    assert nb["nbformat"] == 4
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [], f"{path.name}: committed outputs (strip before commit)"
            assert cell["execution_count"] is None


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_code_cells_parse(path: Path) -> None:
    nb = json.loads(path.read_text())
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]), filename=f"{path.name}:cell{i}")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_no_credentials_in_cells(path: Path) -> None:
    nb = json.loads(path.read_text())
    code = "\n".join(
        "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"
    ).lower()
    for needle in ("password", "client_secret", "token="):
        assert needle not in code, f"{path.name}: possible credential ({needle})"
    assert 'gis("home")' in code, f"{path.name}: hosted notebooks must use GIS('home')"


def test_notebooks_in_sync_with_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The .ipynb files are generated; a hand-edit that skips the builder fails here."""
    # load the builder by file path: scripts/ is not a package, and bare
    # `pytest` (as CI runs it) does not put the repo root on sys.path
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_notebooks", REPO / "scripts" / "build_notebooks.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)

    monkeypatch.setattr(builder, "OUT", tmp_path)
    builder.main()
    for path in NOTEBOOKS:
        rebuilt = (tmp_path / path.name).read_text()
        assert json.loads(rebuilt) == json.loads(path.read_text()), (
            f"{path.name} drifted from scripts/build_notebooks.py — rerun the builder"
        )
