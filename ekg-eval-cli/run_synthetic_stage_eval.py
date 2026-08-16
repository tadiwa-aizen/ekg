"""Run synthetic EKG evaluations stage by stage with checkpoints.

This runner avoids the brittle all-or-nothing CLI path on Windows/Fuseki:
each metric group is executed separately, intermediate results are saved after
every stage, and the Fuseki Java process is stopped explicitly.
"""

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


def wait_for_fuseki(timeout: int = 30) -> None:
    for _ in range(timeout):
        try:
            response = requests.get("http://localhost:3030/$/ping", timeout=1)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Fuseki did not become ready on port 3030")


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [json_safe(v) for v in value]
        return str(value)


def save_checkpoint(path: Path, results: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(results), indent=2), encoding="utf-8")


def run_stage(
    name: str,
    results: dict[str, Any],
    checkpoint: Path,
    fn: Callable[[], Any],
) -> None:
    print(f"[stage] {name}", flush=True)
    start = time.time()
    try:
        value = fn()
        results[name] = value
        results.setdefault("_stage_status", {})[name] = {
            "status": "ok",
            "seconds": round(time.time() - start, 2),
        }
    except Exception as exc:
        results[name] = {"error": str(exc), "error_type": type(exc).__name__}
        results.setdefault("_stage_status", {})[name] = {
            "status": "error",
            "seconds": round(time.time() - start, 2),
            "error": str(exc),
        }
        print(f"[stage-error] {name}: {exc}", flush=True)
    save_checkpoint(checkpoint, results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=sorted(DATASETS))
    parser.add_argument(
        "--jena-home",
        type=Path,
        default=ROOT / "tools" / "apache-jena-5.6.0-bin" / "apache-jena-5.6.0",
    )
    parser.add_argument(
        "--fuseki-home",
        type=Path,
        default=ROOT / "apache-jena-fuseki-5.6.0",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    dataset_folder = DATASETS[args.dataset]
    output_dir = args.output_dir or ROOT / "latest-synthetic-rerun-results" / f"staged-{args.dataset}"
    checkpoint = output_dir / "stage-results.json"

    params = EvaluationParameters()
    db_manager = DatabaseManager(args.jena_home, dataset_folder)

    results: dict[str, Any] = {
        "dataset": args.dataset,
        "ekg_folder": str(dataset_folder),
        "timestamp": datetime.now().isoformat(),
        "runner": "run_synthetic_stage_eval.py",
        "_stage_status": {},
    }
    save_checkpoint(checkpoint, results)

    nt_files = list(dataset_folder.glob("*.nt"))
    if db_manager.database_exists():
        results["database"] = {"status": "reused", "path": str(db_manager.db_path)}
    else:
        loaded = db_manager.load_database(nt_files)
        results["database"] = {
            "status": "loaded",
            "path": str(db_manager.db_path),
            "parsed_triples_loaded": loaded,
        }
    save_checkpoint(checkpoint, results)

    endpoint = "http://localhost:3030/eventkg"
    fuseki_cmd = [
        "java",
        "-Xmx4G",
        "-cp",
        "fuseki-server.jar",
        "org.apache.jena.fuseki.main.cmds.FusekiServerCmd",
        "--loc",
        str(db_manager.db_path),
        "/eventkg",
    ]

    process = subprocess.Popen(
        fuseki_cmd,
        cwd=str(args.fuseki_home),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    edge_file: Path | None = None
    try:
        wait_for_fuseki()
        results["fuseki"] = {"status": "started", "endpoint": endpoint}
        save_checkpoint(checkpoint, results)

        graph_analyzer = GraphAnalyzer()

        def graph_profile() -> dict[str, Any]:
            nonlocal edge_file
            edge_file = SPARQLExecutor(endpoint).extract_edges()
            graph = graph_analyzer.load_graph(edge_file)
            return graph_analyzer.calculate_metrics(graph)

        run_stage("graph_profile", results, checkpoint, graph_profile)
        def temporal() -> dict[str, Any]:
            validator = TemporalValidator(endpoint, params)
            data = validator.validate_temporal_consistency()
            try:
                data["semantic_validation"] = validator.validate_temporal_semantics()
            except Exception as exc:
                data["semantic_validation"] = {"error": str(exc)}
            return data

        run_stage("temporal", results, checkpoint, temporal)
        run_stage(
            "redundancy",
            results,
            checkpoint,
            lambda: RedundancyAnalyzer(endpoint, params).analyze_redundancy(),
        )
        run_stage(
            "schema",
            results,
            checkpoint,
            lambda: SchemaAnalyzer(endpoint, params).analyze_schema_conformance(),
        )

        def completeness() -> dict[str, Any]:
            analyzer = CompletenessAnalyzer(endpoint)
            data = analyzer.analyze_completeness()
            try:
                data["population_completeness"] = analyzer.analyze_population_completeness()
            except Exception as exc:
                data["population_completeness"] = {"error": str(exc)}
            return data

        run_stage("completeness", results, checkpoint, completeness)
        run_stage(
            "type_consistency",
            results,
            checkpoint,
            lambda: TypeConsistencyAnalyzer(endpoint, params).analyze_type_consistency(),
        )
        run_stage(
            "entity_richness",
            results,
            checkpoint,
            lambda: EntityRichnessAnalyzer(endpoint).analyze_entity_richness(),
        )
        run_stage(
            "mapping_coverage",
            results,
            checkpoint,
            lambda: MappingCoverageAnalyzer(endpoint).analyze_mapping_coverage(),
        )
        run_stage(
            "predicate_usage",
            results,
            checkpoint,
            lambda: PredicateUsageAnalyzer(endpoint).analyze_predicate_usage(),
        )
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
            "timestamp": results["timestamp"],
            "ekg_folder": str(dataset_folder.absolute()),
            "runner": results["runner"],
            "_stage_status": results["_stage_status"],
        }
        results["final_outputs"] = {}
        if all(stage["status"] == "ok" for stage in results["_stage_status"].values()):
            output = OutputHandler(output_dir)
            output.display_results(final_metrics)
            results["final_outputs"] = {
                "json": str(output.save_json(final_metrics)),
                "csv": str(output.save_csv(final_metrics)),
                "metric_audit": str(output.save_metric_audit()),
            }
            save_checkpoint(checkpoint, results)
        else:
            save_checkpoint(checkpoint, results)
            print("[warn] not all stages succeeded; final CSV/JSON not emitted", flush=True)

    finally:
        if edge_file and edge_file.exists():
            try:
                edge_file.unlink()
            except OSError:
                pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    failures = [
        name
        for name, stage in results.get("_stage_status", {}).items()
        if stage.get("status") != "ok"
    ]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
