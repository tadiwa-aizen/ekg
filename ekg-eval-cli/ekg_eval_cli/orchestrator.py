"""Orchestration of the complete EKG evaluation workflow."""

from dataclasses import dataclass
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import sys

from .path_resolver import PathResolver
from .database import DatabaseManager
from .fuseki import FusekiManager
from .sparql import SPARQLExecutor, extract_edges_from_nt_files
from .analyzer import GraphAnalyzer
from .large_graph import LargeGraphAnalyzer
from .redundancy import RedundancyAnalyzer
from .temporal import TemporalValidator
from .schema_analyzer import SchemaAnalyzer
from .completeness import CompletenessAnalyzer
from .type_consistency import TypeConsistencyAnalyzer
from .entity_richness import EntityRichnessAnalyzer
from .mapping_coverage import MappingCoverageAnalyzer
from .predicate_usage import PredicateUsageAnalyzer
from .output import OutputHandler
from .config import EvaluationParameters
from .metric_registry import metric_audit
from .provenance import build_run_provenance, build_source_manifest, git_state


@dataclass
class EvaluationConfig:
    """Configuration for evaluation run."""
    ekg_folder: Path
    output_dir: Path
    jena_home: Optional[Path] = None
    fuseki_home: Optional[Path] = None
    verbose: bool = False
    port: int = 3030
    large_graph_mode: bool = False
    graph_structure_only: bool = False
    large_graph_work_dir: Optional[Path] = None
    duckdb_memory_limit: str = "8GB"
    duckdb_temp_dir: Optional[Path] = None
    parameters: Optional[EvaluationParameters] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = EvaluationParameters()


@dataclass
class ConnectivityMetrics:
    """Graph connectivity and cohesion metrics."""
    num_components: int
    giant_component_size: int
    total_nodes: int
    giant_component_ratio: float
    total_edges: int
    avg_clustering: float
    edge_connectivity: int
    timestamp: str
    ekg_folder: str


