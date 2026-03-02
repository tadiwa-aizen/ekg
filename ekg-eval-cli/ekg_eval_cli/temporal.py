"""Temporal consistency validation for EventKG."""

from typing import Dict, Any, List, Optional
import requests
from dateutil import parser
from datetime import datetime
from .config import EvaluationParameters


class TemporalValidator:
    """Validates temporal consistency in EventKG."""

    def __init__(self, endpoint_url: str, parameters: Optional[EvaluationParameters] = None):
        """
        Initialize TemporalValidator.

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

    def validate_date_formats(self, sample_size: int = None) -> Dict[str, Any]:
        """
        Validate ISO 8601 date format compliance.
        
        Note: EventKG stores temporal data on Relations, not directly on Events.
        This queries relations that reference events.
        
        Args:
            sample_size: Number of relations to sample, uses config default if None
        """
        if sample_size is None:
            sample_size = self.parameters.temporal_sample_size
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX ekgs: <https://eventkg.l3s.uni-hannover.de/schema/>
        
        SELECT ?relation ?date
        WHERE {{
            ?relation a ekgs:Relation ;
                      sem:hasBeginTimeStamp ?date .
        }}
        LIMIT {sample_size}
        """
        
        results = self._execute_query(query)
        
        valid_count = 0
        invalid_count = 0
        invalid_dates = []
        
        for r in results:
            date_str = r['date']['value']
            try:
                # Try to parse as ISO 8601
                parser.isoparse(date_str)
                valid_count += 1
            except (ValueError, parser.ParserError):
                invalid_count += 1
                if len(invalid_dates) < 10:  # Keep first 10 examples
                    invalid_dates.append(date_str)
        
        total = len(results)
        compliance_rate = (valid_count / total * 100) if total > 0 else 0.0
        
        return {
            'total_sampled': total,
            'valid_dates': valid_count,
            'invalid_dates': invalid_count,
            'compliance_rate': round(compliance_rate, 2),
            'invalid_examples': invalid_dates
        }

    def analyze_temporal_granularity(self, sample_size: int = None) -> Dict[str, Any]:
        """
        Analyze temporal granularity distribution.
        
        Note: Queries relations that have temporal data.
        
        Args:
            sample_size: Number of relations to sample, uses config default if None
        """
        if sample_size is None:
            sample_size = self.parameters.temporal_sample_size
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX ekgs: <https://eventkg.l3s.uni-hannover.de/schema/>
        
        SELECT ?relation ?date ?unitType
        WHERE {{
            ?relation a ekgs:Relation ;
                      sem:hasBeginTimeStamp ?date .
            OPTIONAL {{ ?relation ekgs:startUnitType ?unitType }}
        }}
        LIMIT {sample_size}
        """
        
        results = self._execute_query(query)
        
        granularity_counts = {
            'year': 0,
            'month': 0,
            'day': 0,
            'timestamp': 0,
            'unknown': 0
        }
        
        for r in results:
            date_str = r['date']['value']
            unit_type = r.get('unitType', {}).get('value', '')
            
            # Check unit type first
            if 'unitYear' in unit_type:
                granularity_counts['year'] += 1
            elif 'unitMonth' in unit_type:
                granularity_counts['month'] += 1
            elif 'unitDay' in unit_type:
                granularity_counts['day'] += 1
            # Fallback to date string analysis
            elif 'T' in date_str:
                granularity_counts['timestamp'] += 1
            elif len(date_str) == 10:  # YYYY-MM-DD
                granularity_counts['day'] += 1
            elif len(date_str) == 7:  # YYYY-MM
                granularity_counts['month'] += 1
            elif len(date_str) == 4:  # YYYY
                granularity_counts['year'] += 1
            else:
                granularity_counts['unknown'] += 1
        
        total = len(results)
        granularity_percentages = {
            k: round((v / total * 100), 2) if total > 0 else 0.0
            for k, v in granularity_counts.items()
        }
        
        return {
            'total_sampled': total,
            'granularity_counts': granularity_counts,
            'granularity_percentages': granularity_percentages
        }

    def detect_missing_dates(self) -> Dict[str, Any]:
        """
        Detect events without temporal information.
        
        Note: Counts events that have relations with temporal data vs those without.
        """
        # Count total events
        total_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT (COUNT(DISTINCT ?event) AS ?total)
        WHERE {
            ?event a sem:Event .
        }
        """
        
        # Count events with temporal relations
        dated_query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX ekgs: <https://eventkg.l3s.uni-hannover.de/schema/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT (COUNT(DISTINCT ?event) AS ?total)
        WHERE {
            ?event a sem:Event .
            ?relation a ekgs:Relation ;
                      rdf:subject ?event ;
                      sem:hasBeginTimeStamp ?date .
        }
        """
        
        total_results = self._execute_query(total_query)
        dated_results = self._execute_query(dated_query)
        
        total_events = int(total_results[0]['total']['value'])
        dated_events = int(dated_results[0]['total']['value'])
        missing_dates = total_events - dated_events
        
        coverage_rate = (dated_events / total_events * 100) if total_events > 0 else 0.0
        
        return {
            'total_events': total_events,
            'events_with_dates': dated_events,
            'events_missing_dates': missing_dates,
            'temporal_coverage_rate': round(coverage_rate, 2)
        }

    def validate_temporal_semantics(self, sample_size: int = None) -> Dict[str, Any]:
        """
        Validate semantic temporal consistency (end date >= start date).
        
        Args:
            sample_size: Number of events to sample, uses config default if None
        """
        if sample_size is None:
            sample_size = self.parameters.temporal_sample_size
        
        query = f"""
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        
        SELECT ?event ?start ?end
        WHERE {{
            ?event a sem:Event ;
                   sem:hasBeginTimeStamp ?start ;
                   sem:hasEndTimeStamp ?end .
        }}
        LIMIT {sample_size}
        """
        
        results = self._execute_query(query)
        
        total = len(results)
        violations = 0
        violation_examples = []
        
        for r in results:
            try:
                start_str = r['start']['value']
                end_str = r['end']['value']
                
                start_date = parser.isoparse(start_str)
                end_date = parser.isoparse(end_str)
                
                if end_date < start_date:
                    violations += 1
                    if len(violation_examples) < 5:
                        violation_examples.append({
                            'event': r['event']['value'],
                            'start': start_str,
                            'end': end_str
                        })
            except (ValueError, parser.ParserError):
                # Skip invalid dates (already caught by format validation)
                continue
        
        consistency_rate = ((total - violations) / total * 100) if total > 0 else 100.0
        
        return {
            'total_checked': total,
            'violations': violations,
            'consistency_rate': round(consistency_rate, 2),
            'violation_examples': violation_examples
        }

    def analyze_temporal_density(self) -> Dict[str, Any]:
        """
        Measure event distribution across time.
        
        Note: Queries relations with temporal data and extracts years from dates.
        """
        query = """
        PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
        PREFIX ekgs: <https://eventkg.l3s.uni-hannover.de/schema/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT ?date (COUNT(DISTINCT ?event) AS ?count) WHERE {
            ?relation a ekgs:Relation ;
                      rdf:subject ?event ;
                      sem:hasBeginTimeStamp ?date .
            ?event a sem:Event .
        } GROUP BY ?date ORDER BY ?date
        """
        
        results = self._execute_query(query)
        
        if not results:
            return {
                'temporal_span_years': 0,
                'avg_events_per_decade': 0.0,
                'coverage_gaps': 0,
                'peak_decade': None,
                'peak_decade_count': 0
            }
        
        # Extract year from date strings and count
        year_counts = {}
        for r in results:
            if 'date' in r and 'count' in r:
                date_str = r['date']['value']
                # Extract year from ISO date (YYYY-MM-DD or YYYY)
                try:
                    year = int(date_str[:4])
                    count = int(r['count']['value'])
                    year_counts[year] = year_counts.get(year, 0) + count
                except (ValueError, IndexError):
                    continue
        
        if not year_counts:
            return {
                'temporal_span_years': 0,
                'avg_events_per_decade': 0.0,
                'coverage_gaps': 0,
                'peak_decade': None,
                'peak_decade_count': 0
            }
        
        # Calculate temporal span
        min_year = min(year_counts.keys())
        max_year = max(year_counts.keys())
        temporal_span = max_year - min_year
        
        # Group by decades and calculate metrics
        decade_counts = {}
        for year, count in year_counts.items():
            decade = (year // 10) * 10
            decade_counts[decade] = decade_counts.get(decade, 0) + count
        
        # Average events per decade
        avg_per_decade = sum(decade_counts.values()) / len(decade_counts) if decade_counts else 0.0
        
        # Coverage gaps (decades with <10 events)
        coverage_gaps = sum(1 for count in decade_counts.values() if count < 10)
        
        # Peak decade
        peak_decade = max(decade_counts, key=decade_counts.get) if decade_counts else None
        peak_count = decade_counts[peak_decade] if peak_decade else 0
        
        return {
            'temporal_span_years': temporal_span,
            'avg_events_per_decade': round(avg_per_decade, 2),
            'coverage_gaps': coverage_gaps,
            'peak_decade': f"{peak_decade}s" if peak_decade else None,
            'peak_decade_count': peak_count
        }

    def validate_temporal_consistency(self) -> Dict[str, Any]:
        """Run complete temporal validation."""
        date_validation = self.validate_date_formats()
        granularity = self.analyze_temporal_granularity()
        missing_dates = self.detect_missing_dates()
        density = self.analyze_temporal_density()
        
        return {
            'date_format_validation': date_validation,
            'temporal_granularity': granularity,
            'temporal_coverage': missing_dates,
            'temporal_density': density
        }
