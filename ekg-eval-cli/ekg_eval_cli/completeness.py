"""Coverage and completeness analysis."""

from typing import Dict, Any, List
import requests


class CompletenessAnalyzer:
    """Analyzes coverage and completeness metrics."""

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

    def count_event_instances(self) -> int:
        """Count total event instances."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a ?eventClass .
            ?eventClass rdfs:subClassOf* sem:Event .
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def count_used_event_classes(self) -> int:
        """Count distinct event classes actually used."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?eventClass) AS ?count)
        WHERE {
            ?event a ?eventClass .
            ?eventClass rdfs:subClassOf* sem:Event .
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def count_declared_event_classes(self) -> int:
        """Count declared event classes in schema."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?eventClass) AS ?count)
        WHERE {
            ?eventClass rdfs:subClassOf sem:Event .
        }
        """
        results = self._execute_query(query)
        # Add 1 for sem:Event itself
        return int(results[0]['count']['value']) + 1

    def count_complete_events(self) -> int:
        """Count events with complete minimal data."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label ;
                   sem:hasBeginTimeStamp ?date .
        }
        """
        results = self._execute_query(query)
        return int(results[0]['count']['value'])

    def analyze_population_completeness(self) -> Dict[str, Any]:
        """
        Analyze formal population completeness.
        
        Measures what percentage of events have all required properties
        for a "complete" event record.
        """
        # Count total events
        total_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event .
        }
        """
        total_results = self._execute_query(total_query)
        total_events = int(total_results[0]['count']['value'])
        
        # Count events with label
        label_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label .
        }
        """
        label_results = self._execute_query(label_query)
        events_with_label = int(label_results[0]['count']['value'])
        
        # Count events with temporal data
        temporal_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   sem:hasBeginTimeStamp ?date .
        }
        """
        temporal_results = self._execute_query(temporal_query)
        events_with_temporal = int(temporal_results[0]['count']['value'])
        
        # Count events with location
        location_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   sem:hasPlace ?place .
        }
        """
        location_results = self._execute_query(location_query)
        events_with_location = int(location_results[0]['count']['value'])
        
        # Count fully complete events (label + temporal + location)
        complete_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label ;
                   sem:hasBeginTimeStamp ?date ;
                   sem:hasPlace ?place .
        }
        """
        complete_results = self._execute_query(complete_query)
        fully_complete_events = int(complete_results[0]['count']['value'])
        
        # Calculate rates
        label_rate = (events_with_label / total_events * 100) if total_events > 0 else 0.0
        temporal_rate = (events_with_temporal / total_events * 100) if total_events > 0 else 0.0
        location_rate = (events_with_location / total_events * 100) if total_events > 0 else 0.0
        completeness_rate = (fully_complete_events / total_events * 100) if total_events > 0 else 0.0
        
        return {
            'total_events': total_events,
            'events_with_label': events_with_label,
            'events_with_temporal': events_with_temporal,
            'events_with_location': events_with_location,
            'fully_complete_events': fully_complete_events,
            'label_coverage_rate': round(label_rate, 2),
            'temporal_coverage_rate': round(temporal_rate, 2),
            'location_coverage_rate': round(location_rate, 2),
            'population_completeness_rate': round(completeness_rate, 2)
        }

    def get_class_usage_distribution(self, limit: int = 20) -> Dict[str, int]:
        """Get distribution of event instances across classes."""
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?class (COUNT(?event) AS ?count)
        WHERE {{
            ?event a ?class .
            ?class a <http://www.w3.org/2002/07/owl#Class> .
        }}
        GROUP BY ?class
        ORDER BY DESC(?count)
        LIMIT {limit}
        """
        results = self._execute_query(query)
        return {r['class']['value']: int(r['count']['value']) for r in results}

    def get_property_usage_stats(self, limit: int = 30) -> Dict[str, int]:
        """Get property usage statistics."""
        query = f"""
        SELECT ?property (COUNT(*) AS ?count)
        WHERE {{
            ?s ?property ?o .
        }}
        GROUP BY ?property
        ORDER BY DESC(?count)
        LIMIT {limit}
        """
        results = self._execute_query(query)
        return {r['property']['value']: int(r['count']['value']) for r in results}

    def analyze_completeness(self) -> Dict[str, Any]:
        """Run complete coverage and completeness analysis."""
        total_events = self.count_event_instances()
        used_classes = self.count_used_event_classes()
        declared_classes = self.count_declared_event_classes()
        complete_events = self.count_complete_events()
        
        schema_coverage = (used_classes / declared_classes * 100) if declared_classes > 0 else 0.0
        population_completeness = (complete_events / total_events * 100) if total_events > 0 else 0.0
        class_usage_efficiency = (used_classes / total_events * 100) if total_events > 0 else 0.0
        
        class_distribution = self.get_class_usage_distribution()
        property_usage = self.get_property_usage_stats()
        
        return {
            'total_event_instances': total_events,
            'used_event_classes': used_classes,
            'declared_event_classes': declared_classes,
            'events_with_complete_data': complete_events,
            'schema_coverage_percentage': round(schema_coverage, 2),
            'population_completeness_percentage': round(population_completeness, 2),
            'class_usage_efficiency_percentage': round(class_usage_efficiency, 2),
            'class_distribution_sample': dict(list(class_distribution.items())[:10]),
            'property_usage_sample': dict(list(property_usage.items())[:10])
        }
