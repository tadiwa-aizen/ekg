# Accepted Evaluation Results

This page is a readable index of the machine-readable evidence in this repository. The values below are not recomputed for display: they are copied from the frozen JSON and comparator summary verified by `reproduce.ps1`.

## Controlled Datasets

| Metric | D1 high | D2 mixed | D3 low |
|---|---:|---:|---:|
| Nodes | 1,620 | 881 | 305 |
| Edges | 2,555 | 1,258 | 297 |
| Connected components | 25 | 14 | 57 |
| Giant component | 97.04% | 96.37% | 75.08% |
| Label uniqueness | 100.00% | 69.89% | 33.33% |
| Temporal coverage | 100.00% | 70.83% | 42.50% |
| Interval consistency | 100.00% | 81.63% | 52.17% |
| Minimal profile completeness | 93.00% | 29.17% | 0.83% |
| Type alignment | 100.00% | 87.78% | 70.00% |
| Average event richness | 7.46 | 4.88 | 1.87 |
| External mapping | 100.00% | 65.00% | 9.17% |
| Sparse events | 0.00% | 6.67% | 64.17% |

The complete accepted outputs, metric formulas, implementation paths, empty-case rules, and provenance classifications are in:

- `final-frozen-evidence-2026-08-07/dataset1/`
- `final-frozen-evidence-2026-08-07/dataset2/`
- `final-frozen-evidence-2026-08-07/dataset3/`

The current generator deliberately changes label, date, place, description, relation, external-link, temporal-granularity, interval-validity, and type-alignment controls. Therefore, the controlled runs test implementation sensitivity to known changes; they do not establish factual correctness or universal construct validity.

## General KG-Quality Tools

The four tools used different native scales and denominators. Their values must be interpreted within each tool and are not combined into a universal score.

| Native output | D1 high | D2 mixed | D3 low |
|---|---:|---:|---:|
| RDFUnit successful definitions | 192 | 192 | 192 |
| RDFUnit violation results | 2,047 | 1,260 | 678 |
| KGHeartbeat score | 0.301 | 0.304 | 0.307 |
| Luzzu extensional conciseness | 0.992 | 0.990 | 0.865 |
| Luzzu human-readable labelling | 0.229 | 0.286 | 0.295 |
| SANSA extensional conciseness | 0.266 | 0.277 | 0.176 |

RDFUnit reports the same four failed test definitions in every condition, while its raw violation counts differ with graph size and content. Two attempted SANSA metrics failed in every run; those failures are retained in the evidence. Exact input hashes, tool revisions, local patch hashes, native values, and failures are in `tool-comparison/corrected-2026-08-07/comparator-summary.json`.

## Published EKG Data

| Graph | Direct events | Triples | Giant component | Temporal coverage | Minimal profile | Richness |
|---|---:|---:|---:|---:|---:|---:|
| OEKG event layer | 954,554 | 93,474,126 | 99.43% | 81.91% | 64.19% | 8.78 |
| ChronoGrapher reference | 235 | 1,682 | 83.85% | 88.09% | 0.00% | 3.35 |
| ChronoGrapher search | 380 | 3,291 | 92.93% | 90.26% | 0.00% | 3.83 |
| ChronoGrapher generation | 374 | 3,165 | 91.53% | 87.17% | 0.00% | 3.68 |

OEKG evaluation covers the complete cleaned event layer, not every source layer. The cleaning repairs invalid backslash escapes needed for RDF parsing and records provenance; it does not add or remove semantic facts. ChronoGrapher uses a different representation, so zero minimal-profile and explicit-mapping values describe profile mismatch rather than factual inaccuracy. Published-graph runs demonstrate execution and descriptive applicability, not ground-truth validation.

## Verification

Run:

```powershell
.\reproduce.ps1 -Mode Quick
```

A passing run executes 24 tests, regenerates the controlled inputs, evaluates all 32 registered fields, and checks the resulting bytes, source hash, and values against the frozen evidence. The accepted evidence manifest is `final-frozen-evidence-2026-08-07/final-evidence-manifest.json`.
