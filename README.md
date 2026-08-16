# EKG Evaluation Research Artefacts

This repository contains the implementation, datasets, accepted result evidence, and reproduction workflow for the thesis **A Comprehensive Evaluation Framework for Event-Centric Knowledge Graphs**.

The evaluator reports a multidimensional intrinsic profile for RDF-based event-centric knowledge graphs. It contains 28 distinct calculations exposed through 32 registered result fields across nine selected dimensions. Four fields are aliases used by more than one reporting module and are not counted as separate evidence.

## Reproduce the Results

From the repository root, run:

```powershell
.\reproduce.ps1 -Mode Quick
```

`Quick` is the recommended examiner workflow. It:

1. creates an isolated environment from locked dependencies;
2. runs all 24 automated tests;
3. regenerates the deterministic D1, D2, and D3 inputs;
4. evaluates all three datasets;
5. compares every input file and all 32 registered result fields with the accepted evidence; and
6. writes HTML, Markdown, and JSON reports under `reproduction-output/<timestamp>-quick/report/`.

Two other modes are available:

```powershell
.\reproduce.ps1 -Mode Verify
.\reproduce.ps1 -Mode Full
```

`Verify` checks the accepted source, input, result, test, comparator, table, and figure records without rerunning the evaluator. `Full` also reruns the three ChronoGrapher artefacts and the complete cleaned OEKG event layer. It may take several hours and needs about 20GB RAM and at least 80GB free working disk when OEKG must be prepared again.

See [REPRODUCE.md](REPRODUCE.md) for prerequisites, data retrieval, expected output, and interpretation.

## What a Passing Run Shows

A passing `Quick` report shows that the current implementation, regenerated D1-D3 input bytes, and all 32 registered outputs reproduce the accepted thesis evidence. A passing `Verify` report also confirms that the stored OEKG and ChronoGrapher results were generated with the same evaluator source snapshot as the current source.

These checks establish implementation and evidence reproducibility. They do not establish factual truth, causal correctness, or downstream-task suitability.

## Evaluation Dimensions

| Dimension | Registered fields |
|---|---:|
| Graph connectivity and structure | 6 |
| Redundancy and duplication | 3 |
| Temporal consistency | 6 |
| Minimal event-profile alignment | 4 |
| Completeness | 5 |
| Type consistency | 1 |
| Entity richness | 2 |
| External mapping coverage | 3 |
| Predicate usage | 2 |
| **Total** | **32** |

The definitive metric definitions are generated from `ekg-eval-cli/ekg_eval_cli/metric_registry.py`. Each accepted JSON result includes the formula, source or formalisation class, implementation path, empty-case rule, and interpretation limits for every registered field.

## Main Directories

- `ekg-eval-cli/` - Python command-line evaluator, locked dependencies, licence, and tests.
- `create_tiered_synthetic_eventkgs.py` - deterministic generator for the accepted D1-D3 RDF inputs used by `Quick`.
- `final-frozen-evidence-2026-08-07/` - accepted first-party result bundle and manifest.
- `tool-comparison/corrected-2026-08-07/comparator-summary.json` - frozen machine-readable summary of the external-tool runs, including input hashes, tool revisions, local patch hashes, native values, and failures.
- `chronographer-evaluation/` - prepared public ChronoGrapher RDF artefacts.
- `real-oekg-evaluation/` - OEKG cleaning, provenance, and large-graph run records.
- `docs/thesis/` - current thesis source mirror.

## Direct CLI Use

The one-command reproduction workflow is preferred when checking the thesis results. For a separate RDF EKG, see [`ekg-eval-cli/README.md`](ekg-eval-cli/README.md). The basic command is:

```powershell
ekg-eval-cli C:\path\to\ntriples-folder --verbose --output-dir C:\path\to\results
```

The default input profile expects direct `sem:Event` instances and SEM timestamps attached to event nodes. Graphs using another vocabulary or representation need an explicit profile mapping before affected metrics can be interpreted.

## Licence

The first-party evaluation software is licensed under the MIT licence in `ekg-eval-cli/LICENSE`. Third-party datasets and comparator tools retain their own licences.
