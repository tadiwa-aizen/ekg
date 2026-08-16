# Reproducing the EKG Evaluation

The repository provides three non-destructive reproduction modes. Every mode writes to a new timestamped folder under `reproduction-output/`; none overwrites the frozen thesis evidence.

## Prerequisites

- Windows PowerShell 5.1 or PowerShell 7
- Python 3.12 for the exact frozen environment
- Java 17 or later on `PATH`
- Internet access on first setup to install locked Python packages and, if absent, download Apache Jena/Fuseki

From the `ekg` folder, run one of the following commands.

## Quick Reproduction

```powershell
.\reproduce.ps1 -Mode Quick
```

Quick mode:

1. creates an isolated `.venv-reproduction` environment;
2. installs `requirements-lock.txt` and the pinned reproduction-only test dependency;
3. locates or downloads Apache Jena 5.6.0 and Fuseki 5.6.0 and verifies their SHA-512 hashes;
4. runs all 24 automated tests;
5. generates fresh deterministic D1, D2, and D3 inputs in the output folder;
6. evaluates the three graphs;
7. compares every named input file and SHA-256, the evaluator source hash, and all 32 core outputs with the frozen evidence;
8. writes `reproduction-report.html`, `reproduction-report.md`, and `verification.json`.

This is the recommended examiner and reviewer path.

## Evidence Verification Only

```powershell
.\reproduce.ps1 -Mode Verify
```

Verify mode does not start Fuseki or recompute metrics. It verifies the hashes of all seven frozen result files, the external-comparator summary, test log, radar chart, generated LaTeX evidence, the 32-core inventory in every run, and the current evaluator source files.

## Full First-Party Reproduction

```powershell
.\reproduce.ps1 -Mode Full
```

Full mode runs Quick mode and additionally evaluates the three eligible ChronoGrapher RDF artefacts and the complete cleaned OEKG event layer. It may take several hours.

If the prepared OEKG input is absent, the runner downloads OEKG V2.0 `event_kg.tar.gz` from Zenodo record 4503163 and requires SHA-256:

```text
392d6eeb69d074130166fb626d4db7279c2b16b45be50213480de1864ce4aa4a
```

The runner then extracts the archive and applies only the documented invalid-literal-escape repairs. An existing archive can be supplied with:

```powershell
.\reproduce.ps1 -Mode Full -OekgArchive D:\data\event_kg.tar.gz
```

Recommended resources for preparation and a fresh complete OEKG run are approximately 20GB RAM and at least 80GB free working disk. The final OEKG run uses an 8GB DuckDB memory limit and disk-backed structural computation.

## Outputs

A successful quick report ends with:

```text
Overall status: PASS
24 passed
All 32 reproduced core outputs: DOne PASS
All 32 reproduced core outputs: DTwo PASS
All 32 reproduced core outputs: DThree PASS
```

Passing reproduction establishes that the implementation, input bytes, and declared metric outputs reproduce the frozen evidence. It does not establish factual truth, causal correctness, or downstream-task suitability.

## External Comparator Evidence

RDFUnit, KGHeartbeat, Luzzu, and SANSA used incompatible runtimes and documented local compatibility adaptations. The public `comparator-summary.json` records the common input hashes, pinned revisions, local patch hashes, native values, and failures. Verify mode checks that frozen summary's hash.

The upstream comparator repositories and machine-specific raw logs are not bundled in this repository, and the one-command workflow does not rerun those four third-party tools. Repeating those runs requires obtaining the pinned upstream revisions and applying the adaptations described in Appendix A of the thesis. This boundary is stated explicitly rather than hiding different environments behind a container or converting incompatible outputs to a common score.
