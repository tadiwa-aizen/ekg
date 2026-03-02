"""Graph analysis using NetworkX."""

from pathlib import Path
from typing import Dict, Any
import networkx as nx
import re


class GraphAnalyzer:
    """Analyzes graph structure using NetworkX."""

    def load_graph(self, edge_file: Path) -> nx.Graph:
        """
        Load edge list into NetworkX undirected graph.

        Parses N-Triples format edge file and extracts subject-object pairs
        to build an undirected graph for connectivity analysis.

        Args:
            edge_file: Path to N-Triples file containing edges

        Returns:
            NetworkX undirected graph

        Raises:
            FileNotFoundError: If edge file doesn't exist
            RuntimeError: If graph loading fails
            OSError: If file cannot be read
        """
        if not edge_file.exists():
            raise FileNotFoundError(
                f"Edge file not found: {edge_file}\n"
                f"The SPARQL query may have failed to produce results."
            )

        try:
            # Create an undirected graph
            graph = nx.Graph()

            # Parse N-Triples format
            # Format: <subject> <predicate> <object> .
            # We extract subject and object as nodes, creating edges between them
            pattern = re.compile(r'<([^>]+)>\s+<[^>]+>\s+<([^>]+)>\s+\.')

            edge_count = 0
            with open(edge_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    match = pattern.match(line)
                    if match:
                        subject = match.group(1)
                        obj = match.group(2)
                        # Add edge (automatically adds nodes if they don't exist)
                        graph.add_edge(subject, obj)
                        edge_count += 1

            if edge_count == 0:
                raise RuntimeError(
                    f"No valid edges found in {edge_file}.\n"
                    f"The file may be empty or in an incorrect format.\n"
                    f"Expected N-Triples format: <subject> <predicate> <object> ."
                )

            return graph

        except PermissionError as e:
            raise OSError(
                f"Permission denied: Cannot read edge file {edge_file}.\n"
                f"Please check file permissions."
            ) from e
        except UnicodeDecodeError as e:
            raise RuntimeError(
                f"Failed to decode edge file {edge_file}.\n"
                f"The file may contain invalid UTF-8 characters.\n"
                f"Error: {str(e)}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to load graph from {edge_file}.\n"
                f"Error: {str(e)}"
            ) from e

    def calculate_metrics(self, graph: nx.Graph) -> Dict[str, Any]:
        """
        Calculate all connectivity and cohesion metrics.

        Computes structural metrics including connected components,
        giant component analysis, clustering, and edge connectivity.

        Args:
            graph: NetworkX undirected graph

        Returns:
            Dictionary containing:
            - num_components: Number of connected components
            - giant_component_size: Size of largest connected component
            - total_nodes: Total number of nodes in graph
            - giant_component_ratio: Ratio of giant component to total nodes
            - total_edges: Total number of edges in graph
            - avg_clustering: Average clustering coefficient
            - edge_connectivity: Minimum edge connectivity

        Raises:
            RuntimeError: If metric calculation fails
            ValueError: If graph is invalid
        """
        if graph is None:
            raise ValueError("Graph cannot be None")

        try:
            metrics = {}

            # Total nodes and edges
            metrics['total_nodes'] = graph.number_of_nodes()
            metrics['total_edges'] = graph.number_of_edges()

            # Handle empty graph
            if metrics['total_nodes'] == 0:
                metrics['num_components'] = 0
                metrics['giant_component_size'] = 0
                metrics['giant_component_ratio'] = 0.0
                metrics['avg_clustering'] = 0.0
                metrics['edge_connectivity'] = 0
                return metrics

            # Connected components
            try:
                components = list(nx.connected_components(graph))
                metrics['num_components'] = len(components)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to calculate connected components.\n"
                    f"Error: {str(e)}"
                ) from e

            # Giant component (largest connected component)
            if components:
                giant_component = max(components, key=len)
                metrics['giant_component_size'] = len(giant_component)
                metrics['giant_component_ratio'] = (
                    metrics['giant_component_size'] / metrics['total_nodes']
                )
            else:
                metrics['giant_component_size'] = 0
                metrics['giant_component_ratio'] = 0.0

            # Average clustering coefficient
            try:
                metrics['avg_clustering'] = nx.average_clustering(graph)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to calculate average clustering coefficient.\n"
                    f"Error: {str(e)}"
                ) from e

            # Edge connectivity (minimum number of edges to disconnect graph)
            # This can be expensive for large graphs, so we handle potential issues
            if metrics['num_components'] > 1:
                # Disconnected graph has edge connectivity of 0
                metrics['edge_connectivity'] = 0
            elif metrics['total_nodes'] == 1:
                # Single node has edge connectivity of 0
                metrics['edge_connectivity'] = 0
            else:
                # For connected graphs, calculate edge connectivity
                # This can be slow for very large graphs
                try:
                    metrics['edge_connectivity'] = nx.edge_connectivity(graph)
                except MemoryError as e:
                    raise RuntimeError(
                        f"Out of memory while calculating edge connectivity.\n"
                        f"The graph may be too large for this metric.\n"
                        f"Graph size: {metrics['total_nodes']:,} nodes, {metrics['total_edges']:,} edges"
                    ) from e
                except Exception as e:
                    # If calculation fails (e.g., too large), set to -1 to indicate error
                    metrics['edge_connectivity'] = -1

            # Graph density
            try:
                metrics['density'] = nx.density(graph)
            except Exception as e:
                metrics['density'] = 0.0

            # Average degree
            if metrics['total_nodes'] > 0:
                metrics['avg_degree'] = (2 * metrics['total_edges']) / metrics['total_nodes']
            else:
                metrics['avg_degree'] = 0.0

            return metrics

        except MemoryError as e:
            raise RuntimeError(
                f"Out of memory while analyzing graph.\n"
                f"The graph may be too large for analysis.\n"
                f"Try analyzing a smaller subset of the data."
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to calculate metrics.\n"
                f"Error: {str(e)}"
            ) from e
