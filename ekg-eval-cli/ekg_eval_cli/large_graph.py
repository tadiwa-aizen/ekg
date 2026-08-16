"""Out-of-core graph structure analysis for large RDF EKG projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional
import json

import duckdb
import numpy as np

from .projection import PROJECTION_DESCRIPTION, parse_iri_triple
from .provenance import build_input_manifest, sha256_file

try:
    from numba import njit
except Exception:  # pragma: no cover - optional acceleration
    njit = None


def _quote_sql(value: Path | str) -> str:
    """Return a single-quoted SQL string literal."""
    return "'" + str(value).replace("'", "''").replace("\\", "/") + "'"


if njit is not None:

    @njit
    def _find(parent: np.ndarray, x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    @njit
    def _union_batch(parent: np.ndarray, rank: np.ndarray, left: np.ndarray, right: np.ndarray) -> None:
        for i in range(left.shape[0]):
            root_left = _find(parent, left[i])
            root_right = _find(parent, right[i])
            if root_left == root_right:
                continue
            if rank[root_left] < rank[root_right]:
                parent[root_left] = root_right
            elif rank[root_left] > rank[root_right]:
                parent[root_right] = root_left
            else:
                parent[root_right] = root_left
                rank[root_left] += 1

    @njit
    def _count_component_sizes(parent: np.ndarray, sizes: np.ndarray) -> None:
        for i in range(parent.shape[0]):
            root = _find(parent, i)
            parent[i] = root
            sizes[root] += 1


class LargeGraphAnalyzer:
    """Compute structural graph metrics without materialising NetworkX graphs."""

    def __init__(
        self,
        work_dir: Path,
        memory_limit: str = "8GB",
        temp_dir: Optional[Path] = None,
        batch_size: int = 250_000,
        log: Optional[Callable[[str], None]] = None,
    ):
        self.work_dir = Path(work_dir)
        self.memory_limit = memory_limit
        self.temp_dir = Path(temp_dir) if temp_dir else self.work_dir / "duckdb-temp"
        self.batch_size = batch_size
        self.log = log or (lambda _message: None)
        self.db_path = self.work_dir / "large_graph_domain_v2.duckdb"
        self.edge_tsv_path = self.work_dir / "projected_domain_edges_v2.tsv"
        self.node_tsv_path = self.work_dir / "projected_domain_nodes_v2.tsv"
        self.projection_manifest_path = self.work_dir / "projection_manifest_v2.json"
        self.parent_path = self.work_dir / "union_find_parent_v2.i64"
        self.rank_path = self.work_dir / "union_find_rank_v2.u1"
        self.sizes_path = self.work_dir / "component_sizes_v2.u8"

    def analyze(self, nt_files: Iterable[Path]) -> Dict[str, Any]:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        nt_files = list(nt_files)
        input_manifest = build_input_manifest(
            nt_files, nt_files[0].parent / ".ekg_eval_input_manifest.json"
        )
        edge_rows, projection_reused = self._ensure_projection_files(nt_files, input_manifest)

        with duckdb.connect(str(self.db_path)) as con:
            self._configure_duckdb(con)
            self._ensure_edge_tables(con, force_rebuild=not projection_reused)
            node_count = int(con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
            edge_count = int(con.execute("SELECT COUNT(*) FROM edges_id").fetchone()[0])
            degree_stats = self._degree_stats(con, node_count, edge_count)
            component_stats = self._component_stats(con, node_count)

        density = 0.0
        if node_count > 1:
            density = (2.0 * edge_count) / (node_count * (node_count - 1))

        edge_connectivity = -1
        edge_connectivity_status = "not_computed_large_graph_mode"
        if component_stats["num_components"] > 1:
            edge_connectivity = 0
            edge_connectivity_status = "conditional_exact_disconnected_graph"
        elif degree_stats["min_degree"] == 1:
            edge_connectivity = 1
            edge_connectivity_status = "conditional_exact_connected_graph_with_leaf"

        return {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "num_components": component_stats["num_components"],
            "giant_component_size": component_stats["giant_component_size"],
            "giant_component_ratio": component_stats["giant_component_ratio"],
            "avg_clustering": -1.0,
            "avg_clustering_status": "not_computed_large_graph_mode",
            "edge_connectivity": edge_connectivity,
            "edge_connectivity_status": edge_connectivity_status,
            "avg_degree": degree_stats["avg_degree"],
            "density": density,
            "min_degree": degree_stats["min_degree"],
            "max_degree": degree_stats["max_degree"],
            "leaf_count": degree_stats["leaf_count"],
            "leaf_fraction": degree_stats["leaf_fraction"],
            "large_graph_mode": {
                "enabled": True,
                "projection": PROJECTION_DESCRIPTION,
                "raw_projected_edge_rows": edge_rows,
                "unique_undirected_edges": edge_count,
                "duckdb_database": str(self.db_path),
                "projected_edge_tsv": str(self.edge_tsv_path),
                "projected_node_tsv": str(self.node_tsv_path),
                "input_aggregate_sha256": input_manifest["aggregate_sha256"],
                "memory_limit": self.memory_limit,
            },
        }

    def _configure_duckdb(self, con: duckdb.DuckDBPyConnection) -> None:
        con.execute(f"SET memory_limit = {_quote_sql(self.memory_limit)}")
        con.execute(f"SET temp_directory = {_quote_sql(self.temp_dir)}")
        con.execute("PRAGMA threads=4")

    def _ensure_projection_files(
        self, nt_files: Iterable[Path], input_manifest: Dict[str, Any]
    ) -> tuple[int, bool]:
        count_path = self.work_dir / "projected_domain_edges_v2.count"
        projection_code_sha256 = sha256_file(Path(__file__).with_name("projection.py"))
        if (
            self.edge_tsv_path.exists()
            and self.node_tsv_path.exists()
            and count_path.exists()
            and self.projection_manifest_path.exists()
        ):
            recorded = json.loads(self.projection_manifest_path.read_text(encoding="utf-8"))
            if (
                recorded.get("aggregate_sha256") == input_manifest.get("aggregate_sha256")
                and recorded.get("projection") == PROJECTION_DESCRIPTION
                and recorded.get("projection_code_sha256") == projection_code_sha256
            ):
                count = int(count_path.read_text(encoding="utf-8").strip())
                self.log(f"Reusing fingerprinted domain projection with {count:,} raw edges")
                return count, True
            raise RuntimeError(
                "Large-graph projection cache does not match the input manifest. "
                f"Use a new work directory or remove the stale v2 artefacts in {self.work_dir}."
            )

        self.log(f"Writing projected domain edges to {self.edge_tsv_path}")
        count = 0
        node_rows = 0
        with (
            self.edge_tsv_path.open("w", encoding="utf-8", newline="\n") as edge_target,
            self.node_tsv_path.open("w", encoding="utf-8", newline="\n") as node_target,
        ):
            edge_target.write("u\tv\n")
            node_target.write("node\n")
            for nt_file in nt_files:
                file_count = 0
                with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                    for line in source:
                        record = parse_iri_triple(line)
                        if not record:
                            continue
                        if record.is_direct_event_declaration:
                            node_target.write(f"{record.subject}\n")
                            node_rows += 1
                        if record.is_domain_edge:
                            left, right = record.subject, record.object
                            if left > right:
                                left, right = right, left
                            edge_target.write(f"{left}\t{right}\n")
                            node_target.write(f"{left}\n{right}\n")
                            node_rows += 2
                            count += 1
                            file_count += 1
                self.log(f"  {nt_file.name}: {file_count:,} projected rows")

        count_path.write_text(str(count), encoding="utf-8")
        self.projection_manifest_path.write_text(
            json.dumps(
                {
                    **input_manifest,
                    "projection": PROJECTION_DESCRIPTION,
                    "projection_code_sha256": projection_code_sha256,
                    "raw_edge_rows": count,
                    "raw_node_rows": node_rows,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return count, False

    def _ensure_edge_tables(
        self, con: duckdb.DuckDBPyConnection, force_rebuild: bool = False
    ) -> None:
        existing = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        required = {"canonical_edges", "nodes", "edges_id", "degrees"}
        if required.issubset(existing) and not force_rebuild:
            self.log("Reusing existing DuckDB graph tables")
            return

        self.log("Building DuckDB graph tables")
        con.execute("DROP TABLE IF EXISTS raw_edges")
        con.execute("DROP TABLE IF EXISTS raw_nodes")
        con.execute("DROP TABLE IF EXISTS canonical_edges")
        con.execute("DROP TABLE IF EXISTS nodes")
        con.execute("DROP TABLE IF EXISTS edges_id")
        con.execute("DROP TABLE IF EXISTS degrees")
        con.execute("CREATE TABLE raw_edges (u VARCHAR, v VARCHAR)")
        con.execute("CREATE TABLE raw_nodes (node VARCHAR)")
        con.execute(
            f"COPY raw_nodes FROM {_quote_sql(self.node_tsv_path)} "
            "(DELIMITER '\t', HEADER TRUE)"
        )
        con.execute(
            f"COPY raw_edges FROM {_quote_sql(self.edge_tsv_path)} "
            "(DELIMITER '\t', HEADER TRUE)"
        )
        con.execute(
            """
            CREATE TABLE canonical_edges AS
            SELECT DISTINCT u, v
            FROM raw_edges
            WHERE u <> v
            """
        )
        con.execute(
            """
            CREATE TABLE nodes AS
            SELECT node, ROW_NUMBER() OVER (ORDER BY node) - 1 AS id
            FROM (
                SELECT node FROM raw_nodes
                UNION
                SELECT u AS node FROM canonical_edges
                UNION
                SELECT v AS node FROM canonical_edges
            )
            """
        )
        con.execute(
            """
            CREATE TABLE edges_id AS
            SELECT CAST(nu.id AS BIGINT) AS u, CAST(nv.id AS BIGINT) AS v
            FROM canonical_edges e
            JOIN nodes nu ON e.u = nu.node
            JOIN nodes nv ON e.v = nv.node
            """
        )
        con.execute(
            """
            CREATE TABLE degrees AS
            SELECT id, COUNT(*) AS degree
            FROM (
                SELECT u AS id FROM edges_id
                UNION ALL
                SELECT v AS id FROM edges_id
            )
            GROUP BY id
            """
        )

    def _degree_stats(
        self, con: duckdb.DuckDBPyConnection, node_count: int, edge_count: int
    ) -> Dict[str, Any]:
        if node_count == 0:
            return {
                "avg_degree": 0.0,
                "min_degree": 0,
                "max_degree": 0,
                "leaf_count": 0,
                "leaf_fraction": 0.0,
            }

        degree_rows, min_degree, max_degree, leaf_count = con.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(MIN(degree), 0),
                COALESCE(MAX(degree), 0),
                COALESCE(SUM(CASE WHEN degree = 1 THEN 1 ELSE 0 END), 0)
            FROM degrees
            """
        ).fetchone()
        if int(degree_rows) < node_count:
            min_degree = 0
        avg_degree = (2.0 * edge_count) / node_count
        return {
            "avg_degree": avg_degree,
            "min_degree": int(min_degree),
            "max_degree": int(max_degree),
            "leaf_count": int(leaf_count),
            "leaf_fraction": int(leaf_count) / node_count,
        }

    def _component_stats(
        self, con: duckdb.DuckDBPyConnection, node_count: int
    ) -> Dict[str, Any]:
        if node_count == 0:
            return {
                "num_components": 0,
                "giant_component_size": 0,
                "giant_component_ratio": 0.0,
            }
        if njit is None:
            raise RuntimeError(
                "numba is required for large graph connected-components analysis"
            )

        self.log(f"Running streaming union-find over {node_count:,} nodes")
        parent = np.memmap(self.parent_path, mode="w+", dtype=np.int64, shape=(node_count,))
        rank = np.memmap(self.rank_path, mode="w+", dtype=np.uint8, shape=(node_count,))
        sizes = np.memmap(self.sizes_path, mode="w+", dtype=np.uint64, shape=(node_count,))
        parent[:] = np.arange(node_count, dtype=np.int64)
        rank[:] = 0
        sizes[:] = 0

        cursor = con.execute("SELECT u, v FROM edges_id")
        processed = 0
        while True:
            rows = cursor.fetchmany(self.batch_size)
            if not rows:
                break
            edges = np.asarray(rows, dtype=np.int64)
            _union_batch(parent, rank, edges[:, 0], edges[:, 1])
            processed += edges.shape[0]
            if processed % (self.batch_size * 20) == 0:
                self.log(f"  unioned {processed:,} edges")

        self.log("Counting connected components")
        _count_component_sizes(parent, sizes)
        sizes.flush()
        parent.flush()
        positive = sizes[sizes > 0]
        component_count = int(positive.shape[0])
        giant_size = int(positive.max()) if component_count else 0
        return {
            "num_components": component_count,
            "giant_component_size": giant_size,
            "giant_component_ratio": giant_size / node_count if node_count else 0.0,
        }
