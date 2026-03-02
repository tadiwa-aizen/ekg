"""Schema alignment and ontology conformance analysis."""

from typing import Dict, Any, List, Optional
import requests
from .config import EvaluationParameters


class SchemaAnalyzer:
    """Analyzes schema alignment and ontology conformance."""

    def __init__(self, endpoint_url: str, parameters: Optional[EvaluationParameters] = None):
        self.endpoint_url = endpoint_url
        if not endpoint_url.endswith('/sparql'):
            self.query_url = f"{endpoint_url}/sparql"
        else:
            self.query_url = endpoint_url
        
        self.parameters = parameters or EvaluationParameters()

    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute SPARQL query and return results."""
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(
            self.query_url,
            headers=headers,
            data={'query': query},
            timeout=300
        )
        response.raise_for_status()
        return response.json()['results']['bindings']

    def count_total_events(self) -> int:
        """Count total events."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event .
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def count_events_with_labels(self) -> int:
        """Count events with labels."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label .
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def count_events_with_dates(self) -> int:
        """Count events with temporal data."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   sem:hasBeginTimeStamp ?date .
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def count_fully_described_events(self) -> int:
        """Count events with label, date, and location."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema: <http://schema.org/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label ;
                   sem:hasBeginTimeStamp ?date .
            OPTIONAL { ?event sem:hasPlace ?location }
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def detect_non_standard_properties(self, limit: int = 50) -> Dict[str, int]:
        """Detect properties not from standard vocabularies."""
        # Build filter from configured namespaces
        namespace_filters = ' && '.join([
            f'!STRSTARTS(STR(?p), "{ns}")'
            for ns in self.parameters.standard_namespaces
        ])
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?p (COUNT(*) AS ?count)
        WHERE {{
            ?event a sem:Event ;
                   ?p ?o .
            FILTER({namespace_filters})
        }}
        GROUP BY ?p
        ORDER BY DESC(?count)
        LIMIT {limit}
        """
        results = self._execute_query(query)
        return {r['p']['value']: int(r['count']['value']) for r in results}

    def count_external_vocabulary_usage(self) -> Dict[str, int]:
        """Count usage of external vocabularies."""
        vocabs = {
            'schema.org': 'http://schema.org/',
            'dbpedia': 'http://dbpedia.org/',
            'wikidata': 'http://www.wikidata.org/'
        }
        
        counts = {}
        for name, prefix in vocabs.items():
            query = f"""
            PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
            
            SELECT (COUNT(DISTINCT ?event) AS ?count)
            WHERE {{
                ?event a sem:Event ;
                       ?p ?o .
                FILTER(STRSTARTS(STR(?p), "{prefix}"))
            }}
            """
            results = self._execute_query(query)
            counts[name] = int(results[0]['count']['value'])
        
        return counts

    def analyze_schema_conformance(self) -> Dict[str, Any]:
        """Run complete schema conformance analysis."""
        total_events = self.count_total_events()
        events_with_labels = self.count_events_with_labels()
        events_with_dates = self.count_events_with_dates()
        fully_described = self.count_fully_described_events()
        
        label_coverage = (events_with_labels / total_events * 100) if total_events > 0 else 0.0
        date_coverage = (events_with_dates / total_events * 100) if total_events > 0 else 0.0
        conformance_rate = (fully_described / total_events * 100) if total_events > 0 else 0.0
        
        non_standard_props = self.detect_non_standard_properties()
        external_vocab_usage = self.count_external_vocabulary_usage()
        
        return {
            'total_events': total_events,
            'events_with_labels': events_with_labels,
            'events_with_dates': events_with_dates,
            'fully_described_events': fully_described,
            'label_coverage_rate': round(label_coverage, 2),
            'date_coverage_rate': round(date_coverage, 2),
            'schema_conformance_rate': round(conformance_rate, 2),
            'non_standard_properties_count': len(non_standard_props),
            'non_standard_properties_sample': dict(list(non_standard_props.items())[:10]),
            'external_vocabulary_usage': external_vocab_usage
        }
