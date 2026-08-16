# Large Graph Mode Context for Real OEKG Evaluation

## Why this exists

The thesis evaluation framework needs evidence that it can run on a real published Event-Centric Knowledge Graph, not only on synthetic datasets. The chosen real dataset is OEKG/EventKG-style RDF from Zenodo because it is public, published, RDF-based, and structurally close to the EventKG conventions used by the thesis and CLI.

The current `ekg-eval-cli` works on small synthetic datasets, but its graph-structure stage originally materialised the full projected graph in NetworkX. That is not feasible for the real OEKG event layer on this machine. The real event-layer projection produced a 7.34GB edge file, and NetworkX continued running for hours using about 9.5GB RAM without producing final results.

The aim is therefore not to weaken the evaluation, but to replace the in-memory NetworkX stage with a more defensible large-graph computation path:

- exact SPARQL/TDB metrics for RDF-native dimensions;
- exact out-of-core graph counts and degree statistics;
- exact streaming connected components using union-find over dense integer IDs;
- approximate clustering later using a documented wedge-sampling method;
- no full exact edge-connectivity attempt at this scale unless it is certified cheaply.

This gives a thesis-defensible explanation: NetworkX was inappropriate for the projected graph scale, but the graph metrics can still be computed with algorithms whose memory use matches the information required by each metric.

## Machine constraints

- Windows workstation.
- Approximately 20GB RAM.
- Disk space has varied during testing; after OEKG extraction and TDB build it was about 84GB free.
- Full OEKG extraction is about 63.32GB.
- Clean OEKG event-layer TDB database is about 15.9GB.
- The original compressed archive is about 3.55GB.

Disk space must be checked before and after expensive runs.

## Important source and data paths

Repository/root:

- `C:\Users\riski\Desktop\Projects\masters`
- EKG work folder: `C:\Users\riski\Desktop\Projects\masters\ekg`
- CLI: `C:\Users\riski\Desktop\Projects\masters\ekg\ekg-eval-cli`

Real OEKG work area:

- `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation`

OEKG files:

- Compressed archive:
  `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\raw\event_kg.tar.gz`
- Full extracted archive:
  `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\oekg-full\event_kg`
- Clean event-layer input folder:
  `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\oekg-event-layer-clean`
- Clean event-layer TDB database:
  `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\oekg-event-layer-clean\databases\eventkg-db`

Research note to read:

- `C:\Users\riski\Desktop\Projects\masters\ekg\deep-research-report-large-graph-computation.md`

Cleaning script:

- `C:\Users\riski\Desktop\Projects\masters\ekg\real-oekg-evaluation\clean_oekg_literals.py`

Jena/Fuseki:

- Complete Jena:
  `C:\Users\riski\Desktop\Projects\masters\ekg\tools\apache-jena-5.6.0-bin\apache-jena-5.6.0`
- Fuseki:
  `C:\Users\riski\Desktop\Projects\masters\ekg\apache-jena-fuseki-5.6.0`

Note: `C:\Users\riski\Desktop\Projects\masters\ekg\apache-jena-5.6.0` is incomplete because it lacks `lib`. Use the complete Jena path above.

## What has already been done

1. Downloaded OEKG small RDF files from Zenodo.
   - They loaded as RDF but did not contain `sem:Event` typed event nodes.
   - They had about 712,320 triples and 16,672 event URI references.
   - They were insufficient for a proper real EKG evaluation.

2. Tried the OEKG public SPARQL endpoint.
   - The endpoint UI loaded, but actual query submissions returned HTTP 404.
   - Do not rely on the public endpoint for the thesis experiment.

3. Downloaded the full OEKG/EventKG archive.
   - Archive size: about 3.55GB.
   - Extracted size: about 63.32GB.
   - Full extraction was acceptable on disk, but full 63GB TDB loading is still risky.

