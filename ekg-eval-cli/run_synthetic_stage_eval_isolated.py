"""Run synthetic EKG evaluations with one fresh Fuseki process per stage."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ekg_eval_cli.analyzer import GraphAnalyzer
from ekg_eval_cli.completeness import CompletenessAnalyzer
from ekg_eval_cli.config import EvaluationParameters
from ekg_eval_cli.database import DatabaseManager
from ekg_eval_cli.entity_richness import EntityRichnessAnalyzer
from ekg_eval_cli.mapping_coverage import MappingCoverageAnalyzer
from ekg_eval_cli.metric_registry import metric_audit
from ekg_eval_cli.provenance import build_run_provenance
from ekg_eval_cli.output import OutputHandler
from ekg_eval_cli.predicate_usage import PredicateUsageAnalyzer
from ekg_eval_cli.redundancy import RedundancyAnalyzer
from ekg_eval_cli.schema_analyzer import SchemaAnalyzer
from ekg_eval_cli.sparql import SPARQLExecutor
from ekg_eval_cli.temporal import TemporalValidator
from ekg_eval_cli.type_consistency import TypeConsistencyAnalyzer

DATASETS = {
    "dataset1": ROOT / "synthetic-event-kg",
    "dataset2": ROOT / "synthetic-event-kg-2",
    "dataset3": ROOT / "synthetic-event-kg-3",
}


def save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def wait_ready() -> None:
    for _ in range(30):
        try:
            if requests.get("http://localhost:3030/$/ping", timeout=1).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Fuseki did not become ready")


def with_fuseki(fuseki_home: Path, db_path: Path, fn: Callable[[str], Any]) -> Any:
    process = subprocess.Popen(
        [
            "java",
            "-Xmx4G",
            "-cp",
            "fuseki-server.jar",
            "org.apache.jena.fuseki.main.cmds.FusekiServerCmd",
            "--loc",
            str(db_path),
            "/eventkg",
        ],
        cwd=str(fuseki_home),
        # Fuseki writes enough logging to fill an unconsumed PIPE and block the
        # staged runner. The stage result is captured separately in JSON.
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_ready()
        return fn("http://localhost:3030/eventkg")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_stage(
    stage: str,
    results: dict[str, Any],
    checkpoint: Path,
    fuseki_home: Path,
    db_path: Path,
    fn: Callable[[str], Any],
) -> None:
    print(f"[stage] {stage}", flush=True)
    start = time.time()
    try:
        results[stage] = with_fuseki(fuseki_home, db_path, fn)
        results["_stage_status"][stage] = {
            "status": "ok",
            "seconds": round(time.time() - start, 2),
        }
    except Exception as exc:
        results[stage] = {"error": str(exc), "error_type": type(exc).__name__}
        results["_stage_status"][stage] = {
            "status": "error",
            "seconds": round(time.time() - start, 2),
            "error": str(exc),
        }
        print(f"[stage-error] {stage}: {exc}", flush=True)
    save(checkpoint, results)


def run_local_stage(
    stage: str,
    results: dict[str, Any],
    checkpoint: Path,
    fn: Callable[[], Any],
) -> None:
    print(f"[stage] {stage}", flush=True)
    start = time.time()
    try:
        results[stage] = fn()
        results["_stage_status"][stage] = {
            "status": "ok",
            "seconds": round(time.time() - start, 2),
        }
    except Exception as exc:
        results[stage] = {"error": str(exc), "error_type": type(exc).__name__}
        results["_stage_status"][stage] = {
            "status": "error",
            "seconds": round(time.time() - start, 2),
            "error": str(exc),
        }
        print(f"[stage-error] {stage}: {exc}", flush=True)
    save(checkpoint, results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=sorted(DATASETS))
    parser.add_argument(
        "--jena-home",
        type=Path,
        default=ROOT / "tools" / "apache-jena-5.6.0-bin" / "apache-jena-5.6.0",
    )
    parser.add_argument("--fuseki-home", type=Path, default=ROOT / "apache-jena-fuseki-5.6.0")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    folder = DATASETS[args.dataset]
    output_dir = args.output_dir or ROOT / "latest-synthetic-rerun-results" / f"isolated-{args.dataset}"
    checkpoint = output_dir / "stage-results.json"
    params = EvaluationParameters()

    db = DatabaseManager(args.jena_home, folder)
    results: dict[str, Any] = {
        "dataset": args.dataset,
        "ekg_folder": str(folder),
        "timestamp": datetime.now().isoformat(),
        "runner": "run_synthetic_stage_eval_isolated.py",
        "_stage_status": {},
    }
    save(checkpoint, results)

    nt_files = list(folder.glob("*.nt"))
    if db.database_exists(nt_files):
        results["database"] = {"status": "reused", "path": str(db.db_path)}
    else:
        results["database"] = {
            "status": "loaded",
            "path": str(db.db_path),
            "parsed_triples_loaded": db.load_database(nt_files),
        }
    save(checkpoint, results)

    def graph_profile(endpoint: str) -> dict[str, Any]:
        edge_file = SPARQLExecutor(endpoint).extract_edges()
        try:
            graph = GraphAnalyzer().load_graph(edge_file)
            return GraphAnalyzer().calculate_metrics(graph)
        finally:
            Path(edge_file).unlink(missing_ok=True)

    def temporal(endpoint: str) -> dict[str, Any]:
        validator = TemporalValidator(endpoint, params)
        data = validator.validate_temporal_consistency()
        try:
            data["semantic_validation"] = validator.validate_temporal_semantics()
        except Exception as exc:
            data["semantic_validation"] = {"error": str(exc)}
        return data

    def completeness(endpoint: str) -> dict[str, Any]:
        analyzer = CompletenessAnalyzer(endpoint, nt_files)
        data = analyzer.analyze_completeness()
        try:
            data["population_completeness"] = analyzer.analyze_population_completeness()
        except Exception as exc:
            data["population_completeness"] = {"error": str(exc)}
        return data

    stages: list[tuple[str, Callable[[str], Any]]] = [
        ("graph_profile", graph_profile),
        ("temporal", temporal),
        ("redundancy", lambda e: RedundancyAnalyzer(e, params).analyze_redundancy()),
        ("type_consistency", lambda e: TypeConsistencyAnalyzer(e, params).analyze_type_consistency()),
        ("entity_richness", lambda e: EntityRichnessAnalyzer(e).analyze_entity_richness()),
        ("mapping_coverage", lambda e: MappingCoverageAnalyzer(e).analyze_mapping_coverage()),
        ("predicate_usage", lambda e: PredicateUsageAnalyzer(e).analyze_predicate_usage()),
        ("schema", lambda e: SchemaAnalyzer(e, params, nt_files).analyze_schema_conformance()),
        ("completeness", completeness),
    ]

    for stage, fn in stages:
        run_stage(stage, results, checkpoint, args.fuseki_home, db.db_path, fn)

    final_metrics = {
        **(results.get("graph_profile") or {}),
        "redundancy": results.get("redundancy"),
        "temporal": results.get("temporal"),
        "schema": results.get("schema"),
        "completeness": results.get("completeness"),
        "type_consistency": results.get("type_consistency"),
        "entity_richness": results.get("entity_richness"),
        "mapping_coverage": results.get("mapping_coverage"),
        "predicate_usage": results.get("predicate_usage"),
        "metric_audit": metric_audit(),
        "run_provenance": build_run_provenance(
            nt_files,
            params.__dict__,
            Path(__file__).resolve().parent,
        ),
        "timestamp": results["timestamp"],
        "ekg_folder": str(folder.absolute()),
        "runner": results["runner"],
        "_stage_status": results["_stage_status"],
    }

    if all(v["status"] == "ok" for v in results["_stage_status"].values()):
        output = OutputHandler(output_dir)
        output.display_results(final_metrics)
        results["final_outputs"] = {
            "json": str(output.save_json(final_metrics)),
            "csv": str(output.save_csv(final_metrics)),
            "metric_audit": str(output.save_metric_audit()),
        }
        save(checkpoint, results)
        return 0

    print("[warn] one or more stages failed; see checkpoint", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
