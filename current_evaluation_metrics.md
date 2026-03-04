# Current Evaluation Metrics (ekg-eval-cli)

30 metrics that actually evaluate EKG quality.

## Graph Structure (6)
1. `num_components` — Number of disconnected subgraphs (fragmentation)
2. `giant_component_ratio` — Fraction of nodes in the largest connected component (cohesion)
3. `avg_clustering` — Average clustering coefficient (local connectivity)
4. `edge_connectivity` — Minimum edges to remove to disconnect the graph (robustness)
5. `density` — Ratio of actual edges to maximum possible edges (interconnectedness)
6. `avg_degree` — Average number of edges per node (connectedness)

## Redundancy & Duplication (3)
7. `redundancy.duplication_rate` — % of events involved in exact label duplicates
8. `redundancy.label_quality.label_uniqueness_rate` — % of distinct labels in the sample (label diversity)
9. `redundancy.fuzzy_duplicate_pairs` — Count of label pairs with ≥90% fuzzy similarity

## Temporal Consistency (6)
10. `temporal.date_format_validation.compliance_rate` — % of event dates that are valid ISO 8601
11. `temporal.temporal_coverage.temporal_coverage_rate` — % of events that have a date
12. `temporal.temporal_density.temporal_span_years` — Year range covered by events
13. `temporal.temporal_density.avg_events_per_decade` — Average events per decade
14. `temporal.temporal_density.coverage_gaps` — Number of decades with fewer than 10 events
15. `temporal.semantic_validation.consistency_rate` — % of events where end date ≥ start date

## Schema Conformance (4)
16. `schema.label_coverage_rate` — % of events with rdfs:label
17. `schema.date_coverage_rate` — % of events with sem:hasBeginTimeStamp
18. `schema.schema_conformance_rate` — % of events with label AND date AND location
19. `schema.non_standard_properties_count` — Count of predicates not from standard vocabularies

## Completeness (4)
20. `completeness.schema_coverage_percentage` — % of declared event classes that have instances
21. `completeness.population_completeness.population_completeness_rate` — % of events with label + date + location
22. `completeness.population_completeness.label_coverage_rate` — % of events with rdfs:label
23. `completeness.population_completeness.temporal_coverage_rate` — % of events with sem:hasBeginTimeStamp
24. `completeness.population_completeness.location_coverage_rate` — % of events with sem:hasPlace

## Type Consistency (1)
25. `type_consistency.overall_type_consistency` — Average RDFS domain/range conformity across used properties

## Entity Richness (2)
26. `entity_richness.avg_properties_per_event` — Mean distinct predicates per event
27. `entity_richness.sparse_entities_percentage` — % of events with fewer than 3 predicates

## External Mapping Coverage (3)
28. `mapping_coverage.external_link_rate` — % of events with at least one owl:sameAs link
29. `mapping_coverage.wikidata_coverage` — % of events linked to Wikidata
30. `mapping_coverage.dbpedia_coverage` — % of events linked to DBpedia

## Predicate Usage (2)
31. `predicate_usage.top_10_concentration` — % of triples from the 10 most-used predicates
32. `predicate_usage.gini_coefficient` — Inequality of predicate usage (0=equal, 1=dominated)