4. Built an event-layer input folder using selected OEKG/EventKG files:
   - `events.nt`
   - `events_descriptions_from_text_events.nt`
   - `events_first_sentences.nt`
   - `preferred_labels.nt`
   - `property_labels.nt`
   - `relations_event_base.nt`
   - `relations_events_literals.nt`
   - `relations_events_other.nt`
   - `schema.nt`
   - `text_events.nt`
   - `types.nt`
   - `types_ontology_dbpedia.nt`
   - `type_labels_dbpedia.nt`

5. Found malformed triples in the published data.
   - Many malformed external IRIs appear as Jena warnings.
   - One fatal problem came from illegal backslash escapes in string literals.
   - `clean_oekg_literals.py` fixed only invalid literal backslashes.
   - It changed 7 lines in `relations_events_literals.nt`.
   - Original extracted files remain untouched.

6. Loaded the cleaned OEKG event layer into Jena TDB.
   - TDB size: about 15.9GB.
   - Verified event count:
     `954,554` `sem:Event` nodes.

7. Tried a direct TDB graph projection.
   - It was still too slow.
   - Replaced it with a streaming N-Triples parser that writes IRI-to-IRI projected edges.
   - That produced a 7.34GB temporary edge projection file.

8. Tried NetworkX on the projected edge file.
   - It ran for hours and used about 9.5GB RAM.
   - No final JSON results were produced.
   - The run was stopped.

## Current code changes already made

Files touched:

- `C:\Users\riski\Desktop\Projects\masters\ekg\ekg-eval-cli\ekg_eval_cli\sparql.py`
- `C:\Users\riski\Desktop\Projects\masters\ekg\ekg-eval-cli\ekg_eval_cli\orchestrator.py`

Current partial change:

- Added streaming N-Triples edge extraction.
- Orchestrator now extracts graph edges from `.nt` files before starting Fuseki.

This is not enough because it still writes a huge edge file and sends it to NetworkX.

## Target implementation

Add a large graph mode to the CLI:

```text
ekg-eval-cli PATH --large-graph-mode
```

In large graph mode:

1. Load/reuse Jena TDB as before.
2. Do not run NetworkX for full graph structure.
3. Project IRI-to-IRI RDF triples into a DuckDB-backed edge table.
4. Canonicalise the projected graph as a simple undirected graph:
   - ignore triples where subject or object is not an IRI;
   - remove self-loops;
   - sort endpoints lexically into `(u, v)`;
   - collapse duplicate `(u, v)` pairs.
5. Create dense integer node IDs.
6. Create `edges_id(u BIGINT, v BIGINT)`.
7. Compute exact scalable metrics:
   - projected node count;
   - unique undirected edge count;
   - average degree;
   - density;
   - min degree;
   - max degree;
   - leaf count;
   - leaf fraction;
   - component count;
   - giant component size;
   - giant component ratio.
8. For edge connectivity:
   - if component count > 1, set global edge connectivity to 0 as a conditional exact result;
   - otherwise do not attempt full exact edge connectivity in large graph mode;
   - report the limitation and replacement metrics.
9. For clustering:
   - initially mark not computed in the first large graph implementation;
   - later add wedge sampling once exact metrics are stable.
10. Continue running RDF-native SPARQL metrics:
   - redundancy;
   - temporal consistency;
   - schema/profile conformance;
   - completeness;
   - type consistency;
   - entity richness;
   - mapping coverage;
   - predicate usage.

## Proposed new files/modules

Likely add:

- `ekg_eval_cli/large_graph.py`

Responsibilities:

- manage a DuckDB database;
- stream N-Triples files into raw edge rows;
- canonicalise and deduplicate edges;
- assign node IDs;
- compute degrees and derived statistics;
- run union-find connected components.

Likely CLI options to add in `cli.py`:

- `--large-graph-mode`
- `--large-graph-work-dir`
- `--duckdb-memory-limit`, default around `8GB`
- `--duckdb-temp-dir`

Likely config additions in `orchestrator.py`:

