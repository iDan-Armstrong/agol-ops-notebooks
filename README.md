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

1. `pip install -e .` into the notebook runtime (or attach `src/agolops` via the
   notebook workspace; for the QA notebook also install `qacore` from the companion repo).
2. Add each `.ipynb` as a Notebook item (ArcGIS Online → Notebooks → Add).
3. Fill in the `REPLACE_WITH_ITEM_ID` constants.
4. Schedule under the notebook's **Tasks** pane per the table above.

## Develop

```bash
pip install -e ".[dev]"
pytest                               # logic + notebook validity/sync/credential tests
python scripts/build_notebooks.py    # regenerate notebooks after editing cells
```

## License

MIT
