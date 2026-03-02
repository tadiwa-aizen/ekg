"""External mapping coverage analysis for EventKG."""

from typing import Dict, Any, List
import requests


class MappingCoverageAnalyzer:
    """Analyzes external entity mapping coverage."""

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

    def analyze_mapping_coverage(self) -> Dict[str, Any]:
        """Measure how well EventKG entities link to external sources."""
        # Total events
        total_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(?e) AS ?count) WHERE { 
            ?e a sem:Event 
        }
        """
        
        # Events with owl:sameAs
        sameas_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT (COUNT(DISTINCT ?e) AS ?count) WHERE { 
            ?e a sem:Event ; 
               owl:sameAs ?ext 
        }
        """
        
        # Events linked to Wikidata
        wikidata_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT (COUNT(DISTINCT ?e) AS ?count) WHERE { 
            ?e a sem:Event ;
               owl:sameAs ?wd 
            FILTER(CONTAINS(STR(?wd), "wikidata"))
        }
        """
        
        # Events linked to DBpedia
        dbpedia_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT (COUNT(DISTINCT ?e) AS ?count) WHERE { 
            ?e a sem:Event ;
               owl:sameAs ?db 
            FILTER(CONTAINS(STR(?db), "dbpedia"))
        }
        """
        
        # Execute queries
        total_results = self._execute_query(total_query)
        sameas_results = self._execute_query(sameas_query)
        wikidata_results = self._execute_query(wikidata_query)
        dbpedia_results = self._execute_query(dbpedia_query)
        
        # Extract counts
        total_events = int(total_results[0]['count']['value'])
        sameas_events = int(sameas_results[0]['count']['value'])
        wikidata_events = int(wikidata_results[0]['count']['value'])
        dbpedia_events = int(dbpedia_results[0]['count']['value'])
        
        # Calculate percentages
        external_link_rate = (sameas_events / total_events * 100) if total_events > 0 else 0.0
        wikidata_coverage = (wikidata_events / total_events * 100) if total_events > 0 else 0.0
        dbpedia_coverage = (dbpedia_events / total_events * 100) if total_events > 0 else 0.0
        
        return {
            'total_events': total_events,
            'events_with_external_links': sameas_events,
            'events_linked_to_wikidata': wikidata_events,
            'events_linked_to_dbpedia': dbpedia_events,
            'external_link_rate': round(external_link_rate, 2),
            'wikidata_coverage': round(wikidata_coverage, 2),
            'dbpedia_coverage': round(dbpedia_coverage, 2)
        }
