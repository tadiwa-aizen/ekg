"""Redundancy and duplicate-candidate analysis for RDF-based EKGs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import requests
from rapidfuzz import fuzz

from .config import EvaluationParameters
from .label_normalizer import LabelNormalizer


class RedundancyAnalyzer:
    """Analyze exact and approximate event-label redundancy."""

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

    def _event_labels(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return one deterministic English-or-unlabelled-language label per event."""

        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?event (MIN(STR(?rawLabel)) AS ?label)
        WHERE {{
            ?event a sem:Event ; rdfs:label ?rawLabel .
            FILTER(lang(?rawLabel) = "en" || lang(?rawLabel) = "")
        }}
        GROUP BY ?event
        ORDER BY STR(?event)
        {limit_clause}
        """
        return self._execute_query(query)

    def detect_exact_label_duplicates(self) -> Dict[str, Any]:
        """Group direct SEM events by normalized label."""

        normalized_groups: Dict[str, List[tuple[str, str]]] = {}
        for row in self._event_labels():
            event = row["event"]["value"]
            label = row["label"]["value"]
            normalized = LabelNormalizer.normalize(label)
            normalized_groups.setdefault(normalized, []).append((event, label))

        duplicates = {
            label: events for label, events in normalized_groups.items() if len(events) > 1
        }
        return {
            "duplicate_label_count": len(duplicates),
            "total_duplicate_events": sum(len(events) for events in duplicates.values()),
            "events_with_eligible_labels": sum(len(events) for events in normalized_groups.values()),
            "normalization_applied": True,
        }

    def detect_owl_sameas_duplicates(self) -> Dict[str, Any]:
        """Detect groups of events that share an explicit owl:sameAs target."""

        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        SELECT ?uri (COUNT(DISTINCT ?event) AS ?count)
        WHERE { ?event a sem:Event ; owl:sameAs ?uri . }
        GROUP BY ?uri
        HAVING (COUNT(DISTINCT ?event) > 1)
        """
        results = self._execute_query(query)
        return {
            "sameas_duplicate_count": len(results),
            "total_sameas_duplicate_events": sum(
                int(row["count"]["value"]) for row in results
            ),
        }

    def detect_fuzzy_duplicates(
        self, threshold: Optional[float] = None, sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Count exact token-sort matches in a deterministic bounded sample.

        This is deliberately not an LSH estimate. Every pair in the selected
        sample is evaluated using the same RapidFuzz function and threshold, so
        installing an optional package cannot change the metric definition.
        """

        threshold = (
            self.parameters.fuzzy_similarity_threshold
            if threshold is None
            else float(threshold)
        )
        sample_size = (
            self.parameters.fuzzy_sample_size if sample_size is None else int(sample_size)
        )
        rows = self._event_labels(sample_size)
        events = [
            (row["event"]["value"], LabelNormalizer.normalize(row["label"]["value"]))
            for row in rows
        ]

        threshold_percent = threshold * 100.0
        matched_pairs = []
        for left_index in range(len(events)):
            for right_index in range(left_index + 1, len(events)):
                if events[left_index][1] == events[right_index][1]:
                    continue
                score = fuzz.token_sort_ratio(
                    events[left_index][1], events[right_index][1]
                )
                if score >= threshold_percent:
                    matched_pairs.append(
                        (events[left_index][0], events[right_index][0], round(score, 2))
                    )

        return {
            "fuzzy_duplicate_pairs": len(matched_pairs),
            "candidate_pairs_generated": len(events) * (len(events) - 1) // 2,
            "sample_size": len(events),
            "sample_limit": sample_size,
            "threshold": threshold,
            "method": "deterministic_exact_all_pairs_token_sort_ratio",
            "sampling_method": "first events ordered by event IRI",
            "population_inference": "none; sampled candidate count only",
            "pairs": matched_pairs[:10],
        }

    def analyze_label_quality(self, sample_size: int = 5000) -> Dict[str, Any]:
        """Measure normalized label uniqueness on a deterministic sample."""

        rows = self._event_labels(sample_size)
        labels = [LabelNormalizer.normalize(row["label"]["value"]) for row in rows]
        unique_labels = len(set(labels))
        total_labels = len(labels)
        uniqueness_rate = unique_labels / total_labels * 100 if total_labels else None
        return {
            "total_labels_sampled": total_labels,
            "unique_normalized_labels": unique_labels,
            "label_uniqueness_rate": (
                round(uniqueness_rate, 2) if uniqueness_rate is not None else None
            ),
            "status": "computed" if total_labels else "not_applicable_no_eligible_labels",
            "normalization_applied": True,
            "sampling_method": "first events ordered by event IRI",
        }

    def calculate_total_events(self) -> int:
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        SELECT (COUNT(DISTINCT ?event) AS ?total)
        WHERE { ?event a sem:Event . }
        """
        results = self._execute_query(query)
        return int(results[0]["total"]["value"])

    def analyze_redundancy(self) -> Dict[str, Any]:
        """Run the complete redundancy analysis."""

        total_events = self.calculate_total_events()
        exact = self.detect_exact_label_duplicates()
        sameas = self.detect_owl_sameas_duplicates()
        fuzzy = self.detect_fuzzy_duplicates()
        label_quality = self.analyze_label_quality()
        eligible_labels = exact["events_with_eligible_labels"]
        duplication_rate = (
            exact["total_duplicate_events"] / eligible_labels * 100
            if eligible_labels
            else None
        )
        return {
            "total_events": total_events,
            "exact_label_duplicates": exact["duplicate_label_count"],
            "exact_duplicate_events": exact["total_duplicate_events"],
            "events_with_eligible_labels": exact["events_with_eligible_labels"],
            "sameas_duplicates": sameas["sameas_duplicate_count"],
            "sameas_duplicate_events": sameas["total_sameas_duplicate_events"],
            "fuzzy_duplicate_pairs": fuzzy["fuzzy_duplicate_pairs"],
            "fuzzy_sample_size": fuzzy["sample_size"],
            "fuzzy_threshold": fuzzy["threshold"],
            "fuzzy_method": fuzzy["method"],
            "fuzzy_sampling_method": fuzzy["sampling_method"],
            "duplication_rate": (
                round(duplication_rate, 2) if duplication_rate is not None else None
            ),
            "duplication_rate_denominator": "events with eligible normalized labels",
            "label_quality": label_quality,
        }
