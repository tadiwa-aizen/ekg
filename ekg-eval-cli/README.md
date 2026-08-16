# ekg-eval-cli

`ekg-eval-cli` evaluates RDF-based event-centric knowledge graphs (EKGs) as a multidimensional intrinsic profile. It reports exactly 32 core metrics across nine selected dimensions, plus supporting counts and diagnostics. It does not collapse the dimensions into one universal quality score.

Every output is defined in `ekg_eval_cli/metric_registry.py` as adopted, adapted, literature-informed original, or project-specific. The generated metric audit records its formula, implementation path, empty-case rule, provenance, and limitations.

## Scope

The default profile uses direct `sem:Event` instances and expects SEM-style temporal properties attached to event nodes. It evaluates graph structure, duplicate candidates, temporal representation, minimal event-profile alignment, completeness, explicit type alignment, event richness, external link presence, and predicate-use patterns. It does not establish factual truth, causal correctness, downstream task utility, or mapping correctness.

## Requirements

- Python 3.8 or later
- Apache Jena 5.6.0
- Apache Jena Fuseki 5.6.0
- Dependencies in `requirements.txt`
- Exact evaluation environment in `requirements-lock.txt`

## Installation

```bash
cd ekg-eval-cli
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
python -m pytest -q
```

## Usage

```bash
ekg-eval-cli /path/to/ekg/folder \
  --verbose \
  --output-dir /path/to/results \
  --jena-home /path/to/apache-jena-5.6.0 \
  --fuseki-home /path/to/apache-jena-fuseki-5.6.0
```

For a graph whose projected domain relations do not fit comfortably in memory:

```bash
ekg-eval-cli /path/to/ekg/folder \
  --large-graph-mode \
  --large-graph-work-dir /path/to/work \
  --duckdb-memory-limit 8GB \
  --duckdb-temp-dir /path/to/work/duckdb-temp
```

Important options:

| Option | Default | Meaning |
|---|---:|---|
| `--port` | `3030` | Fuseki port |
| `--fuzzy-threshold` | `0.90` | RapidFuzz token-sort threshold |
| `--fuzzy-sample-size` | `1000` | IRI-ordered event-label sample; no population inference |
| `--temporal-sample-size` | `1000` | Deterministic temporal sample size |
| `--max-properties` | `50` | Maximum declared properties inspected for type alignment |
| `--large-graph-mode` | off | Disk-backed structural projection and union-find |

## Input Contract

The input is one folder containing UTF-8 N-Triples files. The canonical event population is:

```sparql
?event a <http://semanticweb.cs.vu.nl/2009/11/sem/Event> .
```

The minimal profile requires:

- an `rdfs:label`;
- `sem:hasBeginTimeStamp` or `sem:hasEndTimeStamp`;
- a `sem:hasPlace` value.

The domain-connectivity projection is a simple undirected graph over IRI-to-IRI domain relations. It excludes `rdf:type`, `rdfs:*`, `owl:*`, and other configured schema predicates. Direct `sem:Event` resources remain nodes even when they have no retained IRI relation. Predicate direction and parallel edges are not retained, so the structural outputs must be interpreted under this explicit projection.

## Core Dimensions

| Dimension | Core count | Main implementation |
|---|---:|---|
| Graph connectivity and structure | 6 | `analyzer.py`, `large_graph.py` |
| Redundancy and duplication | 3 | `redundancy.py` |
| Temporal consistency | 6 | `temporal.py` |
| Minimal event-profile alignment | 4 | `schema_analyzer.py` |
| Completeness | 5 | `completeness.py` |
| Type consistency/alignment | 1 | `type_consistency.py` |
| Entity richness | 2 | `entity_richness.py` |
| External mapping coverage | 3 | `mapping_coverage.py` |
| Predicate usage | 2 | `predicate_usage.py` |
| **Total** | **32** | `metric_registry.py` |

Type consistency is a closed-profile explicit alignment check over used RDFS domain/range declarations. Missing explicit types count as non-alignment; they are not asserted to be RDF/OWL logical contradictions. `rdfs:Resource` and `rdfs:Literal` are handled according to RDF semantics. If no declared constraint applies, the score is `null` (`N/A`), not 100%.

External mapping rates measure explicit `owl:sameAs` link presence. Wikidata and DBpedia are identified by HTTP(S) host patterns. The tool does not verify equivalence correctness, currency, or resolvability.

Predicate entropy and concentration, graph density, richness, and related values are descriptive diagnostics. Their direction is not universally good or bad.

## Outputs and Provenance

Each successful run writes:

- `ekg_metrics_YYYYMMDD_HHMMSS.json`;
- `ekg_metrics_YYYYMMDD_HHMMSS.csv`;
- `metric_audit.md`.

The JSON contains:

- SHA-256 hashes for every input and an aggregate input hash;
- the exact first-party source snapshot hash and per-file hashes captured when the run starts;
- Git revision and dirty state;
- Python, platform, and package versions;
- metric parameters and execution options;
- exact metric IDs, formulas, implementation paths, empty-case rules, and provenance classifications.

TDB2 and large-graph caches are protected by input manifests. The domain projection additionally records the projection contract and `projection.py` hash. A mismatched cache is rejected rather than silently reused.

## Determinism and Unavailable Values

- Fuzzy matching evaluates every non-identical pair in an IRI-ordered bounded label sample with `RapidFuzz.fuzz.token_sort_ratio` at 0.90.
- Temporal samples are deterministically selected and ordered; the sampling method is stored in the result.
- Interval consistency is event-level. Unparseable events are excluded from the consistency denominator and reported separately; multiple values use `max(begin) <= min(end)`.
- Empty or inapplicable denominators produce `null` plus a status, never a vacuous perfect score.
- Large-graph mode reports unavailable clustering as `-1` with `avg_clustering_status`, and explains conditional edge-connectivity values.

## Tests

Run:

```bash
python -m pytest -q
```

The regression suite uses hand-computable fixtures for all 32 core output formulas, projection semantics, duplicate normalization, temporal edge cases, direct-event denominators, type applicability, mapping host rules, predicate diversity, source manifests, and cache invalidation. Passing unit tests establish implementation checks for these fixtures; they do not establish construct validity for every EKG use case.

## Licence

MIT. See `LICENSE`.
