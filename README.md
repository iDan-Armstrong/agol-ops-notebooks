# agol-ops-notebooks — ArcGIS Online administration, tested

![CI](https://github.com/iDan-Armstrong/agol-ops-notebooks/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)

Three **ArcGIS Online Hosted Notebooks** for the unglamorous work that keeps an org
healthy, built on a principle: *notebooks orchestrate, packages decide.* Hosted
notebooks are a great scheduler and a terrible place for logic — they can't be
unit-tested or meaningfully code-reviewed — so every decision lives in the `agolops`
package, where pytest reaches it in CI with no portal and no license.

## The notebooks

| Notebook | Schedule | What it does |
|---|---|---|
| `content_audit.ipynb` | monthly | Flags stale, undocumented, unprotected, publicly-shared-unreviewed, and orphaned items; writes a findings CSV for the content review |
| `scheduled_layer_refresh.ipynb` | nightly | Replaces a hosted feature layer from an upstream source — **after** field/null/duplicate validation and a shrink guard that refuses to truncate production when the source comes back suspiciously small |
| `hosted_layer_qa.ipynb` | weekly | Runs declarative attribute QA against a hosted layer using the same rule engine as my [arcgis-qa-toolbox](../arcgis-qa-toolbox) Pro toolbox — one rule set, every runtime |

Design choices worth a reviewer's attention:

- **The shrink guard** (`agolops/refresh.py`): an upstream outage returning a
  near-empty extract must never let a scheduled job truncate production. >20% shrink
  aborts with an explanation; the scheduled run shows as Failed; nobody loses data.
- **Truncate + chunked append, not overwrite**, preserves the layer's item id, so every
  map, app, and popup that references it keeps working.
- **`GIS("home")` only.** Hosted notebooks authenticate as their own session; there is a
  test asserting no credential-shaped strings ever appear in a notebook.
- **Notebooks are generated** (`scripts/build_notebooks.py`) because .ipynb JSON diffs
  terribly; CI fails if a committed notebook drifts from its reviewable source. Outputs
  are always stripped.

## Deploy

1. Add each `.ipynb` as a Notebook item (Content, then New item, then the file).
2. Fill in the `REPLACE_WITH_ITEM_ID` constants.
3. Run it once. The first code cell installs the tested packages from this repo (and,
   for the QA notebook, `qacore` from the companion repo). It installs the GitHub zip
   archive because the hosted runtime has no `git`.
4. Schedule under the notebook's **Tasks** pane per the table above.

The content audit and the hosted layer QA were run in a live ArcGIS Online org
(Standard runtime 14.0) with this install step, from the GitHub zip archive.

## Develop

```bash
pip install -e ".[dev]"
pytest                               # logic + notebook validity/sync/credential tests
python scripts/build_notebooks.py    # regenerate notebooks after editing cells
```

## License

MIT
