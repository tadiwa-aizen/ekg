"""Temporal coverage, format, granularity, distribution, and ordering checks."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

from dateutil import parser
import requests

from .config import EvaluationParameters


SEM = "http://semanticweb.cs.vu.nl/2009/11/sem/"
XSD = "http://www.w3.org/2001/XMLSchema#"


class TemporalValidator:
    """Validate explicitly represented temporal information on direct SEM events."""

    def __init__(
        self,
        endpoint_url: str,
        parameters: Optional[EvaluationParameters] = None,
        nt_files: Optional[List[Path]] = None,
    ):
        self.endpoint_url = endpoint_url
        self.query_url = (
            endpoint_url if endpoint_url.endswith("/sparql") else f"{endpoint_url}/sparql"
        )
        self.parameters = parameters or EvaluationParameters()
        self.nt_files = nt_files or []

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

    def _sample_begin_values(self, sample_size: int) -> Tuple[List[Dict[str, Any]], str]:
        """Return a deterministic hash-ordered sample, with a small-graph fallback."""

        hash_query = f"""
        PREFIX sem: <{SEM}>
        SELECT ?event ?date
        WHERE {{
            ?event a sem:Event ; sem:hasBeginTimeStamp ?date .
            BIND(SHA256(STR(?event)) AS ?sampleKey)
            FILTER(SUBSTR(?sampleKey, 1, 2) = "00")
        }}
        ORDER BY ?sampleKey STR(?event) STR(?date)
        LIMIT {int(sample_size)}
        """
        rows = self._execute_query(hash_query)
        if len(rows) >= min(30, sample_size):
            return rows, "deterministic SHA-256 event sample (00 prefix)"

        fallback_query = f"""
        PREFIX sem: <{SEM}>
        SELECT ?event ?date
        WHERE {{ ?event a sem:Event ; sem:hasBeginTimeStamp ?date . }}
        ORDER BY STR(?event) STR(?date)
        LIMIT {int(sample_size)}
        """
        return self._execute_query(fallback_query), "complete/small-graph IRI-ordered sample"

    @staticmethod
    def _granularity(value: str, datatype: str) -> str:
        datatype_map = {
            f"{XSD}gYear": "year",
            f"{XSD}gYearMonth": "month",
            f"{XSD}date": "day",
            f"{XSD}dateTime": "timestamp",
            f"{XSD}dateTimeStamp": "timestamp",
        }
        if datatype in datatype_map:
            return datatype_map[datatype]
        if re.fullmatch(r"[+-]?\d{4,}", value):
            return "year"
        if re.fullmatch(r"[+-]?\d{4,}-\d{2}", value):
            return "month"
        if re.fullmatch(r"[+-]?\d{4,}-\d{2}-\d{2}(?:Z|[+-]\d{2}:\d{2})?", value):
            return "day"
        if "T" in value:
            return "timestamp"
        return "unknown"

    @classmethod
    def _valid_temporal_lexical(cls, value: str, datatype: str) -> bool:
        granularity = cls._granularity(value, datatype)
        if granularity == "year":
            return bool(re.fullmatch(r"[+-]?\d{4,}", value))
        if granularity == "month":
            match = re.fullmatch(r"([+-]?\d{4,})-(\d{2})", value)
            return bool(match and 1 <= int(match.group(2)) <= 12)
        try:
            parser.isoparse(value)
            return granularity in {"day", "timestamp"}
        except (ValueError, parser.ParserError, OverflowError):
            return False

    @classmethod
    def _parse_temporal_value(cls, value: str) -> datetime:
        """Parse supported temporal granularities to their earliest represented instant."""
        granularity = cls._granularity(value, "")
        if granularity == "year":
            return datetime(int(value), 1, 1)
        if granularity == "month":
            year, month = value.split("-", 1)
            return datetime(int(year), int(month), 1)
        parsed = parser.isoparse(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def validate_date_formats(self, sample_size: Optional[int] = None) -> Dict[str, Any]:
        sample_size = sample_size or self.parameters.temporal_sample_size
        rows, sampling_method = self._sample_begin_values(sample_size)
        invalid_examples = []
        valid_count = 0
        for row in rows:
            value = row["date"]["value"]
            datatype = row["date"].get("datatype", "")
            if self._valid_temporal_lexical(value, datatype):
                valid_count += 1
            elif len(invalid_examples) < 10:
                invalid_examples.append(
                    {"value": value, "datatype": datatype or "untyped"}
                )
        total = len(rows)
        return {
            "total_sampled": total,
            "valid_dates": valid_count,
            "invalid_dates": total - valid_count,
            "compliance_rate": round(valid_count / total * 100, 2) if total else None,
            "status": "computed" if total else "not_applicable_no_begin_values",
            "sampling_method": sampling_method,
            "invalid_examples": invalid_examples,
        }

    def analyze_temporal_granularity(
        self, sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        sample_size = sample_size or self.parameters.temporal_sample_size
        rows, sampling_method = self._sample_begin_values(sample_size)
        counts = {"year": 0, "month": 0, "day": 0, "timestamp": 0, "unknown": 0}
        datatype_counts: Dict[str, int] = defaultdict(int)
        for row in rows:
            value = row["date"]["value"]
            datatype = row["date"].get("datatype", "")
            counts[self._granularity(value, datatype)] += 1
            datatype_counts[datatype or "untyped"] += 1
        total = len(rows)
        percentages = {
            key: round(value / total * 100, 2) if total else None
            for key, value in counts.items()
        }
        return {
            "total_sampled": total,
            "granularity_counts": counts,
            "granularity_percentages": percentages,
            "datatype_counts": dict(datatype_counts),
            "classification_method": "XML Schema datatype with documented lexical fallback",
            "sampling_method": sampling_method,
            "status": "computed" if total else "not_applicable_no_begin_values",
        }

    def detect_missing_dates(self) -> Dict[str, Any]:
        """Count direct SEM events with at least one begin or end timestamp."""

        if self.nt_files:
            return self._detect_missing_dates_from_files()
        query = f"""
        PREFIX sem: <{SEM}>
        SELECT ?total ?dated
        WHERE {{
            {{ SELECT (COUNT(DISTINCT ?event) AS ?total)
               WHERE {{ ?event a sem:Event . }} }}
            {{ SELECT (COUNT(DISTINCT ?datedEvent) AS ?dated)
               WHERE {{
                   ?datedEvent a sem:Event .
                   {{ ?datedEvent sem:hasBeginTimeStamp ?time }}
                   UNION
                   {{ ?datedEvent sem:hasEndTimeStamp ?time }}
               }} }}
        }}
        """
        row = self._execute_query(query)[0]
        total = int(row["total"]["value"])
        dated = int(row["dated"]["value"])
        return self._coverage_result(total, dated, "SPARQL direct sem:Event population")

    @staticmethod
    def _coverage_result(total: int, dated: int, method: str) -> Dict[str, Any]:
        return {
            "total_events": total,
            "events_with_temporal_information": dated,
            "events_missing_temporal_information": total - dated,
            # Compatibility aliases retained for downstream readers.
            "events_with_dates": dated,
            "events_missing_dates": total - dated,
            "temporal_coverage_rate": round(dated / total * 100, 2) if total else None,
            "status": "computed" if total else "not_applicable_no_events",
            "temporal_predicates": [
                f"{SEM}hasBeginTimeStamp",
                f"{SEM}hasEndTimeStamp",
            ],
            "counting_method": method,
        }

    def _detect_missing_dates_from_files(self) -> Dict[str, Any]:
        event_pattern = re.compile(
            rf"^\s*<([^>]+)>\s+<http://www\.w3\.org/1999/02/22-rdf-syntax-ns#type>\s+"
            rf"<{re.escape(SEM)}Event>\s+\.\s*$"
        )
        time_pattern = re.compile(
            rf"^\s*<([^>]+)>\s+<{re.escape(SEM)}has(?:Begin|End)TimeStamp>\s+"
        )
        events = set()
        dated = set()
        for nt_file in self.nt_files:
            with nt_file.open("r", encoding="utf-8", errors="replace") as source:
                for line in source:
                    event_match = event_pattern.match(line)
                    if event_match:
                        events.add(event_match.group(1))
                    time_match = time_pattern.match(line)
                    if time_match:
                        dated.add(time_match.group(1))
        return self._coverage_result(
            len(events), len(events.intersection(dated)), "exact file scan"
        )

    def _sample_intervals(self, sample_size: int) -> Tuple[List[Dict[str, Any]], str]:
        hash_query = f"""
        PREFIX sem: <{SEM}>
        SELECT ?event ?start ?end
        WHERE {{
            ?event a sem:Event ;
                   sem:hasBeginTimeStamp ?start ;
                   sem:hasEndTimeStamp ?end .
            BIND(SHA256(STR(?event)) AS ?sampleKey)
            FILTER(SUBSTR(?sampleKey, 1, 2) = "00")
        }}
        ORDER BY ?sampleKey STR(?event) STR(?start) STR(?end)
        LIMIT {int(sample_size * 4)}
        """
        rows = self._execute_query(hash_query)
        if len({row["event"]["value"] for row in rows}) >= min(30, sample_size):
            return rows, "deterministic SHA-256 event sample (00 prefix)"
        fallback_query = f"""
        PREFIX sem: <{SEM}>
        SELECT ?event ?start ?end
        WHERE {{
            ?event a sem:Event ;
                   sem:hasBeginTimeStamp ?start ;
                   sem:hasEndTimeStamp ?end .
        }}
        ORDER BY STR(?event) STR(?start) STR(?end)
        LIMIT {int(sample_size * 4)}
        """
        return self._execute_query(fallback_query), "complete/small-graph IRI-ordered sample"

    def validate_temporal_semantics(
        self, sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check event-level interval ordering over parseable begin/end values."""

        sample_size = sample_size or self.parameters.temporal_sample_size
        rows, sampling_method = self._sample_intervals(sample_size)
        grouped: Dict[str, Dict[str, set[str]]] = defaultdict(
            lambda: {"starts": set(), "ends": set()}
        )
        for row in rows:
            event = row["event"]["value"]
            grouped[event]["starts"].add(row["start"]["value"])
            grouped[event]["ends"].add(row["end"]["value"])

        violations = 0
        unparseable = 0
        examples = []
        checked = 0
        for event in sorted(grouped)[:sample_size]:
            try:
                starts = [self._parse_temporal_value(value) for value in grouped[event]["starts"]]
                ends = [self._parse_temporal_value(value) for value in grouped[event]["ends"]]
            except (ValueError, TypeError, parser.ParserError, OverflowError):
                unparseable += 1
                continue
            checked += 1
            # Conservative multi-value rule: every represented begin must be
            # no later than every represented end.
            if max(starts) > min(ends):
                violations += 1
                if len(examples) < 5:
                    examples.append(
                        {
                            "event": event,
                            "starts": sorted(grouped[event]["starts"]),
                            "ends": sorted(grouped[event]["ends"]),
                        }
                    )

        rate = (checked - violations) / checked * 100 if checked else None
        return {
            "events_sampled": min(len(grouped), sample_size),
            "total_checked": checked,
            "unparseable_events": unparseable,
            "violations": violations,
            "consistency_rate": round(rate, 2) if rate is not None else None,
            "status": "computed" if checked else "not_applicable_no_parseable_intervals",
            "multi_value_rule": "max(begin values) <= min(end values)",
            "sampling_method": sampling_method,
            "violation_examples": examples,
        }

    def analyze_temporal_density(self) -> Dict[str, Any]:
        query = f"""
        PREFIX sem: <{SEM}>
        SELECT ?date (COUNT(DISTINCT ?event) AS ?count)
        WHERE {{ ?event a sem:Event ; sem:hasBeginTimeStamp ?date . }}
        GROUP BY ?date ORDER BY ?date
        """
        rows = self._execute_query(query)
        year_counts: Dict[int, int] = defaultdict(int)
        for row in rows:
            try:
                year_counts[int(row["date"]["value"][:4])] += int(row["count"]["value"])
            except (ValueError, IndexError, KeyError):
                continue
        if not year_counts:
            return {
                "temporal_span_years": None,
                "avg_events_per_decade": None,
                "coverage_gaps": None,
                "underpopulated_decades": None,
                "peak_decade": None,
                "peak_decade_count": 0,
                "status": "not_applicable_no_parseable_begin_years",
            }

        min_year, max_year = min(year_counts), max(year_counts)
        decade_counts: Dict[int, int] = defaultdict(int)
        for year, count in year_counts.items():
            decade_counts[(year // 10) * 10] += count
        first_decade = (min_year // 10) * 10
        last_decade = (max_year // 10) * 10
        expected_decades = list(range(first_decade, last_decade + 1, 10))
        missing_decades = sum(1 for decade in expected_decades if decade not in decade_counts)
        avg_per_decade = sum(decade_counts.values()) / len(expected_decades)
        peak_decade = max(decade_counts, key=decade_counts.get)
        return {
            "temporal_span_years": max_year - min_year,
            "avg_events_per_decade": round(avg_per_decade, 2),
            "coverage_gaps": missing_decades,
            "coverage_gap_definition": "missing decades between observed minimum and maximum year",
            "underpopulated_decades": sum(
                1 for decade in expected_decades if 0 < decade_counts.get(decade, 0) < 10
            ),
            "peak_decade": f"{peak_decade}s",
            "peak_decade_count": decade_counts[peak_decade],
            "status": "computed",
        }

    def validate_temporal_consistency(self) -> Dict[str, Any]:
        return {
            "date_format_validation": self.validate_date_formats(),
            "temporal_granularity": self.analyze_temporal_granularity(),
            "temporal_coverage": self.detect_missing_dates(),
            "temporal_density": self.analyze_temporal_density(),
        }
