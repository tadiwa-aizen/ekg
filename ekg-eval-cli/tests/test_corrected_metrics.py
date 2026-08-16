from pathlib import Path

import pytest

from ekg_eval_cli.analyzer import GraphAnalyzer
from ekg_eval_cli.completeness import CompletenessAnalyzer
from ekg_eval_cli.config import EvaluationParameters
from ekg_eval_cli.entity_richness import EntityRichnessAnalyzer
from ekg_eval_cli.large_graph import LargeGraphAnalyzer
from ekg_eval_cli.metric_registry import CORE_METRIC_PATHS, metric_audit
from ekg_eval_cli.projection import parse_iri_triple
from ekg_eval_cli.provenance import build_input_manifest, build_source_manifest
from ekg_eval_cli.output import OutputHandler
from ekg_eval_cli.database import DatabaseManager
from ekg_eval_cli.redundancy import RedundancyAnalyzer
from ekg_eval_cli.schema_analyzer import SchemaAnalyzer
from ekg_eval_cli.mapping_coverage import MappingCoverageAnalyzer
from ekg_eval_cli.predicate_usage import PredicateUsageAnalyzer
from ekg_eval_cli.sparql import extract_edges_from_nt_files
from ekg_eval_cli.temporal import TemporalValidator
from ekg_eval_cli.type_consistency import TypeConsistencyAnalyzer


RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
SEM = "http://semanticweb.cs.vu.nl/2009/11/sem/"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
XSD = "http://www.w3.org/2001/XMLSchema#"


def binding(value, datatype=None):
    result = {"type": "literal", "value": value}
    if datatype:
        result["datatype"] = datatype
    return result


