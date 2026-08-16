#!/usr/bin/env python3
"""Verify the frozen bundle and compare newly reproduced evaluator results."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any


EKG_ROOT = Path(__file__).resolve().parent
FROZEN_ROOT = EKG_ROOT / "final-frozen-evidence-2026-08-07"
MANIFEST_PATH = FROZEN_ROOT / "final-evidence-manifest.json"

RUN_LAYOUT = {
    "DOne": Path("dataset1"),
    "DTwo": Path("dataset2"),
    "DThree": Path("dataset3"),
    "ChronoReference": Path("chronographer/eventkg_ng"),
    "ChronoSearch": Path("chronographer/search_ng"),
    "ChronoGeneration": Path("chronographer/generation_ng"),
    "OEKG": Path("oekg"),
}

SELECTED_METRICS = [
    ("Direct events", "schema.total_events"),
    ("Connected components", "num_components"),
    ("Giant component", "giant_component_ratio"),
    ("Duplicate-candidate rate", "redundancy.duplication_rate"),
    ("Label uniqueness", "redundancy.label_quality.label_uniqueness_rate"),
    ("Fuzzy candidate pairs", "redundancy.fuzzy_duplicate_pairs"),
    ("Temporal coverage", "temporal.temporal_coverage.temporal_coverage_rate"),
    ("Interval consistency", "temporal.semantic_validation.consistency_rate"),
    ("Minimal profile", "schema.schema_conformance_rate"),
    ("Type alignment", "type_consistency.overall_type_consistency"),
    ("Distinct predicates/event", "entity_richness.avg_properties_per_event"),
    ("External mapping", "mapping_coverage.external_link_rate"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_result(folder: Path) -> Path:
    candidates = sorted(folder.glob("ekg_metrics_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No result JSON found in {folder}")
    return candidates[-1]


def resolve_manifest_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0].lower() == "ekg":
        path = Path(*parts[1:])
    return EKG_ROOT / path


def get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        current = current[part]
    return current


def values_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def display(value: Any, path: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        rendered = f"{value:.4f}".rstrip("0").rstrip(".")
    else:
        rendered = f"{value:,}" if isinstance(value, int) else str(value)
    if any(token in path for token in ("rate", "consistency", "conformance")):
        return f"{rendered}%"
    if path == "giant_component_ratio":
        return f"{float(value) * 100:.4f}%"
    return rendered


def verify_file(path: Path, expected_hash: str, checks: list[dict[str, Any]], label: str) -> None:
    exists = path.is_file()
    actual = sha256(path) if exists else None
    checks.append(
        {
            "check": label,
            "passed": exists and actual == expected_hash,
            "expected": expected_hash,
            "actual": actual,
            "path": str(path),
        }
    )


def verify_frozen_bundle() -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    manifest = load_json(MANIFEST_PATH)
    checks: list[dict[str, Any]] = []
    frozen_results: dict[str, dict[str, Any]] = {}

    for name, record in manifest["runs"].items():
        path = resolve_manifest_path(record["result_path"])
        verify_file(path, record["result_sha256"], checks, f"Frozen result: {name}")
        if path.is_file():
            result = load_json(path)
            frozen_results[name] = result
            core_count = sum(
                1 for row in result["metric_audit"].values() if row["core_metric"]
            )
            checks.append(
                {
                    "check": f"Core metric inventory: {name}",
                    "passed": core_count == 32,
                    "expected": 32,
                    "actual": core_count,
                    "path": str(path),
                }
            )

    for key in ("comparator_summary", "test_suite", "radar"):
        record = manifest[key]
        verify_file(
            resolve_manifest_path(record["path"]),
            record["sha256"],
            checks,
            f"Frozen artefact: {key}",
        )
    for key, record in manifest["generated_artifacts"].items():
        verify_file(
            resolve_manifest_path(record["path"]),
            record["sha256"],
            checks,
            f"Generated artefact: {key}",
        )

    if frozen_results:
        reference = frozen_results["DOne"]
        snapshot = reference["run_provenance"]["source_snapshot"]
        source_ok = True
        mismatches: list[str] = []
        for row in snapshot["files"]:
            path = EKG_ROOT / "ekg-eval-cli" / row["path"]
            if not path.is_file() or sha256(path) != row["sha256"]:
                source_ok = False
                mismatches.append(row["path"])
        checks.append(
            {
                "check": "Current evaluator files match frozen source snapshot",
                "passed": source_ok,
                "expected": snapshot["aggregate_sha256"],
                "actual": snapshot["aggregate_sha256"] if source_ok else mismatches,
                "path": str(EKG_ROOT / "ekg-eval-cli"),
            }
        )

    return manifest, frozen_results, checks


def compare_reproduced(
    results_root: Path,
    frozen_results: dict[str, dict[str, Any]],
    requested_runs: list[str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    reproduced: dict[str, dict[str, Any]] = {}
    for name in requested_runs:
        path = latest_result(results_root / RUN_LAYOUT[name])
        actual = load_json(path)
        expected = frozen_results[name]
        reproduced[name] = actual

        actual_files = {
            Path(row["path"]).name: row["sha256"]
            for row in actual["run_provenance"]["inputs"]["files"]
        }
        expected_files = {
            Path(row["path"]).name: row["sha256"]
            for row in expected["run_provenance"]["inputs"]["files"]
        }
        checks.append(
            {
                "check": f"Reproduced input bytes: {name}",
                "passed": actual_files == expected_files,
                "expected": f"{len(expected_files)} named files and SHA-256 values",
                "actual": (
                    f"{len(actual_files)} named files and SHA-256 values"
                    if actual_files == expected_files
                    else {
                        "missing_or_changed": sorted(
                            name
                            for name, digest in expected_files.items()
                            if actual_files.get(name) != digest
                        ),
                        "unexpected": sorted(set(actual_files) - set(expected_files)),
                    }
                ),
                "path": str(path),
            }
        )

        actual_source = actual["run_provenance"]["source_snapshot"]["aggregate_sha256"]
        expected_source = expected["run_provenance"]["source_snapshot"]["aggregate_sha256"]
        checks.append(
            {
                "check": f"Reproduced evaluator hash: {name}",
                "passed": actual_source == expected_source,
                "expected": expected_source,
                "actual": actual_source,
                "path": str(path),
            }
        )

        paths = sorted(
            row["path"]
            for row in expected["metric_audit"].values()
            if row["core_metric"]
        )
        mismatches = []
        for metric_path in paths:
            expected_value = get(expected, metric_path)
            actual_value = get(actual, metric_path)
            if not values_equal(actual_value, expected_value):
                mismatches.append(
                    {
                        "path": metric_path,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )
        checks.append(
            {
                "check": f"All 32 reproduced core outputs: {name}",
                "passed": not mismatches,
                "expected": "32/32 match",
                "actual": "32/32 match" if not mismatches else mismatches,
                "path": str(path),
            }
        )
    return checks, reproduced


def markdown_report(
    checks: list[dict[str, Any]],
    reproduced: dict[str, dict[str, Any]],
    test_log: Path | None,
) -> str:
    passed = sum(1 for row in checks if row["passed"])
    status = "PASS" if passed == len(checks) else "FAIL"
    lines = [
        "# EKG Evaluation Reproduction Report",
        "",
        f"**Overall status:** {status}",
        "",
        f"**Checks passed:** {passed}/{len(checks)}",
        "",
    ]
    if test_log and test_log.is_file():
        raw = test_log.read_bytes()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            test_text = raw.decode("utf-16").strip()
        else:
            test_text = raw.decode("utf-8-sig", errors="replace").strip()
        lines.extend([f"**Automated tests:** `{test_text.splitlines()[-1]}`", ""])

    lines.extend(["## Integrity Checks", "", "| Check | Status |", "|---|---|"])
    for row in checks:
        lines.append(f"| {row['check']} | {'PASS' if row['passed'] else 'FAIL'} |")

    if reproduced:
        lines.extend(["", "## Reproduced Results", ""])
        names = list(reproduced)
        lines.append("| Metric | " + " | ".join(names) + " |")
        lines.append("|---|" + "---:|" * len(names))
        for label, path in SELECTED_METRICS:
            values = [display(get(reproduced[name], path), path) for name in names]
            lines.append(f"| {label} | " + " | ".join(values) + " |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A passing report establishes that the executable implementation, input bytes, and 32 declared core outputs reproduce the frozen evidence. It does not establish factual truth, causal correctness, or downstream-task suitability.",
            "",
        ]
    )
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    rows = []
    in_table = False
    table_row = 0
    for line in markdown.splitlines():
        if line.startswith("# "):
            rows.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_table:
                rows.append("</tbody></table>")
                in_table = False
            rows.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("|"):
            if set(line.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not in_table:
                rows.append("<table><tbody>")
                in_table = True
                table_row = 0
            tag = "th" if table_row == 0 else "td"
            rows.append("<tr>" + "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in cells) + "</tr>")
            table_row += 1
        elif line:
            if in_table:
                rows.append("</tbody></table>")
                in_table = False
            text = html.escape(line).replace("**", "")
            rows.append(f"<p>{text}</p>")
    if in_table:
        rows.append("</tbody></table>")
    body = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>EKG reproduction report</title>
<style>body{{font:16px/1.45 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#202124}}table{{border-collapse:collapse;width:100%;margin:16px 0 28px}}th,td{{border:1px solid #b9bec5;padding:8px;text-align:left}}th{{background:#eef1f4}}h1,h2{{color:#17324d}}code{{background:#eef1f4;padding:2px 4px}}</style></head><body>{body}</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--include-chrono", action="store_true")
    parser.add_argument("--include-oekg", action="store_true")
    parser.add_argument("--test-log", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest, frozen_results, checks = verify_frozen_bundle()
    reproduced: dict[str, dict[str, Any]] = {}
    if args.results_root:
        names = ["DOne", "DTwo", "DThree"]
        if args.include_chrono:
            names.extend(["ChronoReference", "ChronoSearch", "ChronoGeneration"])
        if args.include_oekg:
            names.append("OEKG")
        comparison_checks, reproduced = compare_reproduced(
            args.results_root.resolve(), frozen_results, names
        )
        checks.extend(comparison_checks)

    report = markdown_report(checks, reproduced, args.test_log)
    (args.output_dir / "reproduction-report.md").write_text(report, encoding="utf-8")
    (args.output_dir / "reproduction-report.html").write_text(
        html_report(report), encoding="utf-8"
    )
    verification = {
        "status": "pass" if all(row["passed"] for row in checks) else "fail",
        "manifest": str(MANIFEST_PATH),
        "evaluator_source_snapshot_sha256": manifest[
            "evaluator_source_snapshot_sha256"
        ],
        "checks": checks,
    }
    (args.output_dir / "verification.json").write_text(
        json.dumps(verification, indent=2), encoding="utf-8"
    )
    print(args.output_dir / "reproduction-report.md")
    print(args.output_dir / "reproduction-report.html")
    print(f"Overall status: {verification['status'].upper()}")
    return 0 if verification["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
