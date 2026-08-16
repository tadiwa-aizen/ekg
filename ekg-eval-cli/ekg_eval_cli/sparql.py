"""SPARQL query execution for extracting graph edges."""

from pathlib import Path
import tempfile
import requests
from typing import Optional
import os
import platform
import subprocess
from typing import Iterable

from .projection import (
    LINK_PREDICATE,
    NODE_PREDICATE,
    parse_iri_triple,
    projection_filter_sparql,
)


class SPARQLExecutor:
    """
    Executes SPARQL queries against Fuseki.
    
    Graph projection specification:
    ===============================
    
    This class projects RDF graphs to analysis graphs for network algorithms.
    
    VERTICES (Nodes):
        - Include: IRIs only
        - Exclude: Literals (values, not entities)
        - Exclude: Blank nodes (implementation artifacts)
        - Rationale: Network analysis requires stable entity identifiers
        - Filter: FILTER(isIRI(?s) && isIRI(?o))
    
    EDGES (Relationships):
        - Include: Domain-relation IRI-to-IRI triples
        - Exclude: rdf:type and schema/vocabulary predicates
        - Exclude: Datatype properties (IRI-to-literal triples)
        - Directionality: Treated as undirected for connectivity metrics
        - Multi-edges: Collapsed to single edge per node pair
        - Rationale: Focus on structural relationships, not attribute values
    
    SPARQL CONSTRUCT Query:
        Domain edges are projected to a generic edge predicate. Direct
        sem:Event resources are also emitted as node declarations so events
        with no domain-relation edge remain visible as isolated nodes.
    
    Notes:
        - Predicate information is discarded (replaced with <urn:link>)
        - Semantic information is preserved in separate SPARQL queries
    
    References:
        - RDF 1.1 Concepts: https://www.w3.org/TR/rdf11-concepts/
        - Newman, M. (2018). Networks (2nd ed.). Oxford University Press.
        - Zaveri et al. (2016). Quality assessment for Linked Data
    """

    def __init__(self, endpoint_url: str):
        """
        Initialize SPARQLExecutor.

        Args:
            endpoint_url: URL of the SPARQL endpoint (e.g., http://localhost:3030/eventkg)
        """
        self.endpoint_url = endpoint_url
        # Construct the query endpoint URL
        # Fuseki uses /sparql for queries
        if not endpoint_url.endswith('/sparql'):
            self.query_url = f"{endpoint_url}/sparql"
        else:
            self.query_url = endpoint_url

    def extract_edges(self) -> Path:
        """
        Execute CONSTRUCT query to extract IRI-to-IRI edges.
        Returns path to temporary file containing edge list.

        The query extracts all subject-object pairs where both are IRIs,
        creating a simplified edge list suitable for graph analysis.

        Query:
        CONSTRUCT { ?s <urn:link> ?o . }
        WHERE { ?s ?p ?o . FILTER(isIRI(?s) && isIRI(?o)) }

        Returns:
            Path to temporary file containing the edge list in N-Triples format

        Raises:
            RuntimeError: If the SPARQL query fails
            requests.exceptions.RequestException: If HTTP request fails
        """
        predicate_filter = projection_filter_sparql("?p")
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        CONSTRUCT {{
            ?s <{LINK_PREDICATE}> ?o .
            ?event <{NODE_PREDICATE}> ?event .
        }}
        WHERE {{
            {{
                ?s ?p ?o .
                FILTER(isIRI(?s) && isIRI(?o))
                {predicate_filter}
            }}
            UNION
            {{ ?event a sem:Event . }}
        }}
        """

        # Prepare the HTTP POST request
        headers = {
            'Accept': 'application/n-triples',  # Request N-Triples format
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'query': query
        }

        try:
            # Execute the SPARQL query
            response = requests.post(
                self.query_url,
                headers=headers,
                data=data,
                timeout=300  # 5 minute timeout for large graphs
            )

            # Check if request was successful
            response.raise_for_status()

            # Create a temporary file to store the results
            # Use delete=False so the file persists after closing
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.nt',
                prefix='ekg_edges_',
                delete=False
            )

            # Write the response content to the temporary file
            temp_file.write(response.text)
            temp_file.close()

            # Return the path to the temporary file
            return Path(temp_file.name)

        except requests.exceptions.HTTPError as e:
            # HTTP error (4xx, 5xx)
            error_msg = (
                f"SPARQL query failed with HTTP error {e.response.status_code}.\n"
                f"Endpoint: {self.query_url}\n"
                f"Response: {e.response.text}"
            )
            raise RuntimeError(error_msg) from e

        except requests.exceptions.Timeout as e:
            # Request timeout
            error_msg = (
                f"SPARQL query timed out after 300 seconds.\n"
                f"Endpoint: {self.query_url}\n"
                f"The graph may be too large for analysis."
            )
            raise RuntimeError(error_msg) from e

        except requests.exceptions.RequestException as e:
            # Other request errors (connection, etc.)
            error_msg = (
                f"Failed to execute SPARQL query.\n"
                f"Endpoint: {self.query_url}\n"
                f"Error: {str(e)}"
            )
            raise RuntimeError(error_msg) from e


def extract_edges_from_tdb(jena_home: Path, db_path: Path) -> Path:
    """
    Extract IRI-to-IRI graph edges directly from a local TDB2 database.

    This avoids routing the broad CONSTRUCT projection through Fuseki, which
    can time out on larger OEKG/EventKG-style datasets even when the same query
    finishes through Jena's local TDB query command.
    """
    if platform.system() == "Windows":
        query_cmd = jena_home / "bat" / "tdb2_tdbquery.bat"
    else:
        query_cmd = jena_home / "bin" / "tdb2.tdbquery"

    if not query_cmd.exists():
        raise FileNotFoundError(f"tdb2 query command not found at {query_cmd}")

    predicate_filter = projection_filter_sparql("?p")
    query_text = f"""
    PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
    CONSTRUCT {{
        ?s <{LINK_PREDICATE}> ?o .
        ?event <{NODE_PREDICATE}> ?event .
    }}
    WHERE {{
        {{
            ?s ?p ?o .
            FILTER(isIRI(?s) && isIRI(?o))
            {predicate_filter}
        }}
        UNION
        {{ ?event a sem:Event . }}
    }}
    """

    query_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".rq",
        prefix="ekg_edges_",
        delete=False,
        encoding="utf-8",
    )
    try:
        query_file.write(query_text)
        query_file.close()

        edge_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".nt",
            prefix="ekg_edges_",
            delete=False,
            encoding="utf-8",
        )
        edge_file.close()

        env = os.environ.copy()
        env["JENA_HOME"] = str(jena_home)
        env["JENAROOT"] = str(jena_home)

        cmd = [
            str(query_cmd),
            "--loc",
            str(db_path),
            "--query",
            query_file.name,
            "--results=N-TRIPLES",
        ]

        with open(edge_file.name, "w", encoding="utf-8") as stdout:
            result = subprocess.run(
                cmd,
                stdout=stdout,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )

        if result.returncode != 0:
            raise RuntimeError(
                "Direct TDB edge extraction failed.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error output:\n{result.stderr}"
            )

        return Path(edge_file.name)
    finally:
        try:
            Path(query_file.name).unlink(missing_ok=True)
        except Exception:
            pass


def extract_edges_from_nt_files(nt_files: Iterable[Path]) -> Path:
    """
    Extract domain-relation edges and direct event nodes from N-Triples files.

    This is equivalent to the projection:
        CONSTRUCT { ?s <urn:link> ?o . }
        WHERE { ?s ?p ?o . FILTER(isIRI(?s) && isIRI(?o)) }

    It avoids materialising the broad projection through Fuseki/Jena, which can
    be prohibitively slow on real OEKG/EventKG-scale files.
    """
    edge_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".nt",
        prefix="ekg_edges_",
        delete=False,
        encoding="utf-8",
    )

    try:
        with edge_file:
            for nt_file in nt_files:
                with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                    for line in source:
                        record = parse_iri_triple(line)
                        if not record:
                            continue
                        if record.is_direct_event_declaration:
                            edge_file.write(
                                f"<{record.subject}> <{NODE_PREDICATE}> <{record.subject}> .\n"
                            )
                        if record.is_domain_edge:
                            edge_file.write(
                                f"<{record.subject}> <{LINK_PREDICATE}> <{record.object}> .\n"
                            )
        return Path(edge_file.name)
    except Exception:
        try:
            Path(edge_file.name).unlink(missing_ok=True)
        except Exception:
            pass
        raise
