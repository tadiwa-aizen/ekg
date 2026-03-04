"""Type and role consistency analysis."""

from typing import Dict, Any, List, Tuple, Optional
import requests
from .config import EvaluationParameters


class TypeConsistencyAnalyzer:
    """Analyzes type and role consistency."""

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

    def extract_property_domains_ranges(self) -> List[Tuple[str, str, str]]:
        """Extract property domain and range definitions from schema."""
        query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?property ?domain ?range
        WHERE {
            ?property rdfs:domain ?domain .
            OPTIONAL { ?property rdfs:range ?range }
        }
        """
        results = self._execute_query(query)
        return [
            (
                r['property']['value'],
                r.get('domain', {}).get('value', ''),
                r.get('range', {}).get('value', '')
            )
            for r in results
        ]

    def check_domain_violations(self, property_uri: str, expected_domain: str) -> Tuple[int, int]:
        """
        Check domain violations for a property with RDFS inference.
        
        Uses SPARQL property paths (rdfs:subClassOf*) for subclass inference.
        """
        # Count total usage
        total_query = f"""
        SELECT (COUNT(*) AS ?count)
        WHERE {{
            ?s <{property_uri}> ?o .
        }}
        """
        total_results = self._execute_query(total_query)
        total = int(total_results[0]['count']['value'])
        
        if total == 0:
            return 0, 0
        
        # Count violations with subclass inference
        violation_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT (COUNT(*) AS ?count)
        WHERE {{
            ?s <{property_uri}> ?o .
            FILTER NOT EXISTS {{
                ?s a ?type .
                ?type rdfs:subClassOf* <{expected_domain}> .
            }}
        }}
        """
        violation_results = self._execute_query(violation_query)
        violations = int(violation_results[0]['count']['value'])
        
        return total, violations

    def check_range_violations_datatype(self, property_uri: str, expected_datatype: str) -> Tuple[int, int]:
        """Check range violations for datatype properties."""
        total_query = f"""
        SELECT (COUNT(*) AS ?count)
        WHERE {{
            ?s <{property_uri}> ?o .
        }}
        """
        total_results = self._execute_query(total_query)
        total = int(total_results[0]['count']['value'])
        
        if total == 0:
            return 0, 0
        
        violation_query = f"""
        SELECT (COUNT(*) AS ?count)
        WHERE {{
            ?s <{property_uri}> ?o .
            FILTER(DATATYPE(?o) != <{expected_datatype}>)
        }}
        """
        violation_results = self._execute_query(violation_query)
        violations = int(violation_results[0]['count']['value'])
        
        return total, violations

    def analyze_type_consistency(self) -> Dict[str, Any]:
        """Run complete type consistency analysis with configurable limit."""
        # Get property definitions
        property_defs = self.extract_property_domains_ranges()
        
        if not property_defs:
            return {
                'properties_analyzed': 0,
                'properties_with_violations': 0,
                'average_domain_conformity': 100.0,
                'average_range_conformity': 100.0,
                'overall_type_consistency': 100.0,
                'property_details': [],
                'inference_enabled': True
            }
        
        # Limit to configured maximum
        max_props = self.parameters.max_properties_analyzed
        property_defs = property_defs[:max_props]
        
        property_results = []
        total_domain_conformity = 0
        total_range_conformity = 0
        domain_checked_count = 0
        range_checked_count = 0
        properties_with_violations = 0
        
        for prop_uri, domain, range_val in property_defs:
            result = {
                'property': prop_uri,
                'domain': domain,
                'range': range_val
            }
            
            # Check domain with inference
            if domain:
                total, violations = self.check_domain_violations(prop_uri, domain)
                if total > 0:
                    domain_conformity = ((total - violations) / total * 100)
                    result['domain_conformity'] = round(domain_conformity, 2)
                    result['domain_violations'] = violations
                    result['domain_total'] = total
                    total_domain_conformity += domain_conformity
                    domain_checked_count += 1
                    if violations > 0:
                        properties_with_violations += 1
            
            # Check range (simplified - only for XSD datatypes)
            if range_val and 'XMLSchema' in range_val:
                total, violations = self.check_range_violations_datatype(prop_uri, range_val)
                if total > 0:
                    range_conformity = ((total - violations) / total * 100)
                    result['range_conformity'] = round(range_conformity, 2)
                    result['range_violations'] = violations
                    result['range_total'] = total
                    total_range_conformity += range_conformity
                    range_checked_count += 1
            
            property_results.append(result)
        
        avg_domain = (total_domain_conformity / domain_checked_count) if domain_checked_count > 0 else 100.0
        avg_range = (total_range_conformity / range_checked_count) if range_checked_count > 0 else 100.0
        overall = (avg_domain + avg_range) / 2
        
        return {
            'properties_analyzed': len(property_results),
            'properties_with_violations': properties_with_violations,
            'average_domain_conformity': round(avg_domain, 2),
            'average_range_conformity': round(avg_range, 2),
            'overall_type_consistency': round(overall, 2),
            'property_details': property_results,
            'inference_enabled': True,
            'max_properties_configured': self.parameters.max_properties_analyzed
        }
