"""Predicate usage pattern analysis for EventKG."""

from typing import Dict, Any, List
import requests
import math


class PredicateUsageAnalyzer:
    """Analyzes predicate usage patterns and distribution."""

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

    def _calculate_gini(self, values: List[int]) -> float:
        """
        Calculate Gini coefficient from values.
        
        Gini coefficient measures inequality in distribution:
        - 0.0 = perfect equality (all predicates used equally)
        - 1.0 = perfect inequality (one predicate dominates)
        
        Args:
            values: List of usage counts
            
        Returns:
            Gini coefficient (0.0 to 1.0)
        """
        if not values or len(values) == 0:
            return 0.0
        
        n = len(values)
        sorted_vals = sorted(values)
        
        # Calculate cumulative sum weighted by position
        cumsum = 0
        for i, val in enumerate(sorted_vals):
            cumsum += (i + 1) * val
        
        total_sum = sum(sorted_vals)
        if total_sum == 0:
            return 0.0
        
        # Gini formula
        gini = (2 * cumsum) / (n * total_sum) - (n + 1) / n
        return gini

    def analyze_predicate_usage(self) -> Dict[str, Any]:
        """Measure predicate usage patterns."""
        query = """
        SELECT ?predicate (COUNT(*) AS ?usage) WHERE {
            ?s ?predicate ?o .
        } GROUP BY ?predicate ORDER BY DESC(?usage)
        """
        
        results = self._execute_query(query)
        
        if not results:
            return {
                'total_unique_predicates': 0,
                'total_triples': 0,
                'top_10_concentration': 0.0,
                'singleton_predicates': 0,
                'gini_coefficient': 0.0,
                'shannon_entropy': 0.0,
                'normalized_shannon_entropy': None,
                'hhi_concentration': None,
                'status': 'not_applicable_no_predicates'
            }
        
        # Extract predicate usage counts
        usage_counts = [int(r['usage']['value']) for r in results]
        total_triples = sum(usage_counts)
        total_predicates = len(usage_counts)
        
        # Top-10 concentration
        top_10_count = sum(usage_counts[:10]) if len(usage_counts) >= 10 else sum(usage_counts)
        top_10_concentration = (top_10_count / total_triples * 100) if total_triples > 0 else 0.0
        
        # Singleton predicates (used only once)
        singleton_predicates = sum(1 for count in usage_counts if count == 1)
        
        # Gini coefficient
        gini = self._calculate_gini(usage_counts)

        # Predicate diversity/concentration diagnostics.
        probabilities = [count / total_triples for count in usage_counts if total_triples > 0]
        shannon_entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
        normalized_entropy = (
            shannon_entropy / math.log2(total_predicates)
            if total_predicates > 1 else None
        )
        hhi = sum(p ** 2 for p in probabilities)
        
        return {
            'total_unique_predicates': total_predicates,
            'total_triples': total_triples,
            'top_10_concentration': round(top_10_concentration, 2),
            'singleton_predicates': singleton_predicates,
            'gini_coefficient': round(gini, 4),
            'shannon_entropy': round(shannon_entropy, 4),
            'normalized_shannon_entropy': round(normalized_entropy, 4) if normalized_entropy is not None else None,
            'hhi_concentration': round(hhi, 4),
            'status': 'computed'
        }
