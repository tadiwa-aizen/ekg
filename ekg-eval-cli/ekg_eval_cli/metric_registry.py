"""Metric provenance registry for thesis-facing EKG evaluation outputs.

Each metric emitted by the CLI must be either grounded in an external
standard/literature/graph-theory method, or explicitly declared as a custom
operationalization with its own formula and limitations.
"""

from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MetricDefinition:
    """Provenance and interpretation metadata for one reported metric."""

    path: str
    label: str
    formula: str
    provenance_type: str
    source_basis: str
    thesis_use: str
    rationale: str
    limitations: str


CORE_METRICS_BY_DIMENSION = {
    "Graph connectivity and structure": (
        "num_components",
        "giant_component_ratio",
        "avg_clustering",
        "edge_connectivity",
        "density",
        "avg_degree",
    ),
    "Redundancy and duplication": (
        "redundancy.duplication_rate",
        "redundancy.label_quality.label_uniqueness_rate",
        "redundancy.fuzzy_duplicate_pairs",
    ),
    "Temporal consistency": (
        "temporal.date_format_validation.compliance_rate",
        "temporal.temporal_granularity.granularity_percentages",
        "temporal.temporal_coverage.temporal_coverage_rate",
        "temporal.semantic_validation.consistency_rate",
        "temporal.temporal_density.temporal_span_years",
        "temporal.temporal_density.avg_events_per_decade",
    ),
    "Minimal event-profile alignment": (
        "schema.label_coverage_rate",
        "schema.date_coverage_rate",
        "schema.schema_conformance_rate",
        "schema.non_standard_properties_count",
    ),
    "Completeness": (
        "completeness.schema_coverage_percentage",
        "completeness.population_completeness_percentage",
        "completeness.population_completeness.label_coverage_rate",
        "completeness.population_completeness.temporal_coverage_rate",
        "completeness.population_completeness.location_coverage_rate",
    ),
    "Type consistency": ("type_consistency.overall_type_consistency",),
    "Entity richness": (
        "entity_richness.avg_properties_per_event",
        "entity_richness.sparse_entities_percentage",
    ),
    "External mapping coverage": (
        "mapping_coverage.external_link_rate",
        "mapping_coverage.wikidata_coverage",
        "mapping_coverage.dbpedia_coverage",
    ),
    "Predicate usage": (
        "predicate_usage.normalized_shannon_entropy",
        "predicate_usage.hhi_concentration",
    ),
}

CORE_METRIC_PATHS = {
    path for paths in CORE_METRICS_BY_DIMENSION.values() for path in paths
}
CORE_DIMENSION_BY_PATH = {
    path: dimension
    for dimension, paths in CORE_METRICS_BY_DIMENSION.items()
    for path in paths
}

if len(CORE_METRIC_PATHS) != 32:
    raise RuntimeError(f"Core metric registry must contain 32 paths, found {len(CORE_METRIC_PATHS)}")

CORE_METRIC_IDS = {
    path: f"M{index:02d}"
    for index, path in enumerate(
        (
            path
            for paths in CORE_METRICS_BY_DIMENSION.values()
            for path in paths
        ),
        start=1,
    )
}

CORE_IMPLEMENTATION_BY_DIMENSION = {
    "Graph connectivity and structure": "ekg_eval_cli.analyzer.GraphAnalyzer.calculate_metrics",
    "Redundancy and duplication": "ekg_eval_cli.redundancy.RedundancyAnalyzer.analyze_redundancy",
    "Temporal consistency": "ekg_eval_cli.temporal.TemporalValidator.validate_temporal_consistency / validate_temporal_semantics",
    "Minimal event-profile alignment": "ekg_eval_cli.schema_analyzer.SchemaAnalyzer.analyze_schema_conformance",
    "Completeness": "ekg_eval_cli.completeness.CompletenessAnalyzer.analyze_completeness / analyze_population_completeness",
    "Type consistency": "ekg_eval_cli.type_consistency.TypeConsistencyAnalyzer.analyze_type_consistency",
    "Entity richness": "ekg_eval_cli.entity_richness.EntityRichnessAnalyzer.analyze_entity_richness",
    "External mapping coverage": "ekg_eval_cli.mapping_coverage.MappingCoverageAnalyzer.analyze_mapping_coverage",
    "Predicate usage": "ekg_eval_cli.predicate_usage.PredicateUsageAnalyzer.analyze_predicate_usage",
}

CORE_EMPTY_CASE_BY_DIMENSION = {
    "Graph connectivity and structure": "No projected nodes: reject the input and emit no structural profile.",
    "Redundancy and duplication": "No eligible labels: rate is null (N/A); duplicate candidate counts remain 0.",
    "Temporal consistency": "No applicable temporal values or intervals: rate/value is null (N/A), with an explicit status.",
    "Minimal event-profile alignment": "No direct sem:Event instances: profile rates are null (N/A); property count remains descriptive.",
    "Completeness": "No direct sem:Event instances: event-profile rates are null (N/A); schema coverage remains schema-relative.",
    "Type consistency": "No applicable domain/range evidence: score is null (N/A), not 100%.",
    "Entity richness": "No direct sem:Event instances: richness and sparsity are null (N/A).",
    "External mapping coverage": "No direct sem:Event instances: all mapping rates are null (N/A).",
    "Predicate usage": "No predicates: normalized entropy and HHI are null (N/A).",
}


