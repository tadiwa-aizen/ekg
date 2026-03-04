# ekg-eval-cli

A command-line tool for evaluating the quality of Event-Centric Knowledge Graphs (EKGs). Point it at a folder of N-Triples files and it produces a comprehensive quality report across 10 evaluation dimensions.

## How It Works

```
ekg-eval-cli /path/to/your-event-kg
```

The tool:
1. Loads your `.nt` files into an Apache Jena TDB2 database
2. Starts a Fuseki SPARQL server
3. Runs SPARQL queries + NetworkX analysis across a 16-step pipeline
4. Outputs results to console, JSON, and CSV

## Requirements

- **Python 3.8+**
- **Apache Jena** (for TDB2 database) — place `apache-jena-*` in the working directory or use `--jena-home`
- **Apache Jena Fuseki** (for SPARQL endpoint) — place `apache-jena-fuseki-*` in the working directory or use `--fuseki-home`

## Installation

```bash
cd ekg-eval-cli
pip install -e .
```

### Optional Dependencies

```bash
pip install pyshacl     # For SHACL constraint validation
pip install datasketch  # For LSH-based fuzzy matching (faster on large datasets)
```

## Usage

```bash
# Basic evaluation
ekg-eval-cli /path/to/ekg/folder

# Verbose output (shows 16-step progress)
ekg-eval-cli /path/to/ekg/folder --verbose

# Custom parameters
ekg-eval-cli /path/to/ekg/folder --fuzzy-threshold 0.90 --max-properties 100

# Custom Jena/Fuseki paths
ekg-eval-cli /path/to/ekg/folder --jena-home /opt/jena --fuseki-home /opt/fuseki
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--verbose` | off | Show detailed progress for each step |
| `--output-dir` | `./ekg_results` | Directory for JSON/CSV output |
| `--jena-home` | auto-detect | Path to Apache Jena installation |
| `--fuseki-home` | auto-detect | Path to Fuseki installation |
| `--fuzzy-threshold` | 0.85 | Similarity threshold for fuzzy duplicate detection (0.0–1.0) |
| `--fuzzy-sample-size` | 1000 | Events to sample for fuzzy matching |
| `--temporal-sample-size` | 1000 | Temporal relations to sample for validation |
| `--max-properties` | 50 | Max properties to analyze for type consistency |

## Input Format

The tool expects a folder containing N-Triples (`.nt`) files following the EventKG schema:

```turtle
<event_123> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://semanticweb.cs.vu.nl/2009/11/sem/Event> .
<event_123> <http://www.w3.org/2000/01/rdf-schema#label> "World Cup 2022"@en .
<event_123> <http://semanticweb.cs.vu.nl/2009/11/sem/hasBeginTimeStamp> "2022-11-20"^^<http://www.w3.org/2001/XMLSchema#date> .
<event_123> <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q284070> .
```

The tool uses the SEM (Simple Event Model) ontology and EventKG schema conventions.

## Output

Each run produces three outputs:

### Console
```
[1] GRAPH CONNECTIVITY AND COHESION
  Total Nodes:              1,301
  Total Edges:              2,921
  Connected Components:     4
  Giant Component Ratio:    0.9877

[3] REDUNDANCY AND DUPLICATION
  Total Events:             100
  Fuzzy Duplicate Pairs:    913
  Label Uniqueness:         10.31%

[9] EXTERNAL MAPPING COVERAGE
  Wikidata Coverage:        100.00%
  DBpedia Coverage:         100.00%
```

### JSON — `ekg_results/ekg_metrics_YYYYMMDD_HHMMSS.json`
Full structured results with all 114 data points.

### CSV — `ekg_results/ekg_metrics_YYYYMMDD_HHMMSS.csv`
Flat key-value format for spreadsheet analysis.

## Evaluation Dimensions

The tool evaluates 10 quality dimensions:

| # | Dimension | Module | Key Metrics |
|---|-----------|--------|-------------|
| 1 | Graph Connectivity | `analyzer.py` | Nodes, edges, components, giant component ratio, clustering coefficient, edge connectivity |
| 2 | Graph Density | `analyzer.py` | Average degree, graph density |
| 3 | Redundancy | `redundancy.py` | Exact duplicates, owl:sameAs duplicates, fuzzy duplicates (RapidFuzz), label uniqueness |
| 4 | Temporal Consistency | `temporal.py` | ISO 8601 compliance, temporal granularity, temporal coverage, semantic validation (end ≥ start) |
| 5 | Schema Conformance | `schema_analyzer.py` | Label coverage, date coverage, schema conformance, non-standard property detection |
| 6 | Completeness | `completeness.py` | Schema coverage, population completeness, class usage efficiency |
| 7 | Type Consistency | `type_consistency.py` | Domain/range conformity with RDFS subclass inference |
| 8 | Entity Richness | `entity_richness.py` | Avg/median/stddev properties per event, sparse entity detection |
| 9 | Mapping Coverage | `mapping_coverage.py` | External link rate, Wikidata coverage, DBpedia coverage |
| 10 | Predicate Usage | `predicate_usage.py` | Unique predicates, top-10 concentration, Gini coefficient |

