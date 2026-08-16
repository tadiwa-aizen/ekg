# OEKG Full Evaluation Run Summary

Date: 2026-08-02

## Purpose

This run validates the EKG evaluation framework on a real published RDF Event-Centric Knowledge Graph rather than only on the controlled synthetic datasets. The input is the cleaned OEKG/EventKG-style event-layer extraction.

## Input

- Clean input folder: `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\oekg-event-layer-clean`
- TDB database: `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\oekg-event-layer-clean\databases\eventkg-db`
- Jena: `C:\Users\riski\Desktop\Projects\masters\ekg\tools\apache-jena-5.6.0-bin\apache-jena-5.6.0`
- Fuseki: `C:\Users\riski\Desktop\Projects\masters\ekg\apache-jena-fuseki-5.6.0`

## Command Shape

The successful run used the CLI in large-graph mode:

```powershell
python -m ekg_eval_cli.cli `
  "C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\oekg-event-layer-clean" `
  --verbose `
  --large-graph-mode `
  --output-dir "C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\results-oekg-event-layer-full-large-4" `
  --large-graph-work-dir "C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\large-graph-work-oekg" `
  --duckdb-memory-limit 8GB `
  --duckdb-temp-dir "C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\large-graph-work-oekg\duckdb-temp" `
  --jena-home "C:\Users\riski\Desktop\Projects\masters\ekg\tools\apache-jena-5.6.0-bin\apache-jena-5.6.0" `
  --fuseki-home "C:\Users\riski\Desktop\Projects\masters\ekg\apache-jena-fuseki-5.6.0"
```

## Output

- JSON: `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\results-oekg-event-layer-full-large-4\ekg_metrics_20260802_235038.json`
- CSV: `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\results-oekg-event-layer-full-large-4\ekg_metrics_20260802_235038.csv`
- Metric audit: `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\results-oekg-event-layer-full-large-4\metric_audit.md`
- Run log: `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\results-oekg-event-layer-full-large-4\run_stdout.log`

## Main Results

| Area | Result |
|---|---:|
| Projected nodes | 25,126,655 |
| Unique undirected projected edges | 62,027,829 |
| Raw projected IRI-to-IRI rows | 64,140,522 |
| Connected components | 2 |
| Giant component size | 25,126,652 |
| Giant component ratio | 0.9999998806 |
| Average degree | 4.9372 |
| Density | 0.0000001965 |
| Edge connectivity | 0, conditionally exact because the projected graph is disconnected |
| Average clustering | Not computed in large-graph mode |
| Total direct `sem:Event` records | 954,554 |
| Temporal coverage | 81.84% |
| Minimal profile/schema conformance | 64.15% |
| External link rate | 100.00% |
| DBpedia mapping coverage | 53.01% |
| Wikidata mapping coverage | 100.00% |
| Predicate count | 27 |
| Total triples counted for predicate usage | 93,474,126 |

## Implementation Changes Made

- Added `--large-graph-mode`.
- Added DuckDB-backed edge projection, canonicalisation, deduplication, and dense ID assignment.
- Added streaming union-find connected components for large projected graphs.
- Added `--graph-structure-only` so structural validation can be run independently.
- Changed Fuseki startup logging so stdout/stderr are written to files instead of unread pipes.
- Changed Windows Fuseki shutdown to kill the process tree, avoiding leftover Java processes.
- Added exact file-scan fallbacks for temporal coverage, schema conformance, and completeness where endpoint-wide row-returning/count queries were too slow or fragile at OEKG scale.

## Honest Limitations

- Average clustering is not computed for the full OEKG run. It is marked as `not_computed_large_graph_mode` and stored as `-1.0` for compatibility with the existing output format.
- Edge connectivity is only conditionally exact. Because the projected graph has 2 connected components, global edge connectivity is exactly 0. The tool does not attempt a full min-cut computation at this scale.
- Several non-structural metrics still use Fuseki/SPARQL. They completed in this run, but large endpoint queries remain more fragile than streaming file scans.
- The file-scan paths preserve the implemented metric definitions, including existing quirks such as the declared-event-class counting behaviour.

## Disk State

After the run, C: had about 90.48GB free. The reusable large-graph work directory contains the 6.09GB projected edge TSV and the DuckDB database, so future large-graph reruns can avoid rebuilding those parts.