METRIC_DEFINITIONS: List[MetricDefinition] = [
    MetricDefinition(
        "total_nodes",
        "Projected graph node count",
        "|V| on the domain-relation projection, including isolated direct sem:Event resources.",
        "graph-theory standard / adapted RDF projection",
        "RDF 1.1 graph model; standard graph order definition; Newman network analysis.",
        "descriptive structural metric",
        "Counts the number of IRI resources participating in object-property links after RDF-to-graph projection.",
        "Depends on projection choices; literals, blank nodes, rdf:type, and schema predicates are excluded.",
    ),
    MetricDefinition(
        "total_edges",
        "Projected graph edge count",
        "|E| on the undirected simple domain-relation projection.",
        "graph-theory standard / adapted RDF projection",
        "RDF 1.1 graph model; standard graph size definition; Newman network analysis.",
        "descriptive structural metric",
        "Counts relation links used for graph-structural analysis.",
        "Predicate labels and multiedges are collapsed; schema/type predicates are excluded.",
    ),
    MetricDefinition(
        "num_components",
        "Weak/undirected connected components",
        "Number of maximal connected components in the undirected projected graph.",
        "graph-theory standard",
        "Standard connected-component definition; NetworkX connected_components implementation.",
        "descriptive structural metric",
        "Shows fragmentation of the projected EKG relation graph.",
        "Fragmentation is not automatically poor quality; interpretation depends on dataset scope.",
    ),
    MetricDefinition(
        "giant_component_size",
        "Largest connected component size",
        "|V_max|, where V_max is the largest connected component.",
        "graph-theory standard",
        "Standard network-science giant-component concept.",
        "descriptive structural metric",
        "Indicates the absolute size of the main integrated graph region.",
        "Scale-dependent; compare with giant_component_ratio for normalized interpretation.",
    ),
    MetricDefinition(
        "giant_component_ratio",
        "Giant component ratio",
        "|V_max| / |V|.",
        "adapted from graph theory",
        "Standard giant-component concept normalized by graph order.",
        "descriptive structural metric",
        "Compares how much of the graph belongs to the largest connected region.",
        "A highly connected graph can still contain incorrect or redundant facts.",
    ),
    MetricDefinition(
        "avg_clustering",
        "Average local clustering coefficient",
        "(1 / |V|) * sum_v (2e_v / (k_v(k_v - 1))) on the undirected simple projection.",
        "graph-theory standard",
        "Watts-Strogatz clustering coefficient; NetworkX average_clustering implementation.",
        "descriptive structural metric",
        "Summarizes local triangle closure in event/entity neighborhoods.",
        "Sensitive to RDF projection, undirecting, and removal of literal facts.",
    ),
    MetricDefinition(
        "edge_connectivity",
        "Edge connectivity",
        "Minimum number of edges whose removal disconnects the graph; set to 0 for disconnected graphs.",
        "graph-theory standard",
        "Standard edge-connectivity definition; NetworkX edge_connectivity implementation.",
        "descriptive structural metric",
        "Measures structural robustness of a connected projected graph.",
        "Expensive on large graphs and not a direct data-quality score.",
    ),
    MetricDefinition(
        "density",
        "Graph density",
        "2m / (n(n - 1)) for the undirected simple projection.",
        "graph-theory standard",
        "Standard graph-density formula; NetworkX density implementation.",
        "descriptive structural metric",
        "Reports edge saturation under a fixed RDF projection.",
        "Typically very small in KGs and should not be interpreted as quality by itself.",
    ),
    MetricDefinition(
        "avg_degree",
        "Average degree",
        "2m / n for the undirected simple projection.",
        "graph-theory standard",
        "Handshaking lemma; standard graph degree definition.",
        "descriptive structural metric",
        "Summarizes mean projected graph connectivity.",
        "Sensitive to projection choices and node-type mixture.",
    ),
    MetricDefinition(
        "redundancy.exact_label_duplicates",
        "Exact normalized duplicate-label groups",
        "Count of normalized English-label groups with frequency > 1.",
        "custom operationalization adapted from conciseness",
        "Linked Data conciseness dimension from Zaveri et al.; label normalization practice from record linkage.",
        "exploratory/custom redundancy indicator",
        "A transparent first-pass indicator of possible duplicate event records.",
        "Identical labels can describe distinct events; this is candidate evidence, not proof.",
    ),
    MetricDefinition(
        "redundancy.exact_duplicate_events",
        "Events in exact duplicate-label groups",
        "sum_l f(l) for normalized labels where f(l) > 1.",
        "custom operationalization adapted from conciseness",
        "Linked Data conciseness dimension; record-linkage duplicate-candidate practice.",
        "exploratory/custom redundancy indicator",
        "Estimates how many event records are involved in exact-label duplicate groups.",
        "Overcounts true duplication when same labels legitimately repeat.",
    ),
    MetricDefinition(
        "redundancy.sameas_duplicates",
        "Shared owl:sameAs duplicate-candidate groups",
        "Count of external owl:sameAs target IRIs linked by more than one event.",
        "adapted from Linked Data interlinking / OWL identity semantics",
        "OWL owl:sameAs semantics; Linked Data interlinking quality literature.",
        "exploratory/custom duplicate-candidate metric",
        "Shared identity targets are stronger duplicate candidates than labels alone.",
        "owl:sameAs is often misused; shared targets still need review.",
    ),
    MetricDefinition(
        "redundancy.fuzzy_duplicate_pairs",
        "Fuzzy duplicate candidate pairs",
        "Exact count of non-identical sampled normalized-label pairs with RapidFuzz token-sort similarity >= 90%.",
        "adapted from record-linkage literature",
        "Fellegi-Sunter record linkage; duplicate-detection literature; RapidFuzz token_sort_ratio implementation.",
        "exploratory/custom duplicate-candidate metric",
        "Finds near-duplicate labels missed by exact matching.",
        "Deterministic IRI-ordered sample; candidates are not validated duplicates or a population estimate.",
    ),
    MetricDefinition(
        "redundancy.duplication_rate",
        "Exact-label duplicate candidate rate",
        "events in repeated normalized-label groups / events with eligible labels * 100.",
        "custom operationalization adapted from conciseness",
        "Linked Data conciseness dimension; thesis-specific exact-label duplicate proxy.",
        "exploratory/custom redundancy indicator",
        "Provides a normalized summary of conservative duplicate-label evidence.",
        "Uses only exact normalized labels and therefore is incomplete and potentially overinclusive.",
    ),
    MetricDefinition(
        "redundancy.label_quality.label_uniqueness_rate",
        "Label uniqueness rate",
        "unique normalized sampled labels / sampled labels * 100.",
        "custom descriptive metric",
        "Motivated by duplicate-detection and label-quality review practice.",
        "exploratory/custom label diagnostic",
        "Shows how often event labels are unique in the sampled label set.",
        "Normalized labels are language- and sampling-dependent and do not prove semantic uniqueness.",
    ),
    MetricDefinition(
        "temporal.date_format_validation.compliance_rate",
        "Temporal literal validity rate",
        "valid ISO-parseable temporal literals / sampled temporal literals * 100.",
        "standard-based / literature-derived",
        "XML Schema date lexical forms, OWL-Time temporal representation, syntactic validity in KG quality literature.",
        "core quality metric",
        "Tests machine-readable temporal syntax for event timestamps.",
        "Syntactic validity does not guarantee historical correctness.",
    ),
    MetricDefinition(
        "temporal.temporal_granularity.granularity_percentages",
        "Temporal granularity distribution",
        "count(values at granularity g) / sampled temporal values * 100.",
        "adapted descriptive temporal metric",
        "OWL-Time supports multiple temporal positions/granularities; event-KG literature emphasizes temporal anchoring.",
        "descriptive temporal metric",
        "Describes whether the dataset encodes years, months, days, or timestamps.",
        "Granularity is not inherently better or worse without a task requirement.",
    ),
    MetricDefinition(
        "temporal.temporal_coverage.temporal_coverage_rate",
        "Temporal coverage",
        "events with sem:hasBeginTimeStamp or sem:hasEndTimeStamp / direct sem:Event instances * 100.",
        "adapted from completeness literature",
        "Profile-relative completeness in KG/Linked Data quality; SEM/EventKG event-time role.",
        "core quality metric",
        "Time is a core event argument, so coverage is a profile-relative completeness measure.",
        "Checks explicit begin/end predicates only; it does not infer time from relation nodes.",
    ),
    MetricDefinition(
        "temporal.semantic_validation.consistency_rate",
        "Interval validity rate",
        "events with parseable start/end and end >= start / checked start-end events * 100.",
        "custom logical consistency operationalization",
        "OWL-Time interval semantics; temporal consistency principles.",
        "core quality metric where start/end intervals exist",
        "Checks a directly meaningful contradiction in event intervals.",
        "Only applies to explicit start/end timestamps and does not reason over uncertain dates.",
    ),
    MetricDefinition(
        "temporal.temporal_density.temporal_span_years",
        "Temporal span",
        "max(year) - min(year) over dated events.",
        "custom descriptive metric grounded in temporal distribution analysis",
        "OWL-Time temporal positions; event dataset coverage analysis.",
        "descriptive temporal metric",
        "Describes the historical extent of the event corpus.",
        "Span is scope, not quality; large span can hide sparse coverage.",
    ),
    MetricDefinition(
        "temporal.temporal_density.avg_events_per_decade",
        "Average events per decade in observed span",
        "dated events / number of decades from the minimum to maximum observed year, including empty decades.",
        "custom descriptive metric",
        "Temporal distribution analysis; thesis-specific event-corpus summary.",
        "descriptive temporal metric",
        "Summarizes temporal distribution density for context.",
        "Not a standard quality score and depends on domain history.",
    ),
    MetricDefinition(
        "temporal.temporal_density.coverage_gaps",
        "Missing decades in observed span",
        "Count of decades with zero begin-time events between the observed minimum and maximum year.",
        "custom descriptive metric",
        "Thesis-specific temporal coverage diagnostic.",
        "exploratory/custom temporal diagnostic",
        "Flags temporal holes inside the represented span.",
        "A missing decade can reflect source scope rather than poor quality.",
    ),
    MetricDefinition(
        "schema.label_coverage_rate",
        "Label coverage",
        "events with rdfs:label / total sem:Event instances * 100.",
        "adapted from completeness literature",
        "Profile-relative completeness in KG quality literature; rdfs:label as RDF labeling convention.",
        "core quality metric",
        "Labels are required by the evaluation profile for event identification.",
        "Does not check label correctness, language coverage, or ambiguity.",
    ),
    MetricDefinition(
        "schema.date_coverage_rate",
        "Date coverage",
        "events with sem:hasBeginTimeStamp or sem:hasEndTimeStamp / total direct sem:Event instances * 100.",
        "adapted from completeness and event-modeling literature",
        "KG completeness literature; SEM/EventKG event-time modeling.",
        "core quality metric",
        "Measures event-time argument completeness under the thesis profile.",
        "Measures explicit SEM timestamps only; it does not infer dates from other predicates.",
    ),
    MetricDefinition(
        "schema.schema_conformance_rate",
        "Minimal event-profile conformance rate",
        "events with rdfs:label, (sem:hasBeginTimeStamp or sem:hasEndTimeStamp), and sem:hasPlace / total direct sem:Event instances * 100.",
        "custom profile-relative conformance formula",
        "Closed application-profile validation principle; completeness literature under explicit profile requirements.",
        "core quality metric if described as profile-relative",
        "Captures how many events satisfy the declared minimal event profile.",
        "Not RDF/OWL semantic conformance; it is a closed-profile audit.",
    ),
    MetricDefinition(
        "schema.non_standard_properties_count",
        "Non-allowlisted property count",
        "Count of event predicates whose namespace is outside the configured allow-list.",
        "custom descriptive metric",
        "Vocabulary/schema profiling practice; thesis-specific namespace allow-list.",
        "exploratory/schema diagnostic",
        "Surfaces unexpected vocabulary use for manual review.",
        "Non-allowlisted does not mean incorrect; allow-list choice must be declared.",
    ),
    MetricDefinition(
        "completeness.schema_coverage_percentage",
        "Event-class schema coverage",
        "used event classes / declared event classes * 100.",
        "adapted from schema completeness literature",
        "Pipino/Farber-style schema completeness adapted to KG profiles.",
        "core/profile completeness metric",
        "Compares used event classes to the declared event-class profile.",
        "Measures class usage against schema, not real-world population completeness.",
    ),
    MetricDefinition(
        "completeness.population_completeness_percentage",
        "Minimal population completeness",
        "direct sem:Event instances with label, begin or end time, and place / all direct sem:Event instances * 100.",
        "adapted from completeness literature",
        "Profile-relative completeness; column/property completeness adapted to event resources.",
        "core quality metric",
        "Measures required event-facet presence under a closed profile.",
        "Place is profile-required here even though some event classes may legitimately have no place.",
    ),
    MetricDefinition(
        "completeness.class_usage_efficiency_percentage",
        "Class usage efficiency",
        "used event classes / total event instances * 100.",
        "custom descriptive metric",
        "Thesis-specific schema-use diagnostic.",
        "exploratory/schema diagnostic",
        "Shows diversity of event classes relative to instance count.",
        "Not a recognized quality metric and can be misleading for small datasets.",
    ),
    MetricDefinition(
        "completeness.population_completeness.label_coverage_rate",
        "Profile label coverage",
        "events with rdfs:label / total sem:Event instances * 100.",
        "adapted from completeness literature",
        "Profile-relative KG completeness.",
        "core quality metric",
        "Checks required textual identification under the event profile.",
        "Does not validate label quality or multilingual coverage.",
    ),
    MetricDefinition(
        "completeness.population_completeness.temporal_coverage_rate",
        "Profile temporal coverage",
        "events with sem:hasBeginTimeStamp or sem:hasEndTimeStamp / total direct sem:Event instances * 100.",
        "adapted from completeness literature",
        "Profile-relative KG completeness and event-time role modeling.",
        "core quality metric",
        "Checks required temporal anchoring under the event profile.",
        "Does not validate semantic correctness of dates.",
    ),
    MetricDefinition(
        "completeness.population_completeness.location_coverage_rate",
        "Profile place coverage",
        "events with sem:hasPlace / total sem:Event instances * 100.",
        "adapted from completeness and event-modeling literature",
        "Event role completeness from SEM/event-centric KG modeling.",
        "core quality metric when place is required by the profile",
        "Checks spatial argument presence for events.",
        "Some event classes may not require place; class-specific eligibility would be stronger.",
    ),
    MetricDefinition(
        "type_consistency.average_domain_conformity",
        "Evidence-weighted domain conformity",
        "all conforming domain checks / all applicable domain checks * 100.",
        "adapted from Farber KG consistency metrics",
        "Farber et al. domain/range consistency under explicit OWA/CWA caveats; RDFS subclass closure.",
        "core quality metric with applicability denominator",
        "Checks closed-profile subject type compatibility for declared property domains.",
        "RDFS domain is entailment, not an integrity constraint; this must be framed as profile validation.",
    ),
    MetricDefinition(
        "type_consistency.average_range_conformity",
        "Evidence-weighted range conformity",
        "all conforming datatype and object-class range checks / all applicable range checks * 100.",
        "literature-derived / standard-based",
        "Farber relation-range consistency; RDF Schema range semantics; XML Schema datatypes.",
        "core quality metric with applicability denominator",
        "Checks literal datatype compatibility where the profile declares a datatype range.",
        "Closed-profile interpretation; RDFS range normally entails rather than constrains type.",
    ),
    MetricDefinition(
        "type_consistency.overall_type_consistency",
        "Closed-profile explicit type-alignment summary",
        "all explicitly aligned domain and range checks / all applicable declared domain and range checks * 100; null if none apply.",
        "custom closed-profile aggregate over adapted consistency checks",
        "Custom summary informed by RDF/RDFS domain and range semantics and closed-profile validation practice.",
        "exploratory summary metric",
        "Provides a compact evidence-weighted summary of explicit type and datatype alignment.",
        "Missing explicit types are non-alignment under this closed profile, not RDF/OWL logical inconsistency; interpret with applicability counts.",
    ),
    MetricDefinition(
        "type_consistency.applicable_domain_checks",
        "Applicable domain checks",
        "Sum of property usages for analyzed properties with declared domains.",
        "custom reporting denominator",
        "Required by Farber-style caveat that empty constraint sets can yield vacuous scores.",
        "core reporting practice",
        "Prevents overinterpreting high conformity when few triples were actually checked.",
        "Only covers the first max_properties_analyzed property definitions.",
    ),
    MetricDefinition(
        "type_consistency.applicable_range_checks",
        "Applicable datatype range checks",
        "Sum of property usages for analyzed properties with XSD datatype ranges.",
        "custom reporting denominator",
        "Required by Farber-style consistency interpretation and datatype/range validation practice.",
        "core reporting practice",
        "Shows how much evidence supports range-conformity scores.",
        "Only datatype ranges are checked by the current implementation.",
    ),
    MetricDefinition(
        "entity_richness.avg_properties_per_event",
        "Average distinct-predicate richness",
        "mean_e count(distinct outgoing predicates other than rdf:type attached to direct event e).",
        "adapted/custom metric",
        "Adapted from OntoQA attribute richness; event-level descriptive richness is thesis-specific.",
        "exploratory/custom event-description metric",
        "Measures the amount of description attached to event nodes.",
        "Distinct predicates may still be administrative; correctness and relevance are not measured.",
    ),
    MetricDefinition(
        "entity_richness.sparse_entities_percentage",
        "Sparse event rate",
        "events with fewer than 3 distinct outgoing predicates excluding rdf:type / analyzed events * 100.",
        "custom/new metric",
        "Thesis-specific thresholded sparsity indicator.",
        "exploratory/custom event-description metric",
        "Identifies minimally described event records.",
        "The threshold is arbitrary and should be treated as a diagnostic, not a standard.",
    ),
    MetricDefinition(
        "mapping_coverage.external_link_rate",
        "owl:sameAs external-link coverage",
        "events with at least one owl:sameAs link / total events * 100.",
        "literature-derived / standard vocabulary",
        "Linked Data interlinking quality; OWL owl:sameAs identity predicate.",
        "core interlinking metric with caveat",
        "Measures external identity-link presence for event resources.",
        "Coverage does not prove correctness; owl:sameAs misuse is common.",
    ),
    MetricDefinition(
        "mapping_coverage.wikidata_coverage",
        "Wikidata link coverage",
        "events with owl:sameAs on a Wikidata HTTP(S) host / total direct sem:Event instances * 100.",
        "custom source-specific interlinking metric",
        "Adapted from Linked Data interlinking coverage by target source.",
        "core/descriptive interlinking metric",
        "Shows grounding to a major external KG.",
        "Host-pattern detection does not check link correctness, equivalence semantics, currency, or resolvability.",
    ),
    MetricDefinition(
        "mapping_coverage.dbpedia_coverage",
        "DBpedia link coverage",
        "events with owl:sameAs on a DBpedia HTTP(S) host (including language subdomains) / total direct sem:Event instances * 100.",
        "custom source-specific interlinking metric",
        "Adapted from Linked Data interlinking coverage by target source.",
        "core/descriptive interlinking metric",
        "Shows grounding to DBpedia.",
        "Host-pattern detection does not check link correctness, equivalence semantics, currency, or resolvability.",
    ),
    MetricDefinition(
        "predicate_usage.total_unique_predicates",
        "Unique predicate count",
        "|P| in the RDF graph.",
        "custom descriptive metric",
        "Vocabulary breadth/profile analysis.",
        "descriptive structural/schema metric",
        "Characterizes predicate vocabulary breadth.",
        "More predicates do not necessarily indicate better quality.",
    ),
    MetricDefinition(
        "predicate_usage.top_10_concentration",
        "Top-10 predicate concentration",
        "sum(counts of 10 most used predicates) / total triples * 100.",
        "custom descriptive concentration metric",
        "Concentration analysis over categorical frequency distributions.",
        "exploratory predicate-usage diagnostic",
        "Shows whether a small predicate subset dominates the graph.",
        "Not a direct quality metric; compact schemas may legitimately be concentrated.",
    ),
    MetricDefinition(
        "predicate_usage.singleton_predicates",
        "Singleton predicate count",
        "Count of predicates used exactly once.",
        "custom descriptive metric",
        "Vocabulary frequency distribution analysis.",
        "exploratory predicate-usage diagnostic",
        "Flags rare predicates that may indicate schema noise or long-tail modeling.",
        "Rare predicates may be valid domain-specific details.",
    ),
    MetricDefinition(
        "predicate_usage.gini_coefficient",
        "Predicate Gini coefficient",
        "(2 * sum_i i*x_i) / (n * sum_i x_i) - (n + 1) / n after sorting counts.",
        "literature-derived from inequality measurement",
        "Standard Gini coefficient applied to predicate-count distribution.",
        "exploratory predicate-usage diagnostic",
        "Summarizes inequality in predicate usage.",
        "Inequality is not inherently bad; interpret descriptively.",
    ),
    MetricDefinition(
        "predicate_usage.shannon_entropy",
        "Predicate Shannon entropy",
        "-sum_i p_i log2(p_i).",
        "literature-derived from information theory",
        "Shannon entropy applied to predicate frequency distribution.",
        "exploratory predicate-usage diagnostic",
        "Summarizes predicate diversity in a standard mathematical form.",
        "Depends on vocabulary curation and should not be treated as direct quality.",
    ),
    MetricDefinition(
        "predicate_usage.normalized_shannon_entropy",
        "Normalized predicate Shannon entropy",
        "H / log2(k), where k is the number of predicates.",
        "literature-derived from information theory",
        "Normalized Shannon entropy over categorical distributions.",
        "exploratory predicate-usage diagnostic",
        "Allows predicate-diversity comparison across different vocabulary sizes.",
        "Only meaningful when k > 1 and under comparable predicate extraction rules.",
    ),
    MetricDefinition(
        "predicate_usage.hhi_concentration",
        "Predicate HHI concentration",
        "sum_i p_i^2.",
        "literature-derived from concentration measurement",
        "Herfindahl-Hirschman Index applied to predicate frequency distribution.",
        "exploratory predicate-usage diagnostic",
        "Complements entropy by emphasizing dominant predicates.",
        "High concentration can be normal for compact event profiles.",
    ),
]