def test_projection_excludes_type_hub_and_retains_isolated_events(tmp_path):
    source = tmp_path / "graph.nt"
    source.write_text(
        "\n".join(
            [
                f"<urn:event:1> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:event:2> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:event:1> <{SEM}hasPlace> <urn:place:1> .",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    projected = extract_edges_from_nt_files([source])
    try:
        graph = GraphAnalyzer().load_graph(projected)
        metrics = GraphAnalyzer().calculate_metrics(graph)
    finally:
        projected.unlink(missing_ok=True)

    assert metrics["total_nodes"] == 3
    assert metrics["total_edges"] == 1
    assert metrics["num_components"] == 2
    assert metrics["giant_component_size"] == 2
    assert metrics["giant_component_ratio"] == pytest.approx(2 / 3)
    assert metrics["avg_clustering"] == 0.0
    assert metrics["edge_connectivity"] == 0
    assert metrics["density"] == pytest.approx(1 / 3)
    assert metrics["avg_degree"] == pytest.approx(2 / 3)


def test_projection_record_marks_schema_and_domain_edges():
    type_record = parse_iri_triple(f"<urn:e> <{RDF_TYPE}> <{SEM}Event> .")
    place_record = parse_iri_triple(f"<urn:e> <{SEM}hasPlace> <urn:p> .")
    assert type_record.is_direct_event_declaration
    assert not type_record.is_domain_edge
    assert place_record.is_domain_edge


class FakeRedundancy(RedundancyAnalyzer):
    def __init__(self, labels):
        super().__init__("http://unused")
        self.labels = labels

    def _event_labels(self, limit=None):
        rows = [
            {
                "event": {"value": event},
                "label": {"value": label},
            }
            for event, label in sorted(self.labels)
        ]
        return rows[:limit] if limit else rows


def test_redundancy_is_deterministic_normalized_and_exact_at_90_percent():
    analyzer = FakeRedundancy(
        [
            ("urn:e:1", "Caf\u00e9 Flood"),
            ("urn:e:2", "cafe flood!"),
            ("urn:e:3", "Cafe Floods"),
            ("urn:e:4", "Election in Harare"),
        ]
    )
    exact = analyzer.detect_exact_label_duplicates()
    fuzzy = analyzer.detect_fuzzy_duplicates(threshold=0.90, sample_size=10)
    labels = analyzer.analyze_label_quality(sample_size=10)
    assert exact["duplicate_label_count"] == 1
    assert exact["total_duplicate_events"] == 2
    assert fuzzy["fuzzy_duplicate_pairs"] == 2
    assert fuzzy["method"] == "deterministic_exact_all_pairs_token_sort_ratio"
    assert fuzzy["threshold"] == 0.90
    assert labels["unique_normalized_labels"] == 3
    assert labels["label_uniqueness_rate"] == 75.0


def test_redundancy_core_rates_use_eligible_label_denominator():
    analyzer = FakeRedundancy(
        [
            ("urn:e:1", "Cafe Flood"),
            ("urn:e:2", "cafe flood!"),
            ("urn:e:3", "Cafe Floods"),
            ("urn:e:4", "Election in Harare"),
        ]
    )
    analyzer.calculate_total_events = lambda: 5
    analyzer.detect_owl_sameas_duplicates = lambda: {
        "sameas_duplicate_count": 0,
        "total_sameas_duplicate_events": 0,
    }
    result = analyzer.analyze_redundancy()
    assert result["duplication_rate"] == 50.0
    assert result["label_quality"]["label_uniqueness_rate"] == 75.0
    assert result["fuzzy_duplicate_pairs"] == 2


class FakeTemporal(TemporalValidator):
    def __init__(self, interval_rows):
        super().__init__("http://unused")
        self.interval_rows = interval_rows

    def _sample_intervals(self, sample_size):
        return self.interval_rows, "test sample"


def test_temporal_granularity_uses_datatype_before_lexical_fallback():
    assert TemporalValidator._granularity("2020", f"{XSD}gYear") == "year"
    assert TemporalValidator._granularity("2020-05", f"{XSD}gYearMonth") == "month"
    assert TemporalValidator._granularity("2020-05-02", f"{XSD}date") == "day"
    assert TemporalValidator._granularity("2020-05-02T10:00:00Z", f"{XSD}dateTime") == "timestamp"
    assert TemporalValidator._valid_temporal_lexical("2020-13", f"{XSD}gYearMonth") is False
    assert TemporalValidator._parse_temporal_value("2020").year == 2020
    assert TemporalValidator._parse_temporal_value("2020-01-01T01:00:00+01:00").hour == 0


def test_temporal_semantics_uses_event_denominator_and_reports_parse_failures():
    rows = [
        {
            "event": {"value": "urn:e:1"},
            "start": binding("2020-01-01"),
            "end": binding("2020-01-03"),
        },
        {
            "event": {"value": "urn:e:2"},
            "start": binding("2020-01-05"),
            "end": binding("2020-01-04"),
        },
        {
            "event": {"value": "urn:e:3"},
            "start": binding("not-a-date"),
            "end": binding("2020-01-04"),
        },
    ]
    result = FakeTemporal(rows).validate_temporal_semantics()
    assert result["events_sampled"] == 3
    assert result["total_checked"] == 2
    assert result["unparseable_events"] == 1
    assert result["violations"] == 1
    assert result["consistency_rate"] == 50.0


class FakeTemporalProfile(TemporalValidator):
    def __init__(self):
        super().__init__("http://unused")

    def _sample_begin_values(self, sample_size):
        return [
            {"event": {"value": "urn:e:1"}, "date": binding("2020", f"{XSD}gYear")},
            {"event": {"value": "urn:e:2"}, "date": binding("2020-05", f"{XSD}gYearMonth")},
            {"event": {"value": "urn:e:3"}, "date": binding("2020-05-02", f"{XSD}date")},
            {"event": {"value": "urn:e:4"}, "date": binding("invalid", f"{XSD}date")},
        ], "test sample"

    def _execute_query(self, query):
        return [
            {"date": {"value": "2001-01-01"}, "count": {"value": "2"}},
            {"date": {"value": "2021-01-01"}, "count": {"value": "4"}},
        ]


def test_temporal_core_format_granularity_and_density_formulas():
    analyzer = FakeTemporalProfile()
    formats = analyzer.validate_date_formats()
    granularity = analyzer.analyze_temporal_granularity()
    density = analyzer.analyze_temporal_density()
    assert formats["compliance_rate"] == 75.0
    assert granularity["granularity_percentages"] == {
        "year": 25.0,
        "month": 25.0,
        "day": 50.0,
        "timestamp": 0.0,
        "unknown": 0.0,
    }
    assert density["temporal_span_years"] == 20
    assert density["avg_events_per_decade"] == 2.0
    assert density["coverage_gaps"] == 1


def test_temporal_coverage_accepts_begin_or_end(tmp_path):
    source = tmp_path / "temporal.nt"
    source.write_text(
        "\n".join(
            [
                f"<urn:e:1> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:e:2> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:e:1> <{SEM}hasEndTimeStamp> \"2020-01-01\"^^<{XSD}date> .",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = TemporalValidator("http://unused", nt_files=[source]).detect_missing_dates()
    assert result["total_events"] == 2
    assert result["events_with_temporal_information"] == 1
    assert result["temporal_coverage_rate"] == 50.0


def test_schema_profile_accepts_begin_or_end_from_files(tmp_path):
    source = tmp_path / "schema.nt"
    source.write_text(
        "\n".join(
            [
                f"<urn:e:1> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:e:1> <{RDFS_LABEL}> \"End-only event\"@en .",
                f"<urn:e:1> <{SEM}hasEndTimeStamp> \"2020-01-01\"^^<{XSD}date> .",
                f"<urn:e:1> <{SEM}hasPlace> <urn:place> .",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = SchemaAnalyzer("http://unused", nt_files=[source]).analyze_schema_conformance()
    assert result["date_coverage_rate"] == 100.0
    assert result["schema_conformance_rate"] == 100.0


def test_completeness_uses_one_direct_event_population_and_three_part_profile(tmp_path):
    source = tmp_path / "complete.nt"
    source.write_text(
        "\n".join(
            [
                f"<urn:e:1> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:e:2> <{RDF_TYPE}> <{SEM}Event> .",
                f"<urn:child> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <{SEM}Event> .",
                f"<urn:e:3> <{RDF_TYPE}> <urn:child> .",
                f"<urn:e:1> <{RDFS_LABEL}> \"Complete\"@en .",
                f"<urn:e:1> <{SEM}hasEndTimeStamp> \"2020-01-01\"^^<{XSD}date> .",
                f"<urn:e:1> <{SEM}hasPlace> <urn:place> .",
                f"<urn:e:2> <{RDFS_LABEL}> \"Partial\"@en .",
                f"<urn:e:3> <{RDFS_LABEL}> \"Subclass event\"@en .",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    analyzer = CompletenessAnalyzer("http://unused", [source])
    outer = analyzer.analyze_completeness()
    profile = analyzer.analyze_population_completeness()
    assert outer["total_event_instances"] == 2
    assert outer["events_with_complete_data"] == 1
    assert outer["population_completeness_percentage"] == 50.0
    assert profile["total_events"] == 2
    assert profile["fully_complete_events"] == 1
    assert profile["population_completeness_rate"] == 50.0
    assert outer["schema_coverage_percentage"] == 100.0
    assert profile["label_coverage_rate"] == 100.0
    assert profile["temporal_coverage_rate"] == 50.0
    assert profile["location_coverage_rate"] == 50.0


class FakeSchema(SchemaAnalyzer):
    def __init__(self):
        super().__init__("http://unused")

    def count_total_events(self):
        return 4

    def count_events_with_labels(self):
        return 3

    def count_events_with_dates(self):
        return 2

    def count_fully_described_events(self):
        return 1

    def detect_non_standard_properties(self, limit=50):
        return {"urn:custom:p": 2}

    def count_external_vocabulary_usage(self):
        return {"schema.org": 0, "dbpedia": 1, "wikidata": 2}


def test_schema_core_profile_metrics_are_hand_computable():
    result = FakeSchema().analyze_schema_conformance()
    assert result["label_coverage_rate"] == 75.0
    assert result["date_coverage_rate"] == 50.0
    assert result["schema_conformance_rate"] == 25.0
    assert result["non_standard_properties_count"] == 1


class FakeTypeConsistency(TypeConsistencyAnalyzer):
    def __init__(self, applicable=True):
        super().__init__("http://unused", EvaluationParameters(max_properties_analyzed=10))
        self.applicable = applicable

    def extract_property_domains_ranges(self):
        return [("urn:p:1", "urn:Class", ""), ("urn:p:2", "", f"{XSD}string")]

    def check_domain_violations(self, property_uri, expected_domain):
        return (100, 20) if self.applicable else (0, 0)

    def check_range_violations_datatype(self, property_uri, expected_datatype):
        return (10, 0) if self.applicable else (0, 0)


def test_type_consistency_is_evidence_weighted():
    result = FakeTypeConsistency().analyze_type_consistency()
    assert result["applicable_consistency_checks"] == 110
    assert result["overall_type_consistency"] == pytest.approx(81.82)
    assert result["average_domain_conformity"] == 80.0
    assert result["average_range_conformity"] == 100.0


def test_type_consistency_is_null_when_no_checks_apply():
    result = FakeTypeConsistency(applicable=False).analyze_type_consistency()
    assert result["overall_type_consistency"] is None
    assert result["status"] == "not_applicable_no_used_constrained_triples"


class FakeResourceRange(TypeConsistencyAnalyzer):
    def __init__(self):
        super().__init__("http://unused")

    def _count(self, query):
        return 7


def test_rdfs_resource_range_accepts_all_rdf_terms():
    analyzer = FakeResourceRange()
    assert analyzer.check_range_violations_class("urn:p", "http://www.w3.org/2000/01/rdf-schema#Resource") == (7, 0)


class FakeRichness(EntityRichnessAnalyzer):
    def __init__(self):
        super().__init__("http://unused")
        self.query = ""

    def _execute_query(self, query):
        self.query = query
        return [
            {"event": {"value": "urn:e:1"}, "propCount": {"value": "2"}},
            {"event": {"value": "urn:e:2"}, "propCount": {"value": "4"}},
        ]


def test_richness_counts_distinct_predicates_and_excludes_type():
    analyzer = FakeRichness()
    result = analyzer.analyze_entity_richness()
    assert "COUNT(DISTINCT ?prop)" in analyzer.query
    assert "?prop != rdf:type" in analyzer.query
    assert result["avg_properties_per_event"] == 3
    assert result["sparse_entities_percentage"] == 50


class FakeMapping(MappingCoverageAnalyzer):
    def __init__(self):
        super().__init__("http://unused")
        self.counts = iter([4, 3, 2, 1])
        self.queries = []

    def _execute_query(self, query):
        self.queries.append(query)
        return [{"count": {"value": str(next(self.counts))}}]


def test_mapping_core_rates_use_direct_event_denominator():
    analyzer = FakeMapping()
    result = analyzer.analyze_mapping_coverage()
    assert result["external_link_rate"] == 75.0
    assert result["wikidata_coverage"] == 50.0
    assert result["dbpedia_coverage"] == 25.0
    assert "COUNT(DISTINCT ?e)" in analyzer.queries[0]
    assert "wikidata[.]org" in analyzer.queries[2]
    assert "dbpedia[.]org" in analyzer.queries[3]
    assert "\\." not in analyzer.queries[2]
    assert "\\." not in analyzer.queries[3]


class FakePredicateUsage(PredicateUsageAnalyzer):
    def __init__(self):
        super().__init__("http://unused")

    def _execute_query(self, query):
        return [
            {"usage": {"value": "2"}},
            {"usage": {"value": "1"}},
            {"usage": {"value": "1"}},
        ]


def test_predicate_core_entropy_and_concentration_have_exact_expectations():
    result = FakePredicateUsage().analyze_predicate_usage()
    assert result["normalized_shannon_entropy"] == pytest.approx(0.9464)
    assert result["hhi_concentration"] == 0.375
    assert result["gini_coefficient"] == pytest.approx(0.1667)


def test_registry_contains_exactly_32_defined_core_metrics():
    audit = metric_audit()
    assert len(CORE_METRIC_PATHS) == 32
    assert CORE_METRIC_PATHS <= set(audit)
    assert sum(1 for row in audit.values() if row["core_metric"]) == 32
    core_rows = [row for row in audit.values() if row["core_metric"]]
    assert len({row["metric_id"] for row in core_rows}) == 32
    assert all(row["implementation"] and row["empty_case"] for row in core_rows)


def test_input_manifest_changes_when_content_changes(tmp_path):
    source = tmp_path / "data.nt"
    cache = tmp_path / "manifest.json"
    source.write_text("first", encoding="utf-8")
    first = build_input_manifest([source], cache)
    source.write_text("second", encoding="utf-8")
    second = build_input_manifest([source], cache)
    assert first["aggregate_sha256"] != second["aggregate_sha256"]


def test_source_manifest_hashes_first_party_source(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    source = package / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    first = build_source_manifest(tmp_path)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    second = build_source_manifest(tmp_path)
    assert first["aggregate_sha256"] != second["aggregate_sha256"]
    assert first["files"][0]["path"] == "package/module.py"


def test_large_graph_projection_cache_is_fingerprinted(tmp_path):
    source = tmp_path / "graph.nt"
    source.write_text(
        f"<urn:e> <{RDF_TYPE}> <{SEM}Event> .\n"
        f"<urn:e> <{SEM}hasPlace> <urn:p> .\n",
        encoding="utf-8",
    )
    analyzer = LargeGraphAnalyzer(tmp_path / "work")
    analyzer.work_dir.mkdir()
    manifest = build_input_manifest([source])
    count, reused = analyzer._ensure_projection_files([source], manifest)
    assert count == 1
    assert reused is False
    count, reused = analyzer._ensure_projection_files([source], manifest)
    assert count == 1
    assert reused is True

    cache_manifest = analyzer.projection_manifest_path.read_text(encoding="utf-8")
    analyzer.projection_manifest_path.write_text(
        cache_manifest.replace('"projection_code_sha256": "', '"projection_code_sha256": "stale'),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="does not match"):
        analyzer._ensure_projection_files([source], manifest)


def test_empty_denominators_are_not_reported_as_perfect_or_zero_quality():
    assert FakeRedundancy([]).analyze_label_quality()["label_uniqueness_rate"] is None

    empty_richness = EntityRichnessAnalyzer("http://unused")
    empty_richness._execute_query = lambda query: []
    assert empty_richness.analyze_entity_richness()["avg_properties_per_event"] is None

    empty_predicates = PredicateUsageAnalyzer("http://unused")
    empty_predicates._execute_query = lambda query: []
    assert empty_predicates.analyze_predicate_usage()["hhi_concentration"] is None

    empty_mapping = MappingCoverageAnalyzer("http://unused")
    empty_mapping._execute_query = lambda query: [{"count": {"value": "0"}}]
    assert empty_mapping.analyze_mapping_coverage()["external_link_rate"] is None


def test_console_output_renders_unavailable_values_as_na(tmp_path, capsys):
    OutputHandler(tmp_path).display_results(
        {
            "total_nodes": 0,
            "total_edges": 0,
            "num_components": 0,
            "giant_component_size": 0,
            "giant_component_ratio": None,
            "avg_clustering": -1,
            "edge_connectivity": -1,
            "avg_degree": None,
            "density": None,
            "predicate_usage": {
                "total_unique_predicates": 0,
                "total_triples": 0,
                "top_10_concentration": None,
                "singleton_predicates": 0,
                "gini_coefficient": None,
                "shannon_entropy": None,
                "normalized_shannon_entropy": None,
                "hhi_concentration": None,
            },
        }
    )
    rendered = capsys.readouterr().out
    assert "Average Clustering:       N/A" in rendered
    assert "Top-10 Concentration:     N/A" in rendered


def test_database_loader_rejects_incomplete_jena_before_creating_cache(tmp_path):
    jena_home = tmp_path / "jena"
    jena_home.mkdir()
    ekg_folder = tmp_path / "graph"
    ekg_folder.mkdir()
    source = ekg_folder / "data.nt"
    source.write_text("<urn:s> <urn:p> <urn:o> .\n", encoding="utf-8")

    manager = DatabaseManager(jena_home, ekg_folder)
    with pytest.raises(FileNotFoundError, match="complete binary distribution"):
        manager.load_database([source])
    assert not manager.db_path.exists()
