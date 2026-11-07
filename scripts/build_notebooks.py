"""Generate the hosted notebooks from source-of-truth cell definitions.

Notebooks are JSON blobs that diff terribly, so the cells live here (reviewable
Python) and this script renders the .ipynb files:

    python scripts/build_notebooks.py

CI re-renders and fails if the committed notebooks drift from this source.
"""

from __future__ import annotations

from pathlib import Path

import nbformat

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "notebooks"

HEADER = (
    "> Runs as an **ArcGIS Online Hosted Notebook** (Standard runtime). "
    "`GIS('home')` uses the notebook's own session — no credentials in code. "
    "Logic lives in the `agolops` package (tested in CI); cells only orchestrate.\n"
)



def install_cell(*repos: str) -> tuple[str, str]:
    """A cell that installs the tested packages from GitHub.

    A hosted notebook starts from a clean runtime with no git, so pip installs the
    GitHub zip archive instead of a git+ URL. Written as Python, not !pip, so the
    cell still parses in CI.
    """
    urls = ",\n".join(
        f'    "https://github.com/iDan-Armstrong/{r}/archive/refs/heads/main.zip"' for r in repos
    )
    return ("code", f"""\
# Install the tested logic (a hosted notebook starts from a clean runtime, without git)
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
{urls},
])""")


CONTENT_AUDIT = [
    ("md", "# Content audit\n" + HEADER + "\nFlags stale, undocumented, unprotected, and "
     "orphaned items, and writes the findings to a CSV item for the content review meeting."),
    install_cell("agol-ops-notebooks"),
    ("code", """\
from arcgis.gis import GIS

from agolops.audit import audit_items, summarize

gis = GIS("home")
MAX_ITEMS = 2000"""),
    ("code", """\
# Pull the item properties the audit needs (plain dicts, so the logic stays testable)
KEYS = ["id", "title", "owner", "modified", "numViews", "description",
        "thumbnail", "access", "licenseInfo", "protected"]

items = [
    {k: getattr(item, k, None) for k in KEYS}
    for item in gis.content.search(query="", max_items=MAX_ITEMS)
]
org_usernames = {u.username for u in gis.users.search(max_users=1000)}
owners_gone = {i["owner"] for i in items} - org_usernames
print(f"{len(items)} items, {len(owners_gone)} departed owners")"""),
    ("code", """\
findings = audit_items(items, orphan_owners=owners_gone)
summarize(findings)"""),
    ("code", """\
import pandas as pd

df = pd.DataFrame([f.__dict__ for f in findings])
df.to_csv("/arcgis/home/content_audit.csv", index=False)
df.head(20)"""),
    ("md", "The CSV lands in the notebook workspace (`/arcgis/home`), from where it can be "
     "added as a portal item or mailed to item owners. Schedule monthly via the notebook's "
     "**Tasks** pane."),
]