SUPPORTING_COUNT_PATHS = {
    "redundancy.total_events": ("Total events for redundancy analysis", "COUNT(DISTINCT ?event) where ?event a sem:Event."),
    "redundancy.sameas_duplicate_events": ("Events in shared owl:sameAs candidate groups", "sum of event counts for owl:sameAs targets linked by more than one event."),
    "redundancy.fuzzy_sample_size": ("Fuzzy duplicate sample size", "number of event labels retrieved for sampled fuzzy matching."),
    "redundancy.label_quality.total_labels_sampled": ("Sampled labels", "number of labels retrieved for label-quality analysis."),
    "redundancy.label_quality.unique_labels": ("Unique sampled labels", "count of distinct raw labels in the sampled label set."),
    "redundancy.label_quality.fuzzy_duplicates_90": ("High-similarity sampled label pairs", "count of sampled label pairs with token-sort similarity >= 90."),
    "temporal.date_format_validation.total_sampled": ("Sampled temporal literals", "number of sem:hasBeginTimeStamp values retrieved for format validation."),
    "temporal.date_format_validation.valid_dates": ("Valid temporal literals", "count of sampled temporal literals parseable as ISO-style dates."),
    "temporal.date_format_validation.invalid_dates": ("Invalid temporal literals", "count of sampled temporal literals not parseable as ISO-style dates."),
    "temporal.temporal_granularity.total_sampled": ("Temporal granularity sample size", "number of sem:hasBeginTimeStamp values classified by lexical granularity."),
    "temporal.temporal_granularity.granularity_counts": ("Temporal granularity counts", "counts of sampled temporal values classified as year, month, day, timestamp, or unknown."),
    "temporal.temporal_granularity.granularity_counts.year": ("Year-level temporal literal count", "count of sampled temporal values classified as year-level."),
    "temporal.temporal_granularity.granularity_counts.month": ("Month-level temporal literal count", "count of sampled temporal values classified as month-level."),
    "temporal.temporal_granularity.granularity_counts.day": ("Day-level temporal literal count", "count of sampled temporal values classified as day-level."),
    "temporal.temporal_granularity.granularity_counts.timestamp": ("Timestamp-level temporal literal count", "count of sampled temporal values classified as timestamp-level."),
    "temporal.temporal_granularity.granularity_counts.unknown": ("Unknown-granularity temporal literal count", "count of sampled temporal values that could not be classified into the implemented granularity buckets."),
    "temporal.temporal_granularity.granularity_percentages.year": ("Year-level temporal literal percentage", "year-level temporal literal count / temporal granularity sample size * 100."),
    "temporal.temporal_granularity.granularity_percentages.month": ("Month-level temporal literal percentage", "month-level temporal literal count / temporal granularity sample size * 100."),
    "temporal.temporal_granularity.granularity_percentages.day": ("Day-level temporal literal percentage", "day-level temporal literal count / temporal granularity sample size * 100."),
    "temporal.temporal_granularity.granularity_percentages.timestamp": ("Timestamp-level temporal literal percentage", "timestamp-level temporal literal count / temporal granularity sample size * 100."),
    "temporal.temporal_granularity.granularity_percentages.unknown": ("Unknown-granularity temporal literal percentage", "unknown-granularity temporal literal count / temporal granularity sample size * 100."),
    "temporal.temporal_coverage.total_events": ("Events for temporal coverage", "COUNT(DISTINCT ?event) where ?event a sem:Event."),
    "temporal.temporal_coverage.events_with_dates": ("Events with dates", "COUNT(DISTINCT ?event) where the event has sem:hasBeginTimeStamp."),
    "temporal.temporal_coverage.events_missing_dates": ("Events missing dates", "total_events - events_with_dates."),
    "temporal.semantic_validation.total_checked": ("Intervals checked", "number of events with both sem:hasBeginTimeStamp and sem:hasEndTimeStamp in the sample."),
    "temporal.semantic_validation.violations": ("Interval-order violations", "count of checked events where parsed end date is earlier than parsed start date."),
    "temporal.temporal_density.peak_decade_count": ("Peak decade event count", "maximum event count among decade buckets."),
    "schema.total_events": ("Events for schema/profile diagnostics", "COUNT(DISTINCT ?event) where ?event a sem:Event."),
    "schema.events_with_labels": ("Events with labels", "COUNT(DISTINCT ?event) where event has rdfs:label."),
    "schema.events_with_dates": ("Events with dates", "COUNT(DISTINCT ?event) where event has sem:hasBeginTimeStamp."),
    "schema.fully_described_events": ("Events satisfying minimal profile", "COUNT(DISTINCT ?event) with rdfs:label, sem:hasBeginTimeStamp, and sem:hasPlace."),
    "schema.external_vocabulary_usage": ("External vocabulary usage counts", "per-source count of events using configured external vocabulary namespaces in predicate or object position."),
    "completeness.total_event_instances": ("Total event instances", "COUNT(DISTINCT ?event) where event type is sem:Event or a subclass of sem:Event."),
    "completeness.used_event_classes": ("Used event classes", "COUNT(DISTINCT ?eventClass) used by event instances under sem:Event subclass closure."),
    "completeness.declared_event_classes": ("Declared event classes", "COUNT(DISTINCT subclasses of sem:Event) plus sem:Event itself."),
    "completeness.events_with_complete_data": ("Events with minimal complete data", "COUNT(DISTINCT ?event) with rdfs:label and sem:hasBeginTimeStamp."),
    "completeness.population_completeness.total_events": ("Events for profile completeness", "COUNT(DISTINCT ?event) where ?event a sem:Event."),
    "completeness.population_completeness.events_with_label": ("Events with profile labels", "COUNT(DISTINCT ?event) with rdfs:label."),
    "completeness.population_completeness.events_with_temporal": ("Events with profile temporal values", "COUNT(DISTINCT ?event) with sem:hasBeginTimeStamp."),
    "completeness.population_completeness.events_with_location": ("Events with profile places", "COUNT(DISTINCT ?event) with sem:hasPlace."),
    "completeness.population_completeness.fully_complete_events": ("Events satisfying full implemented profile", "COUNT(DISTINCT ?event) with rdfs:label, sem:hasBeginTimeStamp, and sem:hasPlace."),
    "completeness.population_completeness.population_completeness_rate": ("Full profile population completeness rate", "fully_complete_events / total_events * 100 for the implemented label, temporal, and location profile."),
    "type_consistency.properties_analyzed": ("Analyzed properties", "number of schema properties inspected, capped by max_properties_analyzed."),
    "type_consistency.properties_with_violations": ("Properties with consistency violations", "count of analyzed properties with at least one domain violation."),
    "type_consistency.domain_violations_total": ("Domain violations", "sum of closed-profile domain violations across analyzed properties."),
    "type_consistency.range_violations_total": ("Datatype range violations", "sum of datatype range violations across analyzed XSD datatype properties."),
    "type_consistency.applicable_consistency_checks": ("Applicable consistency checks", "applicable_domain_checks + applicable_range_checks."),
    "type_consistency.total_property_usages_examined": ("Property usages examined", "sum of property usages inspected by implemented domain/range checks."),
    "entity_richness.median_properties_per_event": ("Median event property count", "median count of properties attached to sampled sem:Event nodes."),
    "entity_richness.std_dev_properties": ("Property-count standard deviation", "sample standard deviation of per-event property counts."),
    "entity_richness.total_events_analyzed": ("Events analyzed for richness", "number of event nodes with at least one property in the richness query result."),
    "mapping_coverage.total_events": ("Events for mapping coverage", "COUNT(DISTINCT ?e) where ?e a sem:Event."),
    "mapping_coverage.events_with_external_links": ("Events with owl:sameAs links", "COUNT(DISTINCT ?e) where event has owl:sameAs."),
    "mapping_coverage.events_linked_to_wikidata": ("Events linked to Wikidata", "COUNT(DISTINCT ?e) where owl:sameAs has a Wikidata HTTP(S) host."),
    "mapping_coverage.events_linked_to_dbpedia": ("Events linked to DBpedia", "COUNT(DISTINCT ?e) where owl:sameAs has a DBpedia HTTP(S) host, including language subdomains."),
    "predicate_usage.total_triples": ("Total triples for predicate distribution", "sum of predicate usage counts across the RDF graph."),
}

