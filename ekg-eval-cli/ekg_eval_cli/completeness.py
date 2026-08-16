"""Coverage and completeness analysis."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import re
from collections import Counter


class CompletenessAnalyzer:
    """Analyzes coverage and completeness metrics."""

    def __init__(self, endpoint_url: str, nt_files: Optional[List[Path]] = None):
        self.endpoint_url = endpoint_url
        if not endpoint_url.endswith('/sparql'):
            self.query_url = f"{endpoint_url}/sparql"
        else:
            self.query_url = endpoint_url
        self.nt_files = nt_files or []
        self._file_profile_cache: Optional[Dict[str, Any]] = None

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
        """Count the canonical direct sem:Event population."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE { ?event a sem:Event . }
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
        """Count direct events with label, temporal information, and place."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ; rdfs:label ?label ; sem:hasPlace ?place .
            { ?event sem:hasBeginTimeStamp ?date }
            UNION
            { ?event sem:hasEndTimeStamp ?date }
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
        if self.nt_files:
            return self._population_completeness_from_files()

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
            ?event a sem:Event .
            { ?event sem:hasBeginTimeStamp ?date }
            UNION
            { ?event sem:hasEndTimeStamp ?date }
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
            ?event a sem:Event ; rdfs:label ?label ; sem:hasPlace ?place .
            { ?event sem:hasBeginTimeStamp ?date }
            UNION
            { ?event sem:hasEndTimeStamp ?date }
        }
        """
        complete_results = self._execute_query(complete_query)
        fully_complete_events = int(complete_results[0]['count']['value'])
        
        # Calculate rates
        label_rate = (events_with_label / total_events * 100) if total_events > 0 else None
        temporal_rate = (events_with_temporal / total_events * 100) if total_events > 0 else None
        location_rate = (events_with_location / total_events * 100) if total_events > 0 else None
        completeness_rate = (fully_complete_events / total_events * 100) if total_events > 0 else None
        
        return {
            'total_events': total_events,
            'events_with_label': events_with_label,
            'events_with_temporal': events_with_temporal,
            'events_with_location': events_with_location,
            'fully_complete_events': fully_complete_events,
            'label_coverage_rate': round(label_rate, 2) if label_rate is not None else None,
            'temporal_coverage_rate': round(temporal_rate, 2) if temporal_rate is not None else None,
            'location_coverage_rate': round(location_rate, 2) if location_rate is not None else None,
            'population_completeness_rate': round(completeness_rate, 2) if completeness_rate is not None else None,
            'status': 'computed' if total_events else 'not_applicable_no_events',
            'event_population': 'direct sem:Event instances',
            'required_profile': [
                'rdfs:label',
                'sem:hasBeginTimeStamp or sem:hasEndTimeStamp',
                'sem:hasPlace'
            ]
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
        if self.nt_files:
            return self._analyze_completeness_from_files()

        total_events = self.count_event_instances()
        used_classes = self.count_used_event_classes()
        declared_classes = self.count_declared_event_classes()
        complete_events = self.count_complete_events()
        
        schema_coverage = (used_classes / declared_classes * 100) if declared_classes > 0 else 0.0
        population_completeness = (complete_events / total_events * 100) if total_events > 0 else None
        class_usage_efficiency = (used_classes / total_events * 100) if total_events > 0 else None
        
        class_distribution = self.get_class_usage_distribution()
        property_usage = self.get_property_usage_stats()
        
        return {
            'total_event_instances': total_events,
            'used_event_classes': used_classes,
            'declared_event_classes': declared_classes,
            'events_with_complete_data': complete_events,
            'schema_coverage_percentage': round(schema_coverage, 2),
            'population_completeness_percentage': round(population_completeness, 2) if population_completeness is not None else None,
            'class_usage_efficiency_percentage': round(class_usage_efficiency, 2) if class_usage_efficiency is not None else None,
            'status': 'computed' if total_events else 'not_applicable_no_events',
            'class_distribution_sample': dict(list(class_distribution.items())[:10]),
            'property_usage_sample': dict(list(property_usage.items())[:10]),
            'event_population': 'direct sem:Event instances',
            'required_profile': [
                'rdfs:label',
                'sem:hasBeginTimeStamp or sem:hasEndTimeStamp',
                'sem:hasPlace'
            ]
        }

    def _scan_profile_sets(self) -> Dict[str, Any]:
        if self._file_profile_cache is not None:
            return self._file_profile_cache

        triple_pattern = re.compile(r'^\s*<([^>]+)>\s+<([^>]+)>\s+(.+)\s+\.\s*$')
        rdf_type = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        rdfs_subclass = 'http://www.w3.org/2000/01/rdf-schema#subClassOf'
        owl_class = 'http://www.w3.org/2002/07/owl#Class'
        sem_event = 'http://semanticweb.cs.vu.nl/2009/11/sem/Event'
        rdfs_label = 'http://www.w3.org/2000/01/rdf-schema#label'
        sem_begin = 'http://semanticweb.cs.vu.nl/2009/11/sem/hasBeginTimeStamp'
        sem_end = 'http://semanticweb.cs.vu.nl/2009/11/sem/hasEndTimeStamp'
        sem_place = 'http://semanticweb.cs.vu.nl/2009/11/sem/hasPlace'

        subclass_edges = []
        owl_classes = set()
        for nt_file in self.nt_files:
            with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                for line in source:
                    match = triple_pattern.match(line)
                    if not match:
                        continue
                    subject, predicate, obj = match.group(1), match.group(2), match.group(3)
                    obj_iri = obj[1:].split(">", 1)[0] if obj.startswith("<") else ""
                    if predicate == rdfs_subclass and obj_iri:
                        subclass_edges.append((subject, obj_iri))
                    elif predicate == rdf_type and obj_iri == owl_class:
                        owl_classes.add(subject)

        event_classes = {sem_event}
        direct_declared_event_classes = {sem_event}
        direct_subclasses_of_sem_event = set()
        changed = True
        while changed:
            changed = False
            for child, parent in subclass_edges:
                if parent == sem_event:
                    direct_declared_event_classes.add(child)
                    direct_subclasses_of_sem_event.add(child)
                if parent in event_classes and child not in event_classes:
                    event_classes.add(child)
                    changed = True

        event_instances = set()
        direct_sem_events = set()
        used_event_classes = set()
        all_class_distribution = Counter()
        labels = set()
        dates = set()
        places = set()
        property_usage = Counter()
        for nt_file in self.nt_files:
            with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                for line in source:
                    match = triple_pattern.match(line)
                    if not match:
                        continue
                    subject, predicate, obj = match.group(1), match.group(2), match.group(3)
                    property_usage[predicate] += 1
                    if predicate == rdfs_label:
                        labels.add(subject)
                    elif predicate in {sem_begin, sem_end}:
                        dates.add(subject)
                    elif predicate == sem_place:
                        places.add(subject)
                    if predicate != rdf_type or not obj.startswith("<"):
                        continue
                    obj_iri = obj[1:].split(">", 1)[0]
                    if obj_iri in owl_classes:
                        all_class_distribution[obj_iri] += 1
                    if obj_iri in event_classes:
                        event_instances.add(subject)
                        used_event_classes.add(obj_iri)
                    if obj_iri == sem_event:
                        direct_sem_events.add(subject)

        labels.intersection_update(event_instances)
        dates.intersection_update(event_instances)
        places.intersection_update(event_instances)

        self._file_profile_cache = {
            "event_instances": event_instances,
            "direct_sem_events": direct_sem_events,
            "event_classes": event_classes,
            "used_event_classes": used_event_classes,
            "declared_event_classes": direct_declared_event_classes,
            "declared_event_class_count": len(direct_subclasses_of_sem_event) + 1,
            "labels": labels,
            "dates": dates,
            "places": places,
            "class_distribution": all_class_distribution,
            "property_usage": property_usage,
        }
        return self._file_profile_cache

    def _analyze_completeness_from_files(self) -> Dict[str, Any]:
        profile = self._scan_profile_sets()
        direct_sem_events = profile["direct_sem_events"]
        total_events = len(direct_sem_events)
        used_classes = len(profile["used_event_classes"])
        declared_classes = profile["declared_event_class_count"]
        complete_events = len(
            direct_sem_events.intersection(
                profile["labels"], profile["dates"], profile["places"]
            )
        )
        schema_coverage = (used_classes / declared_classes * 100) if declared_classes > 0 else 0.0
        population_completeness = (complete_events / total_events * 100) if total_events > 0 else None
        class_usage_efficiency = (used_classes / total_events * 100) if total_events > 0 else None

        return {
            'total_event_instances': total_events,
            'used_event_classes': used_classes,
            'declared_event_classes': declared_classes,
            'events_with_complete_data': complete_events,
            'schema_coverage_percentage': round(schema_coverage, 2),
            'population_completeness_percentage': round(population_completeness, 2) if population_completeness is not None else None,
            'class_usage_efficiency_percentage': round(class_usage_efficiency, 2) if class_usage_efficiency is not None else None,
            'status': 'computed' if total_events else 'not_applicable_no_events',
            'class_distribution_sample': dict(profile["class_distribution"].most_common(10)),
            'property_usage_sample': dict(profile["property_usage"].most_common(10)),
            'counting_method': 'exact_file_scan',
            'event_population': 'direct sem:Event instances',
            'required_profile': [
                'rdfs:label',
                'sem:hasBeginTimeStamp or sem:hasEndTimeStamp',
                'sem:hasPlace'
            ]
        }

    def _population_completeness_from_files(self) -> Dict[str, Any]:
        profile = self._scan_profile_sets()
        direct_sem_events = profile["direct_sem_events"]
        total_events = len(direct_sem_events)
        events_with_label = len(direct_sem_events.intersection(profile["labels"]))
        events_with_temporal = len(direct_sem_events.intersection(profile["dates"]))
        events_with_location = len(direct_sem_events.intersection(profile["places"]))
        fully_complete_events = len(
            direct_sem_events.intersection(profile["labels"], profile["dates"], profile["places"])
        )

        label_rate = (events_with_label / total_events * 100) if total_events > 0 else None
        temporal_rate = (events_with_temporal / total_events * 100) if total_events > 0 else None
        location_rate = (events_with_location / total_events * 100) if total_events > 0 else None
        completeness_rate = (fully_complete_events / total_events * 100) if total_events > 0 else None

        return {
            'total_events': total_events,
            'events_with_label': events_with_label,
            'events_with_temporal': events_with_temporal,
            'events_with_location': events_with_location,
            'fully_complete_events': fully_complete_events,
            'label_coverage_rate': round(label_rate, 2) if label_rate is not None else None,
            'temporal_coverage_rate': round(temporal_rate, 2) if temporal_rate is not None else None,
            'location_coverage_rate': round(location_rate, 2) if location_rate is not None else None,
            'population_completeness_rate': round(completeness_rate, 2) if completeness_rate is not None else None,
            'status': 'computed' if total_events else 'not_applicable_no_events',
            'counting_method': 'exact_file_scan',
            'event_population': 'direct sem:Event instances',
            'required_profile': [
                'rdfs:label',
                'sem:hasBeginTimeStamp or sem:hasEndTimeStamp',
                'sem:hasPlace'
            ]
        }
