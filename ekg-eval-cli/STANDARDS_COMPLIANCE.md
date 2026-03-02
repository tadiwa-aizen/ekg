# Industry Standards Compliance

This document details how the EKG Evaluation CLI implements industry-standard algorithms and best practices for knowledge graph evaluation.

## Graph Projection (RDF to Analysis Graph)

### Specification

**Vertices (Nodes):**
- **Include:** IRIs only
- **Exclude:** Literals (values, not entities) and blank nodes (implementation artifacts)
- **Rationale:** Network analysis requires stable entity identifiers
- **Implementation:** `FILTER(isIRI(?s) && isIRI(?o))`

**Edges (Relationships):**
- **Include:** Object properties (IRI-to-IRI triples)
- **Exclude:** Datatype properties (IRI-to-literal triples)
- **Directionality:** Treated as undirected for connectivity metrics
- **Multi-edges:** Collapsed to single edge per node pair
- **Rationale:** Focus on structural relationships, not attribute values

**SPARQL Query:**
```sparql
CONSTRUCT { ?s <urn:link> ?o . }
WHERE { ?s ?p ?o . FILTER(isIRI(?s) && isIRI(?o)) }
```

### References
- RDF 1.1 Concepts: https://www.w3.org/TR/rdf11-concepts/
- Newman, M. (2018). Networks (2nd ed.). Oxford University Press.

---

## Label Normalization

### Specification

Industry-standard normalization for duplicate detection:

1. **Unicode Normalization (NFKD)** - Compatibility decomposition
2. **Diacritic Removal** - Remove combining characters
3. **Case Folding** - More aggressive than lowercase
4. **Punctuation Removal** - Keep alphanumeric and spaces only
5. **Whitespace Normalization** - Collapse multiple spaces, strip

### Implementation

```python
from ekg_eval_cli.label_normalizer import LabelNormalizer

normalized = LabelNormalizer.normalize("World War II")
# Result: "world war ii"
```

### References
- Unicode Standard Annex #15: Unicode Normalization Forms
- Zaveri et al. (2016). Quality assessment for Linked Data

---

## RDFS Inference for Type Consistency

### Specification

Type consistency checking uses SPARQL property paths for RDFS subclass inference:

```sparql
# Check if subject has compatible type (including subclasses)
FILTER NOT EXISTS {
    ?s a ?type .
    ?type rdfs:subClassOf* <expected_domain> .
}
```

The `rdfs:subClassOf*` operator performs transitive closure over subclass relationships.

### Example

If `sem:Event` has subclass `ekgs:TextEvent`, and an instance is typed as `ekgs:TextEvent`, it will correctly validate against domain constraint `sem:Event`.

### References
- SPARQL 1.1 Property Paths: https://www.w3.org/TR/sparql11-query/#propertypaths
- RDF Schema 1.1: https://www.w3.org/TR/rdf-schema/

---

## Configurable Parameters

All evaluation parameters are configurable via CLI or API:

### Fuzzy Matching
- **Threshold:** `--fuzzy-threshold` (default: 0.85)
- **Sample Size:** `--fuzzy-sample-size` (default: 1000)
- **Rationale:** Balances precision/recall for event labels with minor variations

### Temporal Validation
- **Sample Size:** `--temporal-sample-size` (default: 1000)
- **Rationale:** Representative sample for format validation

### Type Consistency
- **Max Properties:** `--max-properties` (default: 50)
- **Rationale:** Balances coverage with performance

### Standard Vocabularies

Configurable allow-list of standard namespaces (default includes):
- RDF, RDFS, OWL, XSD (W3C standards)
- Schema.org, DBpedia, Wikidata (common vocabularies)
- SEM, EventKG (domain-specific)
- FOAF, Dublin Core, SKOS (metadata standards)

---

## Algorithms Used

### Connectivity Metrics
- **Connected Components:** BFS/DFS in O(V+E)
- **Clustering Coefficient:** Watts-Strogatz local clustering
- **Edge Connectivity:** NetworkX (likely Stoer-Wagner or flow-based)

### Temporal Validation
- **ISO 8601 Parsing:** Python `dateutil.parser.isoparse()`
- **Standard:** ISO 8601:2004, XML Schema Part 2

### Fuzzy Matching
- **Algorithm:** RapidFuzz `token_sort_ratio`
- **Complexity:** O(n²) with sampling mitigation
- **Threshold:** Configurable (default 85%)

---

## Known Limitations

### 1. No SHACL Validation
**Status:** Not implemented
**Impact:** Schema conformance uses SPARQL approximation instead of standard SHACL
**Workaround:** SPARQL queries check required properties
**Future:** Consider adding pySHACL integration

### 2. No Equivalence Closure for owl:sameAs
**Status:** Not implemented
**Impact:** Doesn't handle transitive chains (A→B, B→C)
**Workaround:** Direct owl:sameAs links are detected
**Future:** Consider adding Union-Find algorithm

### 3. Sampling for Performance
**Status:** By design
**Impact:** Fuzzy matching and temporal validation use samples
**Rationale:** O(n²) complexity requires sampling for large graphs
**Sample Sizes:** Configurable (defaults: 1000 events)

---

## Compliance Summary

| Metric Category | Compliance | Notes |
|----------------|-----------|-------|
| Graph Connectivity | ✅ Full | Standard algorithms, documented projection |
| Label Normalization | ✅ Full | Industry-standard 5-step normalization |
| RDFS Inference | ✅ Full | SPARQL property paths for subclass reasoning |
| Parameterization | ✅ Full | All thresholds configurable via CLI |
| Temporal Validation | ✅ Full | ISO 8601 / XSD compliance |
| SHACL Validation | ❌ Not Implemented | Uses SPARQL approximation |
| owl:sameAs Closure | ⚠️ Partial | Direct links only, no transitivity |

---

## References

1. Zaveri, A., et al. (2016). Quality assessment for Linked Data: A Survey. *Semantic Web*, 7(1), 63-93.
2. Newman, M. (2018). *Networks* (2nd ed.). Oxford University Press.
3. Christen, P. (2012). *Data Matching*. Springer.
4. W3C RDF 1.1 Concepts: https://www.w3.org/TR/rdf11-concepts/
5. W3C SPARQL 1.1: https://www.w3.org/TR/sparql11-query/
6. ISO 8601:2004 - Data elements and interchange formats
7. Unicode Standard Annex #15: Unicode Normalization Forms