for path, (label, formula) in SUPPORTING_COUNT_PATHS.items():
    METRIC_DEFINITIONS.append(
        MetricDefinition(
            path=path,
            label=label,
            formula=formula,
            provenance_type="supporting count / denominator",
            source_basis="SPARQL count or direct aggregation used as numerator, denominator, or diagnostic support for audited metrics.",
            thesis_use="supporting evidence",
            rationale="Provides the count needed to interpret the corresponding ratio, rate, or diagnostic metric.",
            limitations="A supporting count is not a standalone quality score; it must be interpreted with the related metric definition.",
        )
    )


def metric_audit() -> Dict[str, Dict[str, str]]:
    """Return metric definitions keyed by output metric path."""

    audit = {}
    for definition in METRIC_DEFINITIONS:
        row = asdict(definition)
        row["core_metric"] = definition.path in CORE_METRIC_PATHS
        row["dimension"] = CORE_DIMENSION_BY_PATH.get(definition.path, "supporting diagnostic")
        if definition.path in CORE_METRIC_PATHS:
            dimension = CORE_DIMENSION_BY_PATH[definition.path]
            row["metric_id"] = CORE_METRIC_IDS[definition.path]
            row["implementation"] = CORE_IMPLEMENTATION_BY_DIMENSION[dimension]
            row["empty_case"] = CORE_EMPTY_CASE_BY_DIMENSION[dimension]
        else:
            row["metric_id"] = None
            row["implementation"] = "supporting output in the analyzer named by its metric path"
            row["empty_case"] = "Interpret with its associated core metric and denominator."
        audit[definition.path] = row
    return audit


