# ChronoGrapher Evaluation Run Summary

Date: 2026-08-03

## Purpose

This run evaluates the thesis EKG evaluation framework on ChronoGrapher's public RDF/Turtle graph artifacts. The aim is to add a second real, publicly available RDF event-graph validation target beyond the OEKG event-layer run, while keeping the interpretation honest: these graphs are small ChronoGrapher experiment artifacts around the French Revolution, not a large operational EKG like OEKG.

## Disk Monitoring

The run was kept well within local storage limits.

| Step | Free space on C: |
|---|---:|
| Before download/evaluation | 104.68 GB |
| After TTL download and conversion | about 104.41 GB |
| After all three evaluations | 103.85 GB |

No disk-space stop condition was reached.

## Input Artifacts

Downloaded from `https://raw.githubusercontent.com/SonyCSLParis/graph_search_framework/main/kg-example/`.

| Artifact | Role | Raw Turtle size | Evaluation status |
|---|---|---:|---|
| `eventkg_ng.ttl` | EventKG-derived ground-truth graph | 101,735 bytes | Evaluated |
| `search_ng.ttl` | Search/retrieval output graph | 138,867 bytes | Evaluated |
| `generation_ng.ttl` | Generated graph output | 133,544 bytes | Evaluated |
| `frame_ng.ttl` | Textual frame graph | 11,637,021 bytes | Not evaluated as an EKG because it contains no `sem:Event` type assertions |

The Turtle files were validated with Apache Jena RIOT and converted to UTF-8 N-Triples in `nt_utf8/`. The first conversion attempt using PowerShell redirection produced UTF-16 N-Triples and was discarded; only the validated UTF-8 conversion was used for evaluation.

## Evaluation Outputs

| Dataset | JSON result | CSV result |
|---|---|---|
| `eventkg_ng` | `results/eventkg_ng/ekg_metrics_20260803_051549.json` | `results/eventkg_ng/ekg_metrics_20260803_051549.csv` |
| `search_ng` | `results/search_ng/ekg_metrics_20260803_051603.json` | `results/search_ng/ekg_metrics_20260803_051603.csv` |
| `generation_ng` | `results/generation_ng/ekg_metrics_20260803_051616.json` | `results/generation_ng/ekg_metrics_20260803_051616.csv` |

## Selected Results

| Metric | `eventkg_ng` | `search_ng` | `generation_ng` |
|---|---:|---:|---:|
| `sem:Event` instances | 235 | 380 | 374 |
| Triples | 1,682 | 3,291 | 3,165 |
| Projected nodes | 837 | 1,471 | 1,418 |
| Projected edges | 1,260 | 2,605 | 2,513 |
| Connected components | 1 | 1 | 1 |
| Giant component ratio | 100.00% | 100.00% | 100.00% |
| Average clustering | 0.0014 | 0.0099 | 0.0068 |
| Edge connectivity | 1 | 1 | 1 |
| Average degree | 3.0108 | 3.5418 | 3.5444 |
| Temporal coverage | 88.09% | 90.26% | 87.17% |
| Temporal literal validity | 100.00% | 100.00% | 100.00% |
| Temporal semantic consistency | 98.17% | 100.00% | 100.00% |
| Location coverage | 80.43% | 95.26% | 90.91% |
| Label coverage | 0.00% | 0.00% | 0.00% |
| Minimal profile conformance | 0.00% | 0.00% | 0.00% |
| Average properties per event | 7.16 | 8.66 | 8.46 |
| Sparse event percentage | 8.51% | 3.42% | 7.75% |
| Explicit external link rate | 0.00% | 0.00% | 0.00% |
| Unique predicates | 5 | 6 | 6 |
| Predicate Gini coefficient | 0.2468 | 0.4039 | 0.4071 |

## Interpretation

ChronoGrapher is a useful second real/public RDF event-graph validation target because the files contain explicit `sem:Event` resources with SEM temporal, actor, place, and in two files subevent relations. The evaluation completed without code changes and without large-graph mode.

The results should not be read as saying ChronoGrapher is a poor graph overall. They show a profile mismatch between ChronoGrapher's experiment artifacts and the thesis framework's EventKG-style profile assumptions. The graphs are strong on temporal validity, temporal coverage, location coverage, and connectivity. They score low on label coverage, minimal profile conformance, and explicit mapping coverage because the inspected files do not provide `rdfs:label` values or explicit `owl:sameAs` mappings for event resources. DBpedia IRIs are used directly as resource identifiers, but the current mapping metric counts explicit mapping predicates rather than treating every DBpedia subject IRI as an external mapping.

`eventkg_ng` contains four temporal semantic violations where the recorded end date precedes the start date. The search and generation outputs do not show those violations under the implemented check.

## Honest Limitations

- `frame_ng.ttl` was not evaluated because it has no explicit `sem:Event` type assertions.
- These are small ChronoGrapher experiment graphs, not a large independently maintained operational EKG.
- The framework's explicit external mapping metric undercounts DBpedia identity for this dataset because DBpedia IRIs are used as primary resource identifiers rather than through `owl:sameAs`.
- Type consistency is vacuous for these runs because the loaded files do not include usable domain/range declarations for the implemented type-consistency checks.
- Minimal profile conformance is 0% because the framework requires labels, dates, and places; ChronoGrapher provides dates and places but not labels in these files.
