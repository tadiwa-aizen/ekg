"""Entity richness analysis for EventKG."""

from typing import Dict, Any, List
import requests
import statistics


class EntityRichnessAnalyzer:
    """Analyzes information density per entity."""

    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url
        if not endpoint_url.endswith('/sparql'):
            self.query_url = f"{endpoint_url}/sparql"
        else:
            self.query_url = endpoint_url

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

    def analyze_entity_richness(self) -> Dict[str, Any]:
        """Measure average properties/relations per entity."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?event (COUNT(?prop) AS ?propCount) WHERE {
            ?event a sem:Event .
            ?event ?prop ?value .
        } GROUP BY ?event
        """
        
        results = self._execute_query(query)
        
        if not results:
            return {
                'avg_properties_per_event': 0.0,
                'median_properties_per_event': 0.0,
                'std_dev_properties': 0.0,
                'sparse_entities_percentage': 0.0,
                'total_events_analyzed': 0
            }
        
        # Extract property counts
        prop_counts = [int(r['propCount']['value']) for r in results]
        
        # Calculate metrics
        avg_props = statistics.mean(prop_counts)
        median_props = statistics.median(prop_counts)
        std_dev = statistics.stdev(prop_counts) if len(prop_counts) > 1 else 0.0
        
        # Sparse entities: <3 properties
        sparse_count = sum(1 for c in prop_counts if c < 3)
        sparse_percentage = (sparse_count / len(prop_counts) * 100) if prop_counts else 0.0
        
        return {
            'avg_properties_per_event': round(avg_props, 2),
            'median_properties_per_event': median_props,
            'std_dev_properties': round(std_dev, 2),
            'sparse_entities_percentage': round(sparse_percentage, 2),
            'total_events_analyzed': len(prop_counts)
        }