def metric_audit_markdown() -> str:
    """Render the metric audit as a Markdown table."""

    lines = [
        "# EKG Evaluation Metric Audit",
        "",
        "Every reported metric is classified as either source-based/adapted or custom. "
        "Custom metrics include their formula, rationale, and limitations so the thesis "
        "does not imply an unsupported industry-standard method.",
        "",
        f"The registry contains exactly {len(CORE_METRIC_PATHS)} core metrics. Other outputs are supporting counts or diagnostics.",
        "",
        "| ID | Core | Dimension | Metric path | Label | Formula / method | Implementation | Empty case | Provenance | Source basis | Thesis use | Limitations |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for definition in METRIC_DEFINITIONS:
        row = [
            CORE_METRIC_IDS.get(definition.path, "--"),
            "Yes" if definition.path in CORE_METRIC_PATHS else "No",
            CORE_DIMENSION_BY_PATH.get(definition.path, "supporting diagnostic"),
            definition.path,
            definition.label,
            definition.formula,
            CORE_IMPLEMENTATION_BY_DIMENSION.get(
                CORE_DIMENSION_BY_PATH.get(definition.path, ""),
                "supporting output in the analyzer named by its metric path",
            ),
            CORE_EMPTY_CASE_BY_DIMENSION.get(
                CORE_DIMENSION_BY_PATH.get(definition.path, ""),
                "Interpret with its associated core metric and denominator.",
            ),
            definition.provenance_type,
            definition.source_basis,
            definition.thesis_use,
            definition.limitations,
        ]
        escaped = [cell.replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.append("")
    return "\n".join(lines)
