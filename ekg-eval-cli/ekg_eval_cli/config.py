"""Configurable evaluation parameters with documented defaults."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class EvaluationParameters:
    """
    Configurable parameters for EKG evaluation.
    
    Parameters are thesis-defined operational settings and can be overridden
    via the CLI or API. Result files record the values used for each run.
    
    References:
        - Fuzzy matching thresholds: Christen (2012) - Data Matching
        - Sampling strategies: Cochran (1977) - Sampling Techniques
    """
    
    # Fuzzy matching parameters
    fuzzy_similarity_threshold: float = 0.90
    """Similarity threshold for fuzzy duplicate detection (0.0-1.0).
    Default: 0.90 (90% token-sort similarity)
    Rationale: Conservative candidate threshold used consistently in the thesis.
    """
    
    fuzzy_sample_size: int = 1000
    """Number of events to sample for fuzzy matching.
    Default: 1000
    Rationale: O(n²) complexity requires sampling for large graphs.
    """
    
    # Temporal validation parameters
    temporal_sample_size: int = 1000
    """Number of temporal relations to sample for validation.
    Default: 1000
    Rationale: Bounds endpoint work. Sampling metadata is reported; a sample
    is not called representative without a statistical design.
    """
    
    # Type consistency parameters
    max_properties_analyzed: int = 50
    """Maximum properties to analyze for type consistency.
    Default: 50
    Rationale: Balances coverage with performance.
    """
    
    # Standard vocabulary allow-list
    standard_namespaces: List[str] = field(default_factory=lambda: [
        'http://www.w3.org/1999/02/22-rdf-syntax-ns#',      # RDF
        'http://www.w3.org/2000/01/rdf-schema#',            # RDFS
        'http://www.w3.org/2002/07/owl#',                   # OWL
        'http://www.w3.org/2001/XMLSchema#',                # XSD
        'http://schema.org/',                                # Schema.org
        'http://dbpedia.org/ontology/',                     # DBpedia
        'http://www.wikidata.org/entity/',                  # Wikidata
        'http://semanticweb.cs.vu.nl/2009/11/sem/',        # SEM
        'https://eventkg.l3s.uni-hannover.de/schema/',     # EventKG
        'http://xmlns.com/foaf/0.1/',                       # FOAF
        'http://purl.org/dc/elements/1.1/',                 # Dublin Core
        'http://www.w3.org/2004/02/skos/core#'             # SKOS
    ])
    """List of standard vocabulary namespaces.
    Properties from these namespaces are considered 'standard'.
    Properties from other namespaces are flagged as 'non-standard'.
    """
    
    def validate(self) -> None:
        """Validate parameter values."""
        if not 0.0 <= self.fuzzy_similarity_threshold <= 1.0:
            raise ValueError(
                f"fuzzy_similarity_threshold must be between 0.0 and 1.0, "
                f"got {self.fuzzy_similarity_threshold}"
            )
        
        if self.fuzzy_sample_size < 1:
            raise ValueError(
                f"fuzzy_sample_size must be positive, got {self.fuzzy_sample_size}"
            )
        
        if self.temporal_sample_size < 1:
            raise ValueError(
                f"temporal_sample_size must be positive, got {self.temporal_sample_size}"
            )
        
        if self.max_properties_analyzed < 1:
            raise ValueError(
                f"max_properties_analyzed must be positive, got {self.max_properties_analyzed}"
            )
