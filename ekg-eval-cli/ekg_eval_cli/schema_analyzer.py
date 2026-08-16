"""Schema alignment and ontology conformance analysis."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import re
from collections import Counter
from .config import EvaluationParameters


class SchemaAnalyzer:
    """Analyzes schema alignment and ontology conformance."""

    def __init__(
        self,
        endpoint_url: str,
        parameters: Optional[EvaluationParameters] = None,
        nt_files: Optional[List[Path]] = None,
    ):
        self.endpoint_url = endpoint_url
        if not endpoint_url.endswith('/sparql'):
            self.query_url = f"{endpoint_url}/sparql"
        else:
            self.query_url = endpoint_url
        
        self.parameters = parameters or EvaluationParameters()
        self.nt_files = nt_files or []

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
        
        SELECT ?event
        WHERE {
            ?event a sem:Event .
        }
        """
        results = self._execute_query(query)
        return len({r['event']['value'] for r in results if 'event' in r})

    def count_events_with_labels(self) -> int:
        """Count events with labels."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?event
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label .
        }
        """
        results = self._execute_query(query)
        return len({r['event']['value'] for r in results if 'event' in r})

    def count_events_with_dates(self) -> int:
        """Count events with at least one SEM begin or end timestamp."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?event
        WHERE {
            ?event a sem:Event .
            { ?event sem:hasBeginTimeStamp ?date }
            UNION
            { ?event sem:hasEndTimeStamp ?date }
        }
        """
        results = self._execute_query(query)
        return len({r['event']['value'] for r in results if 'event' in r})

    def count_fully_described_events(self) -> int:
        """Count events with label, date, and location."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?event
        WHERE {
            ?event a sem:Event ; rdfs:label ?label ; sem:hasPlace ?location .
            { ?event sem:hasBeginTimeStamp ?date }
            UNION
            { ?event sem:hasEndTimeStamp ?date }
        }
        """
        results = self._execute_query(query)
        return len({r['event']['value'] for r in results if 'event' in r})

    def detect_non_standard_properties(self, limit: int = 50) -> Dict[str, int]:
        """Detect properties not from standard vocabularies."""
        # Build filter from configured namespaces
        namespace_filters = ' && '.join([
            f'!STRSTARTS(STR(?p), "{ns}")'
            for ns in self.parameters.standard_namespaces
        ])
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?p
        WHERE {{
            ?event a sem:Event ;
                   ?p ?o .
            FILTER({namespace_filters})
        }}
        """
        results = self._execute_query(query)
        counts = Counter(r['p']['value'] for r in results if 'p' in r)
        return dict(counts.most_common(limit))

    def count_external_vocabulary_usage(self) -> Dict[str, int]:
        """Count events linked to external vocabularies via properties or owl:sameAs."""
        vocabs = {
            'schema.org': 'http://schema.org/',
            'dbpedia': 'http://dbpedia.org/',
            'wikidata': 'http://www.wikidata.org/'
        }
        
        counts = {}
        for name, prefix in vocabs.items():
            query = f"""
            PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
            
            SELECT ?event
            WHERE {{
                ?event a sem:Event ;
                       ?p ?o .
                FILTER(STRSTARTS(STR(?p), "{prefix}") || STRSTARTS(STR(?o), "{prefix}"))
            }}
            """
            results = self._execute_query(query)
            counts[name] = len({r['event']['value'] for r in results if 'event' in r})
        
        return counts

    def analyze_schema_conformance(self) -> Dict[str, Any]:
        """Run complete schema conformance analysis."""
        if self.nt_files:
            return self._analyze_schema_conformance_from_files()

        total_events = self.count_total_events()
        events_with_labels = self.count_events_with_labels()
        events_with_dates = self.count_events_with_dates()
        fully_described = self.count_fully_described_events()
        
        label_coverage = (events_with_labels / total_events * 100) if total_events > 0 else None
        date_coverage = (events_with_dates / total_events * 100) if total_events > 0 else None
        conformance_rate = (fully_described / total_events * 100) if total_events > 0 else None
        
        non_standard_props = self.detect_non_standard_properties()
        external_vocab_usage = self.count_external_vocabulary_usage()
        
        return {
            'total_events': total_events,
            'events_with_labels': events_with_labels,
            'events_with_dates': events_with_dates,
            'fully_described_events': fully_described,
            'label_coverage_rate': round(label_coverage, 2) if label_coverage is not None else None,
            'date_coverage_rate': round(date_coverage, 2) if date_coverage is not None else None,
            'schema_conformance_rate': round(conformance_rate, 2) if conformance_rate is not None else None,
            'status': 'computed' if total_events else 'not_applicable_no_events',
            'non_standard_properties_count': len(non_standard_props),
            'non_standard_properties_sample': dict(list(non_standard_props.items())[:10]),
            'external_vocabulary_usage': external_vocab_usage
        }

    def _analyze_schema_conformance_from_files(self) -> Dict[str, Any]:
        """Run exact profile counts from N-Triples files for large graphs."""
        triple_pattern = re.compile(r'^\s*<([^>]+)>\s+<([^>]+)>\s+(.+)\s+\.\s*$')
        rdf_type = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        sem_event = 'http://semanticweb.cs.vu.nl/2009/11/sem/Event'
        rdfs_label = 'http://www.w3.org/2000/01/rdf-schema#label'
        sem_begin = 'http://semanticweb.cs.vu.nl/2009/11/sem/hasBeginTimeStamp'
        sem_end = 'http://semanticweb.cs.vu.nl/2009/11/sem/hasEndTimeStamp'
        sem_place = 'http://semanticweb.cs.vu.nl/2009/11/sem/hasPlace'

        events = set()
        labels = set()
        dates = set()
        places = set()

        for nt_file in self.nt_files:
            with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                for line in source:
                    match = triple_pattern.match(line)
                    if not match:
                        continue
                    subject, predicate, obj = match.group(1), match.group(2), match.group(3)
                    if predicate == rdf_type and obj == f"<{sem_event}>":
                        events.add(subject)
                    elif predicate == rdfs_label:
                        labels.add(subject)
                    elif predicate in {sem_begin, sem_end}:
                        dates.add(subject)
                    elif predicate == sem_place:
                        places.add(subject)

        event_count = len(events)
        events_with_labels = len(events.intersection(labels))
        events_with_dates = len(events.intersection(dates))
        fully_described = len(events.intersection(labels, dates, places))

        non_standard_counts = Counter()
        vocabs = {
            'schema.org': 'http://schema.org/',
            'dbpedia': 'http://dbpedia.org/',
            'wikidata': 'http://www.wikidata.org/'
        }
        external_sets = {name: set() for name in vocabs}

        for nt_file in self.nt_files:
            with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                for line in source:
                    match = triple_pattern.match(line)
                    if not match:
                        continue
                    subject, predicate, obj = match.group(1), match.group(2), match.group(3)
                    if subject not in events:
                        continue
                    if not any(predicate.startswith(ns) for ns in self.parameters.standard_namespaces):
                        non_standard_counts[predicate] += 1
                    clean_obj = obj[1:].split(">", 1)[0] if obj.startswith("<") else ""
                    for name, prefix in vocabs.items():
                        if predicate.startswith(prefix) or clean_obj.startswith(prefix):
                            external_sets[name].add(subject)

        label_coverage = (events_with_labels / event_count * 100) if event_count > 0 else None
        date_coverage = (events_with_dates / event_count * 100) if event_count > 0 else None
        conformance_rate = (fully_described / event_count * 100) if event_count > 0 else None
        non_standard_props = dict(non_standard_counts.most_common(50))

        return {
            'total_events': event_count,
            'events_with_labels': events_with_labels,
            'events_with_dates': events_with_dates,
            'fully_described_events': fully_described,
            'label_coverage_rate': round(label_coverage, 2) if label_coverage is not None else None,
            'date_coverage_rate': round(date_coverage, 2) if date_coverage is not None else None,
            'schema_conformance_rate': round(conformance_rate, 2) if conformance_rate is not None else None,
            'status': 'computed' if event_count else 'not_applicable_no_events',
            'non_standard_properties_count': len(non_standard_props),
            'non_standard_properties_sample': dict(list(non_standard_props.items())[:10]),
            'external_vocabulary_usage': {
                name: len(subjects) for name, subjects in external_sets.items()
            },
            'counting_method': 'exact_file_scan'
        }
