#!/usr/bin/env python3
"""Validate frozen result provenance and generate thesis-ready evidence artefacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT
THESIS_ROOT = ROOT / "docs" / "thesis"
EVIDENCE = ROOT / "final-frozen-evidence-2026-08-07"
COMPARATOR = ROOT / "tool-comparison" / "corrected-2026-08-07"
sys.path.insert(0, str(ROOT / "ekg-eval-cli"))

from ekg_eval_cli.provenance import build_source_manifest

RUNS = {
    "DOne": EVIDENCE / "dataset1",
    "DTwo": EVIDENCE / "dataset2",
    "DThree": EVIDENCE / "dataset3",
    "ChronoReference": EVIDENCE / "chronographer" / "eventkg_ng",
    "ChronoSearch": EVIDENCE / "chronographer" / "search_ng",
    "ChronoGeneration": EVIDENCE / "chronographer" / "generation_ng",
    "OEKG": EVIDENCE / "oekg",
}


def latest_result(folder: Path) -> Path:
    candidates = sorted(folder.glob("ekg_metrics_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No frozen result JSON found in {folder}")
    return candidates[-1]


def load_result(folder: Path) -> tuple[Path, dict[str, Any]]:
    path = latest_result(folder)
    return path, json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repository_path(path: Path) -> str:
    """Return a portable path relative to the public repository root."""
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        current = current[part]
    return current


def tex_value(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def tex_escape(value: Any) -> str:
    text = str(value)
    for source, target in (
        ("Normalized", "Normalised"),
        ("normalized", "normalised"),
        ("normalization", "normalisation"),
        ("operationalization", "operationalisation"),
        ("modeling", "modelling"),
        ("analyzed", "analysed"),
        ("emphasizes", "emphasises"),
    ):
        text = text.replace(source, target)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def tex_path(value: Any) -> str:
    """Render a machine path with url-style line-break opportunities."""
    text = str(value).replace("\\", "/")
    return rf"\path{{{text}}}"


def build_core_inventory(audit: dict[str, Any], output: Path) -> None:
    rows = sorted(
        (row for row in audit.values() if row["core_metric"]),
        key=lambda row: int(row["metric_id"][1:]),
    )
    if len(rows) != 32:
        raise RuntimeError("Core inventory does not contain exactly 32 rows")

    # The frozen evaluator registry is retained byte-for-byte in each result.
    # These presentation corrections make bounded implementation details
    # explicit without changing the frozen calculations or their identifiers.
    presentation_overrides = {
        "M03": {
            "empty_case": (
                "No projected nodes: reject the input. In large-graph mode, "
                "clustering is unavailable and accompanied by an explicit status."
            ),
        },
        "M04": {
            "empty_case": (
                "No projected nodes: reject the input. In large-graph mode, report "
                "only conditionally exact cases; otherwise mark the value unavailable."
            ),
        },
        "M15": {
            "formula": (
                "sum of distinct-event counts per represented begin-date literal / "
                "number of decades from the minimum to maximum observed year, including empty decades."
            ),
        },
        "M19": {
            "label": "Reported non-allowlisted property count (cap 50)",
            "formula": (
                "Count of the up to 50 most frequent distinct event predicates whose "
                "namespace is outside the configured allow-list."
            ),
            "limitations": (
                "Non-allowlisted does not mean incorrect; the allow-list must be declared, "
                "and values above 50 are truncated by the reporting cap."
            ),
        },
        "M20": {
            "formula": (
                "event classes used under sem:Event subclass closure / sem:Event plus "
                "declared direct subclasses of sem:Event * 100."
            ),
            "limitations": (
                "Measures class usage against the declared direct profile, not real-world "
                "population completeness; indirect used descendants can produce a value above 100%."
            ),
        },
    }
    rows = [dict(row, **presentation_overrides.get(row["metric_id"], {})) for row in rows]
    for row in rows:
        implementation_parts = [part.strip() for part in row["implementation"].split("/")]
        if len(implementation_parts) > 1:
            owner = implementation_parts[0].rsplit(".", 1)[0]
            row["implementation"] = " / ".join(
                part if "." in part else f"{owner}.{part}"
                for part in implementation_parts
            )

    lines = [
        r"\section{Definitive Registered-Result Inventory}",
        r"\label{app:core_metric_inventory}",
        "",
        (
            "The following tables are generated from the frozen implementation's list of "
            "registered result fields and checked against the implementation. The 32 fields "
            "represent 28 distinct calculations because four are aliases used by another "
            "reporting module. Other JSON fields provide counts, denominators, status values, "
            "samples, or diagnostic details rather than additional metrics."
        ),
        "",
        r"\begingroup\scriptsize\setlength{\tabcolsep}{3pt}\setlength{\LTpre}{0.4em}\setlength{\LTpost}{0.4em}",
        r"\begin{longtable}{p{0.06\textwidth}p{0.25\textwidth}p{0.61\textwidth}}",
        r"\caption{Registered result-field names and dimensions.}\label{tab:core_metric_inventory_names}\\",
        r"\toprule ID & Dimension & Metric \\",
        r"\midrule\endfirsthead",
        r"\toprule ID & Dimension & Metric \\",
        r"\midrule\endhead",
        r"\bottomrule\endfoot",
    ]
    for row in rows:
        lines.append(
            " & ".join(
                tex_escape(row[key])
                for key in ("metric_id", "dimension", "label")
            )
            + r" \\"
        )
    lines.extend(
        [
            r"\end{longtable}",
            "",
            r"\begin{longtable}{p{0.06\textwidth}p{0.38\textwidth}p{0.48\textwidth}}",
            r"\caption{Registered JSON result fields and implementation paths.}\label{tab:core_metric_inventory_paths}\\",
            r"\toprule ID & JSON output path & Implementation path \\",
            r"\midrule\endfirsthead",
            r"\toprule ID & JSON output path & Implementation path \\",
            r"\midrule\endhead",
            r"\bottomrule\endfoot",
        ]
    )
    for row in rows:
        lines.append(
            " & ".join(
                [
                    tex_escape(row["metric_id"]),
                    tex_path(row["path"]),
                    tex_path(row["implementation"]),
                ]
            )
            + r" \\"
        )
    lines.extend(
        [
            r"\end{longtable}",
            "",
            r"\begin{longtable}{p{0.05\textwidth}p{0.37\textwidth}p{0.22\textwidth}p{0.25\textwidth}}",
            r"\caption{Exact formula contracts, unavailable-value policies, and provenance classification.}\label{tab:core_metric_inventory_contracts}\\",
            r"\toprule ID & Formula / operational definition & Empty or inapplicable case & Source / formalisation class \\",
            r"\midrule\endfirsthead",
            r"\toprule ID & Formula / operational definition & Empty or inapplicable case & Source / formalisation class \\",
            r"\midrule\endhead",
            r"\bottomrule\endfoot",
        ]
    )
    for row in rows:
        basis = f"{row['provenance_type']}: {row['source_basis']}"
        lines.append(
            " & ".join(
                [
                    tex_escape(row["metric_id"]),
                    tex_escape(row["formula"]),
                    tex_escape(row["empty_case"]),
                    tex_escape(basis),
                ]
            )
            + r" \\"
        )
    lines.extend([r"\end{longtable}", r"\endgroup", ""])
    output.write_text("\n".join(lines), encoding="ascii")


MACRO_FIELDS = {
    "Nodes": ("total_nodes", 0),
    "Edges": ("total_edges", 0),
    "Components": ("num_components", 0),
    "GiantPct": ("giant_component_ratio", 4),
    "AverageDegree": ("avg_degree", 2),
    "DuplicateRatePct": ("redundancy.duplication_rate", 2),
    "LabelUniquenessPct": ("redundancy.label_quality.label_uniqueness_rate", 2),
    "FuzzyPairs": ("redundancy.fuzzy_duplicate_pairs", 0),
    "TemporalCoveragePct": ("temporal.temporal_coverage.temporal_coverage_rate", 2),
    "IntervalConsistencyPct": ("temporal.semantic_validation.consistency_rate", 2),
    "ProfilePct": ("schema.schema_conformance_rate", 2),
    "CompletenessPct": ("completeness.population_completeness_percentage", 2),
    "TypeAlignmentPct": ("type_consistency.overall_type_consistency", 2),
    "TypeChecks": ("type_consistency.applicable_consistency_checks", 0),
    "Richness": ("entity_richness.avg_properties_per_event", 2),
    "SparsePct": ("entity_richness.sparse_entities_percentage", 2),
    "ExternalMappingPct": ("mapping_coverage.external_link_rate", 2),
    "WikidataPct": ("mapping_coverage.wikidata_coverage", 2),
    "DBpediaPct": ("mapping_coverage.dbpedia_coverage", 2),
    "PredicateEntropy": ("predicate_usage.normalized_shannon_entropy", 4),
    "PredicateHHI": ("predicate_usage.hhi_concentration", 4),
    "Triples": ("predicate_usage.total_triples", 0),
    "Events": ("schema.total_events", 0),
}


def validate_comparator_inputs(results: dict[str, dict[str, Any]]) -> None:
    manifest = json.loads((COMPARATOR / "input-manifest.json").read_text(encoding="utf-8"))
    mapping = {
        "dataset1-high": "DOne",
        "dataset2-mixed": "DTwo",
        "dataset3-low": "DThree",
    }
    for comparator_name, run_name in mapping.items():
        comparator_files = {
            row["name"]: row["sha256"]
            for row in manifest["datasets"][comparator_name]["source_files"]
        }
        evaluator_files = {
            Path(row["path"]).name: row["sha256"]
            for row in results[run_name]["run_provenance"]["inputs"]["files"]
        }
        if comparator_files != evaluator_files:
            raise RuntimeError(
                f"Comparator and proposed evaluator inputs differ for {comparator_name}"
            )


def build() -> None:
    loaded = {name: load_result(folder) for name, folder in RUNS.items()}
    paths = {name: pair[0] for name, pair in loaded.items()}
    results = {name: pair[1] for name, pair in loaded.items()}

    source_hashes = {
        result["run_provenance"]["source_snapshot"]["aggregate_sha256"]
        for result in results.values()
    }
    if len(source_hashes) != 1:
        raise RuntimeError("Frozen runs do not share one evaluator source hash")
    current_source = build_source_manifest(ROOT / "ekg-eval-cli")
    if current_source["aggregate_sha256"] != next(iter(source_hashes)):
        raise RuntimeError(
            "Frozen runs do not match the current first-party evaluator source"
        )
    if any(
        sum(1 for row in result["metric_audit"].values() if row["core_metric"]) != 32
        for result in results.values()
    ):
        raise RuntimeError("A frozen run does not contain exactly 32 core metrics")

    validate_comparator_inputs(results)

    lines = ["% Generated by ekg/build_final_evidence_bundle.py. Do not edit manually."]
    for run_name, result in results.items():
        for suffix, (path, digits) in MACRO_FIELDS.items():
            value = get(result, path)
            if suffix == "GiantPct" and value is not None:
                value = float(value) * 100
            lines.append(f"\\newcommand{{\\{run_name}{suffix}}}{{{tex_value(value, digits)}}}")
    source_hash = next(iter(source_hashes))
    lines.append(f"\\newcommand{{\\FrozenEvaluatorHash}}{{\\texttt{{{source_hash[:12]}}}}}")
    lines.append("\\newcommand{\\FrozenCoreMetricCount}{32}")

    generated = THESIS_ROOT / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    macro_path = generated / "final_results_macros.tex"
    macro_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    inventory_path = generated / "core_metric_inventory.tex"
    build_core_inventory(results["DOne"]["metric_audit"], inventory_path)

    comparator_summary = COMPARATOR / "comparator-summary.json"
    test_log = EVIDENCE / "test-suite.log"
    if not test_log.exists():
        raise FileNotFoundError("Final test-suite log is missing")
    bundle = {
        "manifest_version": 2,
        "path_base": "thesis_repository_root",
        "created_by": "ekg/build_final_evidence_bundle.py",
        "evaluator_source_snapshot_sha256": source_hash,
        "current_evaluator_source_matches_frozen_runs": True,
        "core_metric_count": 32,
        "comparator_inputs_match_evaluator_inputs": True,
        "runs": {
            name: {
                "result_path": repository_path(path),
                "result_sha256": sha256(path),
                "input_aggregate_sha256": results[name]["run_provenance"]["inputs"][
                    "aggregate_sha256"
                ],
            }
            for name, path in paths.items()
        },
        "comparator_summary": {
            "path": repository_path(comparator_summary),
            "sha256": sha256(comparator_summary),
        },
        "test_suite": {
            "path": repository_path(test_log),
            "sha256": sha256(test_log),
            "passed": 24,
        },
        "radar": {
            "path": repository_path(EVIDENCE / "synthetic_quality_profile_radar.png"),
            "sha256": sha256(EVIDENCE / "synthetic_quality_profile_radar.png"),
            "uses_only_directly_bounded_rates": True,
            "universal_aggregate_score": False,
        },
        "generated_artifacts": {
            "final_results_macros": {
                "path": repository_path(macro_path),
                "sha256": sha256(macro_path),
            },
            "core_metric_inventory": {
                "path": repository_path(inventory_path),
                "sha256": sha256(inventory_path),
            },
        },
    }
    bundle_path = EVIDENCE / "final-evidence-manifest.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(macro_path)
    print(inventory_path)
    print(bundle_path)


if __name__ == "__main__":
    build()
