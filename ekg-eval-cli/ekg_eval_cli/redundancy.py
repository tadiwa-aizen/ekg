"""Redundancy and duplication detection for EventKG."""

from typing import Dict, Any, List, Tuple, Optional
import requests
from rapidfuzz import fuzz
import re
from .label_normalizer import LabelNormalizer
from .config import EvaluationParameters

try:
    from datasketch import MinHash, MinHashLSH
    DATASKETCH_AVAILABLE = True
except ImportError:
    DATASKETCH_AVAILABLE = False


class RedundancyAnalyzer:
    """Analyzes event duplication and redundancy."""

    def __init__(self, endpoint_url: str, parameters: Optional[EvaluationParameters] = None):
        """
        Initialize RedundancyAnalyzer.

        Args:
            endpoint_url: URL of the SPARQL endpoint
            parameters: Evaluation parameters (uses defaults if None)
        """
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

    def detect_exact_label_duplicates(self) -> Dict[str, Any]:
        """
        Detect events with identical English labels after normalization.
        
        Uses industry-standard normalization:
        - Unicode normalization (NFKD)
        - Case folding
        - Diacritic removal
        - Punctuation removal
        - Whitespace normalization
        """
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?event ?label
        WHERE {
            ?event a sem:Event ;
                   rdfs:label ?label .
            FILTER(lang(?label) = "en")
        }
        """
        
        results = self._execute_query(query)
        
        # Group by normalized label
        normalized_groups = {}
        for r in results:
            event = r['event']['value']
            label = r['label']['value']
            normalized = LabelNormalizer.normalize(label)
            
            if normalized not in normalized_groups:
                normalized_groups[normalized] = []
            normalized_groups[normalized].append((event, label))
        
        # Count duplicates (groups with >1 event)
        duplicates = {k: v for k, v in normalized_groups.items() if len(v) > 1}
        
        duplicate_labels = len(duplicates)
        total_duplicate_events = sum(len(v) for v in duplicates.values())
        
        return {
            'duplicate_label_count': duplicate_labels,
            'total_duplicate_events': total_duplicate_events,
            'normalization_applied': True
        }

    def detect_owl_sameas_duplicates(self) -> Dict[str, Any]:
        """Detect events sharing owl:sameAs links."""
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?uri (COUNT(DISTINCT ?event) AS ?count)
        WHERE {
            ?event a sem:Event ;
                   owl:sameAs ?uri .
        }
        GROUP BY ?uri
        HAVING (COUNT(DISTINCT ?event) > 1)
        """
        
        results = self._execute_query(query)
        sameas_duplicates = len(results)
        total_sameas_events = sum(int(r['count']['value']) for r in results)
        
        return {
            'sameas_duplicate_count': sameas_duplicates,
            'total_sameas_duplicate_events': total_sameas_events
        }

    def detect_fuzzy_duplicates_lsh(self, threshold: float = None, sample_size: int = None) -> Dict[str, Any]:
        """
        Detect near-duplicate events using LSH (Locality-Sensitive Hashing) for scalability.
        
        Falls back to naive fuzzy matching if datasketch is not available.
        
        Args:
            threshold: Similarity threshold (0.0-1.0), uses config default if None
            sample_size: Number of events to sample, uses config default if None
        """
        if threshold is None:
            threshold = self.parameters.fuzzy_similarity_threshold
        if sample_size is None:
            sample_size = self.parameters.fuzzy_sample_size
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?event ?label
        WHERE {{
            ?event a sem:Event ;
                   rdfs:label ?label .
            FILTER(lang(?label) = "en")
        }}
        LIMIT {sample_size}
        """
        
        results = self._execute_query(query)
        
        if not DATASKETCH_AVAILABLE:
            # Fallback to naive fuzzy matching
            return self._fuzzy_duplicates_naive(results, int(threshold * 100))
        
        # Use LSH for scalable candidate generation
        lsh = MinHashLSH(threshold=threshold, num_perm=128)
        minhashes = {}
        events = []
        
        for r in results:
            event = r['event']['value']
            label = r['label']['value']
            clean_label = LabelNormalizer.normalize(label)
            
            # Create MinHash signature
            m = MinHash(num_perm=128)
            for word in clean_label.split():
                if word:  # Skip empty strings
                    m.update(word.encode('utf8'))
            
            minhashes[event] = m
            events.append((event, clean_label))
            lsh.insert(event, m)
        
        # Find candidate pairs using LSH
        candidate_pairs = set()
        for event, _ in events:
            candidates = lsh.query(minhashes[event])
            for candidate in candidates:
                if candidate != event:
                    pair = tuple(sorted([event, candidate]))
                    candidate_pairs.add(pair)
        
        # Verify candidates with actual similarity
        verified_pairs = []
        for event1, event2 in candidate_pairs:
            label1 = next(l for e, l in events if e == event1)
            label2 = next(l for e, l in events if e == event2)
            score = fuzz.token_sort_ratio(label1, label2)
            if score >= threshold * 100:
                verified_pairs.append((event1, event2, score))
        
        return {
            'fuzzy_duplicate_pairs': len(verified_pairs),
            'candidate_pairs_generated': len(candidate_pairs),
            'sample_size': len(events),
            'threshold': threshold,
            'method': 'LSH' if DATASKETCH_AVAILABLE else 'naive',
            'pairs': verified_pairs[:10]  # First 10 examples
        }
    
    def _fuzzy_duplicates_naive(self, results: List[Dict], threshold: int) -> Dict[str, Any]:
        """Naive O(n^2) fuzzy matching fallback."""
        events = []
        for r in results:
            event = r['event']['value']
            label = r['label']['value']
            clean_label = LabelNormalizer.normalize(label)
            events.append((event, clean_label))
        
        fuzzy_pairs = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                score = fuzz.token_sort_ratio(events[i][1], events[j][1])
                if score >= threshold:
                    fuzzy_pairs.append((events[i][0], events[j][0], score))
        
        return {
            'fuzzy_duplicate_pairs': len(fuzzy_pairs),
            'candidate_pairs_generated': len(events) * (len(events) - 1) // 2,
            'sample_size': len(events),
            'threshold': threshold / 100.0,
            'method': 'naive',
            'pairs': fuzzy_pairs[:10]
        }

    def detect_fuzzy_duplicates(self, threshold: int = None, sample_size: int = None) -> Dict[str, Any]:
        """
        Detect near-duplicate events using fuzzy string matching.
        
        Args:
            threshold: Similarity threshold (0-100), uses config default if None
            sample_size: Number of events to sample, uses config default if None
        """
        if threshold is None:
            threshold = int(self.parameters.fuzzy_similarity_threshold * 100)
        if sample_size is None:
            sample_size = self.parameters.fuzzy_sample_size
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?event ?label
        WHERE {{
            ?event a sem:Event ;
                   rdfs:label ?label .
            FILTER(lang(?label) = "en")
        }}
        LIMIT {sample_size}
        """
        
        results = self._execute_query(query)
        
        # Preprocess labels with normalization
        events = []
        for r in results:
            event = r['event']['value']
            label = r['label']['value']
            clean_label = LabelNormalizer.normalize(label)
            events.append((event, clean_label))
        
        # Find fuzzy duplicates
        fuzzy_pairs = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                score = fuzz.token_sort_ratio(events[i][1], events[j][1])
                if score >= threshold:
                    fuzzy_pairs.append((events[i][0], events[j][0], score))
        
        return {
            'fuzzy_duplicate_pairs': len(fuzzy_pairs),
            'sample_size': len(events),
            'threshold': threshold,
            'threshold_configured': self.parameters.fuzzy_similarity_threshold
        }

    def analyze_label_quality(self, sample_size: int = 5000) -> Dict[str, Any]:
        """
        Analyze label quality including uniqueness and high-similarity duplicates.
        
        Args:
            sample_size: Number of labels to sample for analysis
        """
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?event ?label WHERE {{
            ?event a sem:Event ;
                   rdfs:label ?label .
            FILTER(lang(?label) = "en")
        }} LIMIT {sample_size}
        """
        
        results = self._execute_query(query)
        
        if not results:
            return {
                'total_labels_sampled': 0,
                'unique_labels': 0,
                'label_uniqueness_rate': 0.0,
                'fuzzy_duplicates_90': 0
            }
        
        # Extract labels
        labels = [r['label']['value'] for r in results]
        unique_labels = len(set(labels))
        total_labels = len(labels)
        
        # Label uniqueness rate
        uniqueness_rate = (unique_labels / total_labels * 100) if total_labels > 0 else 0.0
        
        # Find fuzzy duplicates at 90% threshold
        clean_labels = [re.sub(r'[^\w\s]', '', label.lower()).strip() for label in labels]
        fuzzy_90_count = 0
        
        # Sample-based fuzzy matching (to avoid O(n²) on large datasets)
        sample_limit = min(1000, len(clean_labels))
        for i in range(sample_limit):
            for j in range(i + 1, sample_limit):
                score = fuzz.token_sort_ratio(clean_labels[i], clean_labels[j])
                if score >= 90:
                    fuzzy_90_count += 1
        
        return {
            'total_labels_sampled': total_labels,
            'unique_labels': unique_labels,
            'label_uniqueness_rate': round(uniqueness_rate, 2),
            'fuzzy_duplicates_90': fuzzy_90_count
        }

    def calculate_total_events(self) -> int:
        """Get total count of events."""
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?total)
        WHERE {
            ?event a sem:Event .
        }
        """
        
        results = self._execute_query(query)
        return int(results[0]['total']['value'])

    def analyze_redundancy(self) -> Dict[str, Any]:
        """Run complete redundancy analysis."""
        total_events = self.calculate_total_events()
        
        exact_dups = self.detect_exact_label_duplicates()
        sameas_dups = self.detect_owl_sameas_duplicates()
        
        # Use LSH if available, otherwise fallback to naive
        try:
            fuzzy_dups = self.detect_fuzzy_duplicates_lsh()
        except Exception as e:
            self._log(f"LSH fuzzy matching failed, using naive: {e}")
            fuzzy_dups = self.detect_fuzzy_duplicates()
        
        label_quality = self.analyze_label_quality()
        
        # Calculate duplication rate
        unique_duplicate_events = exact_dups['total_duplicate_events']
        duplication_rate = (unique_duplicate_events / total_events * 100) if total_events > 0 else 0.0
        
        return {
            'total_events': total_events,
            'exact_label_duplicates': exact_dups['duplicate_label_count'],
            'exact_duplicate_events': exact_dups['total_duplicate_events'],
            'sameas_duplicates': sameas_dups['sameas_duplicate_count'],
            'sameas_duplicate_events': sameas_dups['total_sameas_duplicate_events'],
            'fuzzy_duplicate_pairs': fuzzy_dups['fuzzy_duplicate_pairs'],
            'fuzzy_sample_size': fuzzy_dups['sample_size'],
            'fuzzy_method': fuzzy_dups.get('method', 'naive'),
            'duplication_rate': round(duplication_rate, 2),
            'label_quality': label_quality
        }
    
    def _log(self, message: str):
        """Log message (placeholder for orchestrator logging)."""
        pass