class EvaluationOrchestrator:
    """Orchestrates the entire evaluation workflow."""

    def __init__(self, config: EvaluationConfig):
        """
        Initialize the orchestrator with configuration.

        Args:
            config: EvaluationConfig object with all settings
        """
        self.config = config
        self.path_resolver = PathResolver()
        self.db_manager: Optional[DatabaseManager] = None
        self.fuseki_manager: Optional[FusekiManager] = None
        self.sparql_executor: Optional[SPARQLExecutor] = None
        self.analyzer = GraphAnalyzer()
        self.redundancy_analyzer: Optional[RedundancyAnalyzer] = None
        self.temporal_validator: Optional[TemporalValidator] = None
        self.schema_analyzer: Optional[SchemaAnalyzer] = None
        self.completeness_analyzer: Optional[CompletenessAnalyzer] = None
        self.type_consistency_analyzer: Optional[TypeConsistencyAnalyzer] = None
        self.entity_richness_analyzer: Optional[EntityRichnessAnalyzer] = None
        self.mapping_coverage_analyzer: Optional[MappingCoverageAnalyzer] = None
        self.predicate_usage_analyzer: Optional[PredicateUsageAnalyzer] = None
        self.output_handler = OutputHandler(config.output_dir)
        
        # Track state
        self.fuseki_process = None
        self.temp_edge_file: Optional[Path] = None
        self.nt_files: List[Path] = []
        self.resolved_jena_home: Optional[Path] = None
        self.resolved_fuseki_home: Optional[Path] = None
        self.project_root = Path(__file__).resolve().parent.parent
        self.source_snapshot = build_source_manifest(self.project_root)
        self.git_snapshot = git_state(self.project_root)

    def run(self) -> Dict[str, Any]:
        """
        Execute the complete evaluation workflow.

        Steps:
        1. Validate EKG folder
        2. Resolve Jena/Fuseki paths
        3. Initialize database (if needed)
        4. Start Fuseki (if needed)
        5. Extract edges via SPARQL
        6. Analyze with NetworkX
        7. Output results

        Returns:
            Dictionary containing all calculated metrics

        Raises:
            Various exceptions with context for each step failure
        """
        try:
            # Step 1: Validate EKG folder
            self._log("Step 1: Validating EKG folder...")
            nt_files = self._validate_ekg_folder()
            self.nt_files = nt_files
            self._log(f"Found {len(nt_files)} .nt files")

            # Step 2: Resolve Jena/Fuseki paths
            self._log("\nStep 2: Resolving Jena and Fuseki paths...")
            jena_home, fuseki_home = self._resolve_paths()
            self.resolved_jena_home = jena_home
            self.resolved_fuseki_home = fuseki_home
            self._log(f"Jena home: {jena_home}")
            self._log(f"Fuseki home: {fuseki_home}")

            # Step 3: Initialize database (if needed)
            self._log("\nStep 3: Checking database...")
            self.db_manager = DatabaseManager(jena_home, self.config.ekg_folder)
            
            if self.db_manager.database_exists(nt_files):
                self._log("Database already exists, skipping load")
            else:
                self._log("Database not found, loading data...")
                triples_loaded = self._load_database(nt_files)
                self._log(f"Loaded {triples_loaded:,} triples")

            # Step 4/5: Analyze graph structure.
            if self.config.large_graph_mode:
                self._log("\nStep 4: Analyzing graph structure in large graph mode...")
                metrics = self._analyze_large_graph(nt_files)
                self._log("Large graph analysis complete")
            else:
                # This streams the same IRI-to-IRI projection as the SPARQL
                # CONSTRUCT query, without materialising it through Fuseki/Jena.
                self._log("\nStep 4: Extracting graph edges from N-Triples files...")
                edge_file = self._extract_edges_from_nt_files(nt_files)
                self._log(f"Edges saved to: {edge_file}")

                self._log("\nStep 5: Analyzing graph structure with NetworkX...")
                metrics = self._analyze_graph(edge_file)
                self._log("Analysis complete")

            if self.config.graph_structure_only:
                self._log("\nGraph-structure-only mode enabled; skipping endpoint metrics.")
                metrics_dict = self._prepare_structure_only_metrics_dict(metrics)
                self._output_results(metrics_dict)
                self._cleanup()
                return metrics_dict

            # Step 6: Start Fuseki for the remaining SPARQL metric queries
            self._log("\nStep 6: Starting Fuseki server...")
            self.fuseki_manager = FusekiManager(
                fuseki_home, self.db_manager.db_path, port=self.config.port
            )
            self._start_fuseki()

            # Step 7: Analyze redundancy
            self._log("\nStep 7: Analyzing redundancy and duplication...")
            redundancy_metrics = self._analyze_redundancy()
            self._log("Redundancy analysis complete")

            # Step 8: Validate temporal consistency
            self._log("\nStep 8: Validating temporal consistency...")
            temporal_metrics = self._validate_temporal()
            self._log("Temporal validation complete")

            # Step 9: Analyze schema conformance
            self._log("\nStep 9: Analyzing schema conformance...")
            schema_metrics = self._analyze_schema()
            self._log("Schema analysis complete")

            # Step 10: Analyze completeness
            self._log("\nStep 10: Analyzing coverage and completeness...")
            completeness_metrics = self._analyze_completeness()
            self._log("Completeness analysis complete")

            # Step 11: Analyze type consistency
            self._log("\nStep 11: Analyzing type consistency...")
            type_metrics = self._analyze_type_consistency()
            self._log("Type consistency analysis complete")

            # Step 12: Entity richness
            self._log("\nStep 12: Analyzing entity richness...")
            richness_metrics = self._analyze_entity_richness()
            self._log("Entity richness analysis complete")

            # Step 13: Mapping coverage
            self._log("\nStep 13: Analyzing external mapping coverage...")
            mapping_metrics = self._analyze_mapping_coverage()
            self._log("Mapping coverage analysis complete")

            # Step 14: Predicate usage
            self._log("\nStep 14: Analyzing predicate usage patterns...")
            predicate_metrics = self._analyze_predicate_usage()
            self._log("Predicate usage analysis complete")

            # Step 15: Output results
            self._log("\nStep 15: Saving results...")
            metrics_dict = self._prepare_metrics_dict(
                metrics, redundancy_metrics, temporal_metrics,
                schema_metrics, completeness_metrics, type_metrics,
                richness_metrics, mapping_metrics, predicate_metrics
            )
            self._output_results(metrics_dict)

            # Clean up resources on success
            self._cleanup()

            return metrics_dict

        except KeyboardInterrupt:
            self._log("\nEvaluation interrupted by user")
            self._cleanup()
            raise
        except Exception as e:
            self._log(f"\nError during evaluation: {str(e)}")
            if self.config.verbose:
                import traceback
                traceback.print_exc()
            self._cleanup()
            raise

    def _validate_ekg_folder(self) -> List[Path]:
        """
        Validate that EKG folder exists and contains .nt files.

        Returns:
            List of paths to .nt files

        Raises:
            FileNotFoundError: If folder doesn't exist
            ValueError: If folder contains no .nt files
        """
        ekg_folder = self.config.ekg_folder

        # Check if folder exists
        if not ekg_folder.exists():
            raise FileNotFoundError(
                f"EKG folder does not exist: {ekg_folder}\n"
                f"Please provide a valid path to a folder containing .nt files."
            )

        if not ekg_folder.is_dir():
            raise ValueError(
                f"EKG folder path is not a directory: {ekg_folder}\n"
                f"Please provide a path to a folder, not a file."
            )

        # Find all .nt files
        nt_files = list(ekg_folder.glob("*.nt"))

        if not nt_files:
            raise ValueError(
                f"EKG folder contains no .nt files: {ekg_folder}\n"
                f"Please ensure the folder contains N-Triples (.nt) files."
            )

        return nt_files

    def _resolve_paths(self) -> tuple[Path, Path]:
        """
        Resolve Jena and Fuseki installation paths.

        Returns:
            Tuple of (jena_home, fuseki_home) paths

        Raises:
            FileNotFoundError: If installations cannot be found
        """
        try:
            jena_home = self.path_resolver.find_jena(
                str(self.config.jena_home) if self.config.jena_home else None
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Failed to locate Jena installation.\n{str(e)}"
            ) from e

        try:
            fuseki_home = self.path_resolver.find_fuseki(
                str(self.config.fuseki_home) if self.config.fuseki_home else None
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Failed to locate Fuseki installation.\n{str(e)}"
            ) from e

        return jena_home, fuseki_home

    def _load_database(self, nt_files: List[Path]) -> int:
        """
        Load .nt files into TDB2 database.

        Args:
            nt_files: List of .nt file paths to load

        Returns:
            Number of triples loaded

        Raises:
            RuntimeError: If database loading fails
        """
        if self.db_manager is None:
            raise RuntimeError("DatabaseManager not initialized")

        try:
            triples_loaded = self.db_manager.load_database(nt_files)
            return triples_loaded
        except Exception as e:
            raise RuntimeError(
                f"Failed to load database.\n{str(e)}"
            ) from e

    def _start_fuseki(self) -> None:
        """
        Start Fuseki server if not already running.

        Raises:
            RuntimeError: If Fuseki fails to start
        """
        if self.fuseki_manager is None:
            raise RuntimeError("FusekiManager not initialized")

        # Check if already running
        if self.fuseki_manager.is_running():
            raise RuntimeError(
                f"Fuseki is already running on port {self.config.port}. Stop the existing "
                "Fuseki process before running this evaluation so the CLI does "
                "not query a database from a previous run."
            )

        # Start Fuseki
        try:
            self._log("Starting Fuseki server...")
            self.fuseki_process = self.fuseki_manager.start_server()
            
            # Wait for server to be ready
            self._log("Waiting for Fuseki to be ready...")
            if not self.fuseki_manager.wait_for_ready(timeout=30):
                raise RuntimeError(
                    "Fuseki server failed to become ready within 30 seconds.\n"
                    f"Check if port {self.config.port} is available."
                )
            
            self._log(f"Fuseki server ready at {self.fuseki_manager.endpoint_url}")
            self.sparql_executor = SPARQLExecutor(self.fuseki_manager.endpoint_url)
            self._initialize_endpoint_analyzers()

        except Exception as e:
            raise RuntimeError(
                f"Failed to start Fuseki server.\n{str(e)}"
            ) from e

    def _initialize_endpoint_analyzers(self) -> None:
        """Initialize analyzers that query the Fuseki endpoint."""
        if self.fuseki_manager is None:
            raise RuntimeError("FusekiManager not initialized")

        self.redundancy_analyzer = RedundancyAnalyzer(
            self.fuseki_manager.endpoint_url,
            self.config.parameters
        )
        self.temporal_validator = TemporalValidator(
            self.fuseki_manager.endpoint_url,
            self.config.parameters,
            self.nt_files
        )
        self.schema_analyzer = SchemaAnalyzer(
            self.fuseki_manager.endpoint_url,
            self.config.parameters,
            self.nt_files
        )
        self.completeness_analyzer = CompletenessAnalyzer(
            self.fuseki_manager.endpoint_url,
            self.nt_files
        )
        self.type_consistency_analyzer = TypeConsistencyAnalyzer(
            self.fuseki_manager.endpoint_url,
            self.config.parameters
        )
        self.entity_richness_analyzer = EntityRichnessAnalyzer(self.fuseki_manager.endpoint_url)
        self.mapping_coverage_analyzer = MappingCoverageAnalyzer(self.fuseki_manager.endpoint_url)
        self.predicate_usage_analyzer = PredicateUsageAnalyzer(self.fuseki_manager.endpoint_url)

    def _extract_edges(self) -> Path:
        """
        Extract graph edges using SPARQL query.

        Returns:
            Path to temporary file containing edges

        Raises:
            RuntimeError: If SPARQL query fails
        """
        if self.sparql_executor is None:
            raise RuntimeError("SPARQLExecutor not initialized")

        try:
            edge_file = self.sparql_executor.extract_edges()
            self.temp_edge_file = edge_file
            return edge_file
        except Exception as e:
            raise RuntimeError(
                f"Failed to extract edges via SPARQL.\n{str(e)}"
            ) from e

    def _extract_edges_from_nt_files(self, nt_files: List[Path]) -> Path:
        """Extract graph edges directly from N-Triples files."""
        try:
            edge_file = extract_edges_from_nt_files(nt_files)
            self.temp_edge_file = edge_file
            return edge_file
        except Exception as e:
            raise RuntimeError(
                f"Failed to extract edges from N-Triples files.\n{str(e)}"
            ) from e

    def _analyze_graph(self, edge_file: Path) -> Dict[str, Any]:
        """
        Analyze graph structure using NetworkX.

        Args:
            edge_file: Path to file containing graph edges

        Returns:
            Dictionary of calculated metrics

        Raises:
            RuntimeError: If analysis fails
        """
        try:
            # Load graph
            self._log("Loading graph into NetworkX...")
            graph = self.analyzer.load_graph(edge_file)
            self._log(f"Graph loaded: {graph.number_of_nodes():,} nodes, {graph.number_of_edges():,} edges")

            # Calculate metrics
            self._log("Calculating metrics...")
            metrics = self.analyzer.calculate_metrics(graph)
            
            return metrics

        except Exception as e:
            raise RuntimeError(
                f"Failed to analyze graph.\n{str(e)}"
            ) from e

    def _analyze_large_graph(self, nt_files: List[Path]) -> Dict[str, Any]:
        """Analyze graph structure with out-of-core DuckDB and streaming union-find."""
        try:
            work_dir = self.config.large_graph_work_dir
            if work_dir is None:
                work_dir = self.config.output_dir / "large_graph_work"
            analyzer = LargeGraphAnalyzer(
                work_dir=work_dir,
                memory_limit=self.config.duckdb_memory_limit,
                temp_dir=self.config.duckdb_temp_dir,
                log=self._log,
            )
            return analyzer.analyze(nt_files)
        except Exception as e:
            raise RuntimeError(
                f"Failed to analyze graph in large graph mode.\n{str(e)}"
            ) from e

    def _analyze_redundancy(self) -> Dict[str, Any]:
        """
        Analyze redundancy and duplication.

        Returns:
            Dictionary of redundancy metrics

        Raises:
            RuntimeError: If analysis fails
        """
        if self.redundancy_analyzer is None:
            raise RuntimeError("RedundancyAnalyzer not initialized")

        try:
            return self.redundancy_analyzer.analyze_redundancy()
        except Exception as e:
            raise RuntimeError(
                f"Failed to analyze redundancy.\n{str(e)}"
            ) from e

    def _validate_temporal(self) -> Dict[str, Any]:
        """
        Validate temporal consistency.

        Returns:
            Dictionary of temporal validation metrics

        Raises:
            RuntimeError: If validation fails
        """
        if self.temporal_validator is None:
            raise RuntimeError("TemporalValidator not initialized")

        try:
            base_metrics = self.temporal_validator.validate_temporal_consistency()
            
            # Add semantic temporal validation
            try:
                semantic_metrics = self.temporal_validator.validate_temporal_semantics()
                base_metrics['semantic_validation'] = semantic_metrics
            except Exception as e:
                self._log(f"Warning: Semantic temporal validation failed: {e}")
                base_metrics['semantic_validation'] = {'error': str(e)}
            
            return base_metrics
        except Exception as e:
            raise RuntimeError(
                f"Failed to validate temporal consistency.\n{str(e)}"
            ) from e

    def _analyze_schema(self) -> Dict[str, Any]:
        """Analyze schema conformance."""
        if self.schema_analyzer is None:
            raise RuntimeError("SchemaAnalyzer not initialized")
        try:
            return self.schema_analyzer.analyze_schema_conformance()
        except Exception as e:
            raise RuntimeError(f"Failed to analyze schema.\n{str(e)}") from e

    def _analyze_completeness(self) -> Dict[str, Any]:
        """Analyze completeness."""
        if self.completeness_analyzer is None:
            raise RuntimeError("CompletenessAnalyzer not initialized")
        try:
            base_metrics = self.completeness_analyzer.analyze_completeness()
            
            # Add population completeness
            try:
                pop_metrics = self.completeness_analyzer.analyze_population_completeness()
                base_metrics['population_completeness'] = pop_metrics
            except Exception as e:
                self._log(f"Warning: Population completeness failed: {e}")
                base_metrics['population_completeness'] = {'error': str(e)}
            
            return base_metrics
        except Exception as e:
            raise RuntimeError(f"Failed to analyze completeness.\n{str(e)}") from e

    def _analyze_type_consistency(self) -> Dict[str, Any]:
        """Analyze type consistency."""
        if self.type_consistency_analyzer is None:
            raise RuntimeError("TypeConsistencyAnalyzer not initialized")
        try:
            return self.type_consistency_analyzer.analyze_type_consistency()
        except Exception as e:
            raise RuntimeError(f"Failed to analyze type consistency.\n{str(e)}") from e

    def _analyze_entity_richness(self) -> Dict[str, Any]:
        """Analyze entity richness."""
        if self.entity_richness_analyzer is None:
            raise RuntimeError("EntityRichnessAnalyzer not initialized")
        try:
            return self.entity_richness_analyzer.analyze_entity_richness()
        except Exception as e:
            raise RuntimeError(f"Failed to analyze entity richness.\n{str(e)}") from e

    def _analyze_mapping_coverage(self) -> Dict[str, Any]:
        """Analyze mapping coverage."""
        if self.mapping_coverage_analyzer is None:
            raise RuntimeError("MappingCoverageAnalyzer not initialized")
        try:
            return self.mapping_coverage_analyzer.analyze_mapping_coverage()
        except Exception as e:
            raise RuntimeError(f"Failed to analyze mapping coverage.\n{str(e)}") from e

    def _analyze_predicate_usage(self) -> Dict[str, Any]:
        """Analyze predicate usage."""
        if self.predicate_usage_analyzer is None:
            raise RuntimeError("PredicateUsageAnalyzer not initialized")
        try:
            return self.predicate_usage_analyzer.analyze_predicate_usage()
        except Exception as e:
            raise RuntimeError(f"Failed to analyze predicate usage.\n{str(e)}") from e

    def _prepare_metrics_dict(self, metrics: Dict[str, Any], 
                             redundancy: Dict[str, Any],
                             temporal: Dict[str, Any],
                             schema: Dict[str, Any],
                             completeness: Dict[str, Any],
                             type_consistency: Dict[str, Any],
                             entity_richness: Dict[str, Any],
                             mapping_coverage: Dict[str, Any],
                             predicate_usage: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metrics dictionary with metadata."""
        combined = {
            **metrics,
            'redundancy': redundancy,
            'temporal': temporal,
            'schema': schema,
            'completeness': completeness,
            'type_consistency': type_consistency,
            'entity_richness': entity_richness,
            'mapping_coverage': mapping_coverage,
            'predicate_usage': predicate_usage,
            'metric_audit': metric_audit(),
            'run_provenance': self._build_provenance(),
            'timestamp': datetime.now().isoformat(),
            'ekg_folder': str(self.config.ekg_folder.absolute())
        }
        return combined

    def _prepare_structure_only_metrics_dict(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare a result dictionary for graph-structure-only runs."""
        return {
            **metrics,
            'metric_audit': metric_audit(),
            'run_provenance': self._build_provenance(),
            'timestamp': datetime.now().isoformat(),
            'ekg_folder': str(self.config.ekg_folder.absolute()),
            'run_scope': 'graph_structure_only'
        }

    def _build_provenance(self) -> Dict[str, Any]:
        """Capture metric parameters and execution choices for this exact run."""

        parameters = {
            "metric_parameters": asdict(self.config.parameters),
            "execution": {
                "port": self.config.port,
                "large_graph_mode": self.config.large_graph_mode,
                "graph_structure_only": self.config.graph_structure_only,
                "duckdb_memory_limit": self.config.duckdb_memory_limit,
                "duckdb_temp_dir": str(self.config.duckdb_temp_dir.resolve())
                if self.config.duckdb_temp_dir else None,
                "large_graph_work_dir": str(self.config.large_graph_work_dir.resolve())
                if self.config.large_graph_work_dir else None,
                "jena_home": str(self.resolved_jena_home.resolve())
                if self.resolved_jena_home else None,
                "fuseki_home": str(self.resolved_fuseki_home.resolve())
                if self.resolved_fuseki_home else None,
            },
        }
        return build_run_provenance(
            self.nt_files,
            parameters,
            self.project_root,
            source_snapshot=self.source_snapshot,
            git_snapshot=self.git_snapshot,
        )

    def _prepare_metrics_dict_old(self, metrics: Dict[str, Any], 
                             redundancy: Dict[str, Any],
                             temporal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare metrics dictionary with metadata (legacy).

        Args:
            metrics: Raw metrics from analyzer

        Returns:
            Enhanced metrics dictionary with timestamp and folder info
        """
        # Add timestamp and folder information
        metrics['timestamp'] = datetime.now().isoformat()
        metrics['ekg_folder'] = str(self.config.ekg_folder.absolute())
        
        return metrics

    def _output_results(self, metrics: Dict[str, Any]) -> None:
        """
        Output results to console and files.

        Args:
            metrics: Dictionary of metrics to output

        Raises:
            OSError: If file writing fails
        """
        try:
            # Display to console
            self.output_handler.display_results(metrics)

            # Save to JSON
            json_path = self.output_handler.save_json(metrics)
            self._log(f"Results saved to JSON: {json_path}")

            # Save to CSV
            csv_path = self.output_handler.save_csv(metrics)
            self._log(f"Results saved to CSV: {csv_path}")

            # Save metric provenance audit
            audit_path = self.output_handler.save_metric_audit()
            self._log(f"Metric audit saved to Markdown: {audit_path}")

        except Exception as e:
            raise OSError(
                f"Failed to save results.\n{str(e)}"
            ) from e

    def _cleanup(self) -> None:
        """Clean up resources (stop Fuseki, delete temp files)."""
        # Stop Fuseki if we started it
        if self.fuseki_process is not None and self.fuseki_manager is not None:
            self._log("Stopping Fuseki server...")
            try:
                self.fuseki_manager.stop_server(self.fuseki_process)
            except Exception as e:
                self._log(f"Warning: Failed to stop Fuseki: {e}")

        # Delete temporary edge file
        if self.temp_edge_file is not None and self.temp_edge_file.exists():
            try:
                self.temp_edge_file.unlink()
            except Exception as e:
                self._log(f"Warning: Failed to delete temp file: {e}")

    def _log(self, message: str) -> None:
        """
        Log a message if verbose mode is enabled.

        Args:
            message: Message to log
        """
        if self.config.verbose:
            print(message)
