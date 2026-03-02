"""SHACL validation for EventKG schema conformance."""

from typing import Dict, Any, Optional
from pathlib import Path

try:
    from pyshacl import validate
    from rdflib import Graph
    PYSHACL_AVAILABLE = True
except ImportError:
    PYSHACL_AVAILABLE = False
    Graph = None  # Type hint placeholder


class SHACLValidator:
    """Validates EventKG data against SHACL shapes."""
    
    # EventKG SHACL shapes
    EVENTKG_SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix sem: <http://semanticweb.cs.vu.nl/2009/11/sem/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ekgs: <https://eventkg.l3s.uni-hannover.de/schema/> .

# Event must have at least one label
:EventLabelShape a sh:NodeShape ;
    sh:targetClass sem:Event ;
    sh:property [
        sh:path rdfs:label ;
        sh:minCount 1 ;
        sh:message "Event must have at least one rdfs:label" ;
    ] .

# Event must have temporal data
:EventTemporalShape a sh:NodeShape ;
    sh:targetClass sem:Event ;
    sh:property [
        sh:path sem:hasBeginTimeStamp ;
        sh:minCount 1 ;
        sh:datatype xsd:date ;
        sh:message "Event must have sem:hasBeginTimeStamp with xsd:date datatype" ;
    ] .

# If event has end date, it must be xsd:date
:EventEndDateShape a sh:NodeShape ;
    sh:targetClass sem:Event ;
    sh:property [
        sh:path sem:hasEndTimeStamp ;
        sh:datatype xsd:date ;
        sh:message "Event end date must be xsd:date datatype" ;
    ] .

# Relation must have subject and object
:RelationShape a sh:NodeShape ;
    sh:targetClass ekgs:Relation ;
    sh:property [
        sh:path <http://www.w3.org/1999/02/22-rdf-syntax-ns#subject> ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:message "Relation must have exactly one rdf:subject" ;
    ] ;
    sh:property [
        sh:path <http://www.w3.org/1999/02/22-rdf-syntax-ns#object> ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:message "Relation must have exactly one rdf:object" ;
    ] ;
    sh:property [
        sh:path sem:roleType ;
        sh:minCount 1 ;
        sh:message "Relation must have sem:roleType" ;
    ] .

# Actor must have label
:ActorLabelShape a sh:NodeShape ;
    sh:targetClass sem:Actor ;
    sh:property [
        sh:path rdfs:label ;
        sh:minCount 1 ;
        sh:message "Actor must have at least one rdfs:label" ;
    ] .
"""
    
    def __init__(self, data_graph_path: Optional[Path] = None):
        """
        Initialize SHACL validator.
        
        Args:
            data_graph_path: Path to RDF data file (optional, can load later)
        """
        if not PYSHACL_AVAILABLE:
            raise ImportError(
                "pyshacl is not installed. Install with: pip install pyshacl"
            )
        
        self.shapes_graph = Graph()
        self.shapes_graph.parse(data=self.EVENTKG_SHAPES, format='turtle')
        
        self.data_graph = None
        if data_graph_path:
            self.load_data_graph(data_graph_path)
    
    def load_data_graph(self, path: Path):
        """Load RDF data graph from file."""
        self.data_graph = Graph()
        self.data_graph.parse(str(path), format='nt')
    
    def validate(self, data_graph: Optional[Graph] = None) -> Dict[str, Any]:
        """
        Run SHACL validation.
        
        Args:
            data_graph: RDF graph to validate (uses loaded graph if None)
        
        Returns:
            Dictionary with validation results
        """
        if data_graph is None:
            data_graph = self.data_graph
        
        if data_graph is None:
            raise ValueError("No data graph provided or loaded")
        
        # Run validation
        conforms, results_graph, results_text = validate(
            data_graph=data_graph,
            shacl_graph=self.shapes_graph,
            inference='rdfs',
            abort_on_first=False
        )
        
        # Parse results
        violations = self._parse_violations(results_graph)
        
        return {
            'conforms': conforms,
            'total_violations': len(violations),
            'violations_by_shape': self._group_violations(violations),
            'conformance_rate': self._calculate_conformance_rate(violations, data_graph),
            'violations': violations[:20]  # First 20 examples
        }
    
    def _parse_violations(self, results_graph: Graph) -> list:
        """Parse SHACL validation results."""
        violations = []
        
        query = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        
        SELECT ?focusNode ?resultPath ?message ?value
        WHERE {
            ?result a sh:ValidationResult ;
                    sh:focusNode ?focusNode ;
                    sh:resultMessage ?message .
            OPTIONAL { ?result sh:resultPath ?resultPath }
            OPTIONAL { ?result sh:value ?value }
        }
        """
        
        for row in results_graph.query(query):
            violations.append({
                'focus_node': str(row.focusNode),
                'path': str(row.resultPath) if row.resultPath else None,
                'message': str(row.message),
                'value': str(row.value) if row.value else None
            })
        
        return violations
    
    def _group_violations(self, violations: list) -> Dict[str, int]:
        """Group violations by message type."""
        groups = {}
        for v in violations:
            msg = v['message']
            groups[msg] = groups.get(msg, 0) + 1
        return groups
    
    def _calculate_conformance_rate(self, violations: list, data_graph: Graph) -> float:
        """Calculate overall conformance rate."""
        # Count total focus nodes
        focus_nodes = set(v['focus_node'] for v in violations)
        
        # Count total events + relations + actors
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX ekgs: <https://eventkg.l3s.uni-hannover.de/schema/>
        
        SELECT (COUNT(DISTINCT ?node) AS ?count)
        WHERE {
            {
                ?node a sem:Event .
            } UNION {
                ?node a ekgs:Relation .
            } UNION {
                ?node a sem:Actor .
            }
        }
        """
        
        result = list(data_graph.query(query))
        total_nodes = int(result[0][0]) if result else 0
        
        if total_nodes == 0:
            return 100.0
        
        conforming_nodes = total_nodes - len(focus_nodes)
        return round((conforming_nodes / total_nodes) * 100, 2)