- `large_graph_mode: bool = False`
- `large_graph_work_dir: Optional[Path] = None`
- `duckdb_memory_limit: str = "8GB"`
- `duckdb_temp_dir: Optional[Path] = None`

## Implementation details

Projection definition:

Let `D` be the RDF dataset. The projected graph is:

```text
G = (V, E)
V = all IRIs occurring as endpoints of at least one projected edge
E = unique unordered pairs {s, o}
    where (s, p, o) is an RDF triple,
    s and o are IRIs,
    and s != o
```

This preserves the original NetworkX `Graph` semantics more carefully than the old code:

- undirected;
- no predicate multiplicity;
- no duplicate edges;
- no self-loops.

DuckDB staging:

```sql
CREATE TABLE raw_edges (s VARCHAR, o VARCHAR);

CREATE TABLE canonical_edges AS
SELECT DISTINCT
  CASE WHEN s < o THEN s ELSE o END AS u,
  CASE WHEN s < o THEN o ELSE s END AS v
FROM raw_edges
WHERE s <> o;

CREATE TABLE nodes AS
SELECT
  node,
  ROW_NUMBER() OVER (ORDER BY node) - 1 AS id
FROM (
  SELECT u AS node FROM canonical_edges
  UNION
  SELECT v AS node FROM canonical_edges
);

CREATE TABLE edges_id AS
SELECT nu.id AS u, nv.id AS v
FROM canonical_edges e
JOIN nodes nu ON e.u = nu.node
JOIN nodes nv ON e.v = nv.node;

CREATE TABLE degrees AS
SELECT id, COUNT(*) AS degree
FROM (
  SELECT u AS id FROM edges_id
  UNION ALL
  SELECT v AS id FROM edges_id
)
GROUP BY id;
```

Connected components:

- Use a disjoint-set union / union-find.
- Use dense integer IDs from DuckDB.
- Use NumPy arrays or memory maps.
- Process edges in batches.
- Compute:
  - number of roots with nonzero component size;
  - maximum component size;
  - giant component ratio.

## Dependencies to check/install

Need to check whether these are installed:

- `duckdb`
- `numpy`
- optionally `pyarrow`
- optionally `numba`

If `numba` is unavailable, start with a pure-Python/NumPy implementation only if the graph is not too large. Prefer installing `numba` if possible because a Python loop over millions of edges will be too slow.

## Verification plan

1. Run existing synthetic datasets in normal mode to ensure no regression.
2. Run synthetic datasets in large graph mode.
3. Compare exact large graph metrics against NetworkX results on synthetic data:
   - node count;
   - edge count after canonicalisation;
   - average degree;
   - density;
   - component count;
   - giant component size;
   - giant component ratio.
4. Run large graph mode on cleaned OEKG event layer.
5. Save:
   - JSON output;
   - CSV output;
   - DuckDB database;
   - run log/context.

## Thesis reporting implications

The thesis should not say simply that NetworkX failed. It should say:

- the framework was first implemented with NetworkX for small/medium evaluation;
- full real OEKG validation required a different graph-analysis execution strategy;
- RDF-native metrics were evaluated through Jena/SPARQL;
- graph-structure metrics were computed over a declared simple undirected IRI projection;
- exact scalable metrics used out-of-core canonicalisation and streaming union-find;
- clustering was not exact at full scale unless later implemented with sampling;
- edge connectivity was reported only when conditionally exact or replaced with more scalable fragility metrics.

Potential result label categories:

- `Exact-SPARQL`
- `Exact-streaming`
- `Exact-derived`
- `Approximate-sampling`
- `Conditional exact`
- `Not computed`
- `Replacement metric`

## Important caution

The deep-research report contains broken citation placeholders such as `îˆ€cite...`. Do not copy those into the thesis. Before thesis writing, replace them with real citations for:

- DuckDB out-of-core/spilling behaviour;
- disjoint-set union / union-find;
- wedge sampling for clustering;
- edge connectivity/min-cut feasibility;
- external-memory or semi-streaming connected components.