SHACL validation is available as an optional 11th dimension if `pyshacl` is installed.

## Architecture

```
cli.py                  → Click CLI entry point
orchestrator.py         → 16-step pipeline coordinator
path_resolver.py        → Auto-detect Jena/Fuseki installations
database.py             → Load .nt files into TDB2
fuseki.py               → Start/stop Fuseki SPARQL server
sparql.py               → Execute SPARQL queries (graph projection)
analyzer.py             → NetworkX graph analysis
redundancy.py           → Duplicate detection (exact, sameAs, fuzzy)
temporal.py             → Temporal validation (ISO 8601, coverage, semantics)
schema_analyzer.py      → Schema conformance checking
completeness.py         → Population completeness analysis
type_consistency.py     → Domain/range validation with RDFS inference
entity_richness.py      → Properties-per-event statistics
mapping_coverage.py     → Wikidata/DBpedia link analysis
predicate_usage.py      → Property distribution and Gini coefficient
shacl_validator.py      → SHACL constraint validation (optional)
label_normalizer.py     → Unicode NFKD + case folding + diacritic removal
config.py               → Configurable parameters with defaults
output.py               → Console, JSON, CSV output formatting
```

### Pipeline Steps

```
 1. Validate EKG folder (find .nt files)
 2. Resolve Jena/Fuseki paths
 3. Load .nt files → TDB2 database
 4. Start Fuseki SPARQL server
 5. Extract graph edges via SPARQL CONSTRUCT
 6. Analyze graph structure (NetworkX)
 7. Detect redundancy (exact + fuzzy matching)
 8. Validate temporal consistency
 9. Check schema conformance
10. Analyze completeness
11. Check type consistency (RDFS inference)
12. Measure entity richness
13. Check external mapping coverage
14. Analyze predicate usage patterns
15. Run SHACL validation (if pyshacl installed)
16. Save results (JSON + CSV + console)
```

## Key Algorithms

| Task | Library | Method |
|------|---------|--------|
| Connected components | NetworkX | `nx.connected_components()` |
| Clustering coefficient | NetworkX | `nx.average_clustering()` |
| Edge connectivity | NetworkX | `nx.edge_connectivity()` |
| Graph density | NetworkX | `nx.density()` |
| Fuzzy matching | RapidFuzz | `fuzz.token_sort_ratio()` |
| LSH candidate generation | datasketch | `MinHashLSH` (optional) |
| Label normalization | stdlib | Unicode NFKD + `str.casefold()` |
| Date validation | python-dateutil | `parser.isoparse()` |
| RDFS inference | SPARQL | `rdfs:subClassOf*` property paths |
| Graph projection | SPARQL | `CONSTRUCT` with `FILTER(isIRI())` |

## Performance

| Dataset | Events | Total Time |
|---------|--------|------------|
| synthetic-event-kg (100 events) | 100 | ~11s |
| synthetic-event-kg-2 (150 events) | 150 | ~13s |
| Real EventKG (~1M events) | 993,268 | ~30–40 min |

Database loading is a one-time cost. Subsequent runs reuse the existing TDB2 database.

## Known Limitations

- **Type consistency** reports 0% conformity when datasets have limited RDFS domain/range declarations
- **Gini coefficient** can produce negative values (calculation issue)
- **SHACL validation** requires `pyshacl` to be installed separately
- **Fuzzy matching** uses O(n²) naive comparison when `datasketch` is not installed; sampling mitigates this
- **Temporal density** queries the Relations model, which may return empty results for datasets that store dates directly on events
- **No unit tests** — validation was done against ground truth datasets (see `REPORT.md`)

## Project Structure

```
ekg-eval-cli/
├── ekg_eval_cli/
│   ├── __init__.py
│   ├── cli.py
│   ├── orchestrator.py
│   ├── path_resolver.py
│   ├── database.py
│   ├── fuseki.py
│   ├── sparql.py
│   ├── analyzer.py
│   ├── redundancy.py
│   ├── temporal.py
│   ├── schema_analyzer.py
│   ├── completeness.py
│   ├── type_consistency.py
│   ├── entity_richness.py
│   ├── mapping_coverage.py
│   ├── predicate_usage.py
│   ├── shacl_validator.py
│   ├── label_normalizer.py
│   ├── config.py
│   └── output.py
├── setup.py
├── requirements.txt
├── README.md
├── STANDARDS_COMPLIANCE.md
└── REPORT.md (in parent directory)
```

## License

MIT
