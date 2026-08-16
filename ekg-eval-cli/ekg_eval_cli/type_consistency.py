"""Closed-profile domain and range consistency analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import requests

from .config import EvaluationParameters


XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema#"
RDFS_RESOURCE = "http://www.w3.org/2000/01/rdf-schema#Resource"
RDFS_LITERAL = "http://www.w3.org/2000/01/rdf-schema#Literal"


class TypeConsistencyAnalyzer:
    """Check used triples against explicitly declared RDFS domain/range profiles."""

    def __init__(
        self, endpoint_url: str, parameters: Optional[EvaluationParameters] = None
    ):
        self.endpoint_url = endpoint_url
        self.query_url = (
            endpoint_url if endpoint_url.endswith("/sparql") else f"{endpoint_url}/sparql"
        )
        self.parameters = parameters or EvaluationParameters()

    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        headers = {
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(
            self.query_url, headers=headers, data={"query": query}, timeout=300
        )
        response.raise_for_status()
        return response.json()["results"]["bindings"]

    def extract_property_domains_ranges(self) -> List[Tuple[str, str, str]]:
        query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?property ?domain ?range
        WHERE {
            {
                SELECT DISTINCT ?property WHERE {
                    { ?property rdfs:domain ?anyDomain }
                    UNION
                    { ?property rdfs:range ?anyRange }
                }
            }
            OPTIONAL { ?property rdfs:domain ?domain }
            OPTIONAL { ?property rdfs:range ?range }
        }
        ORDER BY STR(?property) STR(?domain) STR(?range)
        """
        return [
            (
                row["property"]["value"],
                row.get("domain", {}).get("value", ""),
                row.get("range", {}).get("value", ""),
            )
            for row in self._execute_query(query)
        ]

    def _count(self, query: str) -> int:
        rows = self._execute_query(query)
        return int(rows[0]["count"]["value"]) if rows else 0

    def check_domain_violations(
        self, property_uri: str, expected_domain: str
    ) -> Tuple[int, int]:
        total = self._count(
            f"SELECT (COUNT(*) AS ?count) WHERE {{ ?s <{property_uri}> ?o . }}"
        )
        if not total:
            return 0, 0
        if expected_domain == RDFS_RESOURCE:
            return total, 0
        violations = self._count(
            f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT (COUNT(*) AS ?count) WHERE {{
                ?s <{property_uri}> ?o .
                FILTER NOT EXISTS {{
                    ?s a ?type .
                    ?type rdfs:subClassOf* <{expected_domain}> .
                }}
            }}
            """
        )
        return total, violations

    def check_range_violations_datatype(
        self, property_uri: str, expected_datatype: str
    ) -> Tuple[int, int]:
        total = self._count(
            f"SELECT (COUNT(*) AS ?count) WHERE {{ ?s <{property_uri}> ?o . }}"
        )
        if not total:
            return 0, 0
        violations = self._count(
            f"""
            SELECT (COUNT(*) AS ?count) WHERE {{
                ?s <{property_uri}> ?o .
                FILTER(!isLiteral(?o) || DATATYPE(?o) != <{expected_datatype}>)
            }}
            """
        )
        return total, violations

    def check_range_violations_class(
        self, property_uri: str, expected_class: str
    ) -> Tuple[int, int]:
        total = self._count(
            f"SELECT (COUNT(*) AS ?count) WHERE {{ ?s <{property_uri}> ?o . }}"
        )
        if not total:
            return 0, 0
        if expected_class == RDFS_RESOURCE:
            return total, 0
        if expected_class == RDFS_LITERAL:
            violations = self._count(
                f"""
                SELECT (COUNT(*) AS ?count) WHERE {{
                    ?s <{property_uri}> ?o .
                    FILTER(!isLiteral(?o))
                }}
                """
            )
            return total, violations
        violations = self._count(
            f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT (COUNT(*) AS ?count) WHERE {{
                ?s <{property_uri}> ?o .
                FILTER(!isIRI(?o) && !isBlank(?o) || NOT EXISTS {{
                    ?o a ?type .
                    ?type rdfs:subClassOf* <{expected_class}> .
                }})
            }}
            """
        )
        return total, violations

    @staticmethod
    def _rate(total: int, violations: int) -> Optional[float]:
        return (total - violations) / total * 100 if total else None

    def analyze_type_consistency(self) -> Dict[str, Any]:
        definitions = self.extract_property_domains_ranges()[
            : self.parameters.max_properties_analyzed
        ]
        details = []
        domain_total = domain_violations = 0
        range_total = range_violations = 0
        violating_properties = set()

        for property_uri, domain, range_value in definitions:
            detail: Dict[str, Any] = {
                "property": property_uri,
                "domain": domain or None,
                "range": range_value or None,
            }
            if domain:
                total, violations = self.check_domain_violations(property_uri, domain)
                domain_total += total
                domain_violations += violations
                detail.update(
                    {
                        "domain_total": total,
                        "domain_violations": violations,
                        "domain_conformity": (
                            round(self._rate(total, violations), 2) if total else None
                        ),
                    }
                )
                if violations:
                    violating_properties.add(property_uri)

            if range_value:
                if range_value.startswith(XSD_NAMESPACE):
                    range_kind = "datatype"
                    total, violations = self.check_range_violations_datatype(
                        property_uri, range_value
                    )
                else:
                    range_kind = "class"
                    total, violations = self.check_range_violations_class(
                        property_uri, range_value
                    )
                range_total += total
                range_violations += violations
                detail.update(
                    {
                        "range_kind": range_kind,
                        "range_total": total,
                        "range_violations": violations,
                        "range_conformity": (
                            round(self._rate(total, violations), 2) if total else None
                        ),
                    }
                )
                if violations:
                    violating_properties.add(property_uri)
            details.append(detail)

        applicable = domain_total + range_total
        violations = domain_violations + range_violations
        domain_rate = self._rate(domain_total, domain_violations)
        range_rate = self._rate(range_total, range_violations)
        overall_rate = self._rate(applicable, violations)
        status = "computed" if applicable else "not_applicable_no_used_constrained_triples"
        return {
            "properties_analyzed": len(definitions),
            "properties_with_violations": len(violating_properties),
            "average_domain_conformity": (
                round(domain_rate, 2) if domain_rate is not None else None
            ),
            "average_range_conformity": (
                round(range_rate, 2) if range_rate is not None else None
            ),
            "overall_type_consistency": (
                round(overall_rate, 2) if overall_rate is not None else None
            ),
            "applicable_domain_checks": domain_total,
            "domain_violations_total": domain_violations,
            "applicable_range_checks": range_total,
            "range_violations_total": range_violations,
            "applicable_consistency_checks": applicable,
            "total_property_usages_examined": applicable,
            "status": status,
            "aggregation": "evidence-weighted applicable checks",
            "consistency_interpretation": (
                "Closed-profile explicit type alignment over declared and used RDFS constraints."
                if applicable
                else "No declared constraints applied to used triples; no score is reported."
            ),
            "property_details": details,
            "inference_enabled": False,
            "open_world_caveat": (
                "Missing explicit class assertions count as non-alignment under this closed profile; "
                "they are not RDF/OWL logical inconsistencies. rdfs:Resource and rdfs:Literal are "
                "handled according to their RDF semantics."
            ),
            "max_properties_configured": self.parameters.max_properties_analyzed,
        }