LAYER_REFRESH = [
    ("md", "# Scheduled hosted-layer refresh\n" + HEADER + "\nReplaces the contents of a "
     "hosted feature layer from an upstream source, with validation and a shrink guard "
     "**before** anything touches production. Schedule nightly via the **Tasks** pane."),
    install_cell("agol-ops-notebooks"),
    ("code", """\
from arcgis.gis import GIS

from agolops.refresh import plan_refresh, validate_against_layer

gis = GIS("home")

TARGET_ITEM_ID = "REPLACE_WITH_ITEM_ID"   # hosted feature layer to refresh
SOURCE_ITEM_ID = "REPLACE_WITH_ITEM_ID"   # upstream CSV/GeoJSON item (or swap in an API call)
REQUIRED_FIELDS = ["facility_name"]
KEY_FIELD = "facility_id\""""),
    ("code", """\
# Fetch new rows from the source item
import json

source = gis.content.get(SOURCE_ITEM_ID)
rows = json.loads(source.get_data(try_json=False).decode())  # expects a list of dicts
print(f"source rows: {len(rows)}")"""),
    ("code", """\
# Validate against the live layer, then decide
target = gis.content.get(TARGET_ITEM_ID)
layer = target.layers[0]
layer_fields = [f.name for f in layer.properties.fields]
current_count = layer.query(return_count_only=True)

validation = validate_against_layer(rows, layer_fields, REQUIRED_FIELDS, KEY_FIELD)
plan = plan_refresh(len(rows), current_count, validation)
print(plan)
if plan.action == "abort":
    raise SystemExit(plan.reason)  # scheduled run shows as Failed, nobody loses data"""),
    ("code", """\
# Execute: truncate + chunked append (keeps the layer, its item id, and all its references)
layer.manager.truncate()
features = [{"attributes": row} for row in rows]
for start in range(0, len(features), plan.chunk_size):
    chunk = features[start : start + plan.chunk_size]
    result = layer.edit_features(adds=chunk)
    failed = [r for r in result["addResults"] if not r["success"]]
    if failed:
        raise RuntimeError(f"append failed at offset {start}: {failed[:3]}")
print(f"replaced {current_count} -> {len(features)} features in {plan.chunks} chunks")"""),
    ("md", "Failure modes are explicit: validation errors or a >20% shrink abort before the "
     "truncate, and a failed chunk raises immediately. The truncate+append pattern (vs. "
     "overwrite) preserves the item id, so maps, apps, and popups keep working."),
]

LAYER_QA = [
    ("md", "# Hosted layer QA\n" + HEADER + "\nRuns attribute QA against a hosted feature "
     "layer using the same rule engine as the ArcGIS Pro toolbox in the companion repo — "
     "one set of rules, every runtime."),
    install_cell("arcgis-qa-toolbox"),
    ("code", """\
from arcgis.gis import GIS

gis = GIS("home")
LAYER_ITEM_ID = "REPLACE_WITH_ITEM_ID"
RULES = {
    "unique_fields": ["facility_id"],
    "rules": [
        {"kind": "not_null", "fields": ["facility_name", "facility_type"]},
        {"kind": "in_set", "field": "facility_type",
         "values": ["clinic", "hospital", "health_post", "pharmacy"]},
        {"kind": "range", "field": "beds", "min": 0, "max": 500},
    ],
}"""),
    ("code", """\
from qacore.rules import Rule, run_rules  # same engine as the Pro toolbox

layer = gis.content.get(LAYER_ITEM_ID).layers[0]
oid_field = layer.properties.objectIdField
fields = sorted({f for r in RULES["rules"] for f in r.get("fields", [r.get("field")])} |
                set(RULES["unique_fields"]))

feature_set = layer.query(out_fields=[oid_field, *fields], return_geometry=False)
records = ((f.attributes[oid_field], {k: f.attributes.get(k) for k in fields})
           for f in feature_set.features)

summary = run_rules(records, [Rule.from_config(r) for r in RULES["rules"]],
                    RULES["unique_fields"])
print("\\n".join(summary.to_lines()))"""),
    ("md", "Failing OIDs can be fed straight back into `layer.query` for review, or the "
     "summary posted to the team channel. Schedule weekly; pair with the refresh notebook "
     "so QA runs the morning after each load."),
]

NOTEBOOKS = {
    "content_audit.ipynb": CONTENT_AUDIT,
    "scheduled_layer_refresh.ipynb": LAYER_REFRESH,
    "hosted_layer_qa.ipynb": LAYER_QA,
}


def build(cells: list[tuple[str, str]]) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "esriNotebookRuntime": {
            "notebookRuntimeName": "ArcGIS Notebook Python 3 Standard",
            "notebookRuntimeVersion": "11.0",
        },
    }
    for i, (kind, text) in enumerate(cells):
        cell = (
            nbformat.v4.new_markdown_cell(text)
            if kind == "md"
            else nbformat.v4.new_code_cell(text)
        )
        cell["id"] = f"cell-{i}"  # deterministic ids keep notebook diffs readable
        nb.cells.append(cell)
    return nb


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        path = OUT / name
        nbformat.write(build(cells), path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
