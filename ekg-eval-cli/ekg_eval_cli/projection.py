"""Canonical RDF-to-graph projection used by structural metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
SEM_EVENT = "http://semanticweb.cs.vu.nl/2009/11/sem/Event"
LINK_PREDICATE = "urn:ekg-eval:domain-link"
NODE_PREDICATE = "urn:ekg-eval:node"

# These predicates describe schema/vocabulary structure rather than links in
# the event domain. In particular, excluding rdf:type prevents all events from
# becoming connected through the shared sem:Event class node.
EXCLUDED_PROJECTION_PREDICATES = frozenset(
    {
        RDF_TYPE,
        "http://www.w3.org/2000/01/rdf-schema#subClassOf",
        "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
        "http://www.w3.org/2000/01/rdf-schema#domain",
        "http://www.w3.org/2000/01/rdf-schema#range",
        "http://www.w3.org/2002/07/owl#equivalentClass",
        "http://www.w3.org/2002/07/owl#equivalentProperty",
        "http://www.w3.org/2002/07/owl#disjointWith",
        "http://www.w3.org/2002/07/owl#imports",
        "http://www.w3.org/2002/07/owl#inverseOf",
        "http://www.w3.org/2002/07/owl#propertyChainAxiom",
        "http://www.w3.org/2002/07/owl#unionOf",
        "http://www.w3.org/2002/07/owl#intersectionOf",
        "http://www.w3.org/2002/07/owl#oneOf",
        "http://www.w3.org/2002/07/owl#complementOf",
    }
)

IRI_TRIPLE_PATTERN = re.compile(
    r"^\s*<([^>]+)>\s+<([^>]+)>\s+<([^>]+)>\s+\.\s*$"
)


@dataclass(frozen=True)
class ProjectionRecord:
    """One parsed IRI-to-IRI triple and its projection role."""

    subject: str
    predicate: str
    object: str

    @property
    def is_direct_event_declaration(self) -> bool:
        return self.predicate == RDF_TYPE and self.object == SEM_EVENT

    @property
    def is_domain_edge(self) -> bool:
        return (
            self.subject != self.object
            and self.predicate not in EXCLUDED_PROJECTION_PREDICATES
        )


def parse_iri_triple(line: str) -> Optional[ProjectionRecord]:
    """Parse an N-Triples line whose subject, predicate, and object are IRIs."""

    match = IRI_TRIPLE_PATTERN.match(line)
    if not match:
        return None
    return ProjectionRecord(match.group(1), match.group(2), match.group(3))


def projection_filter_sparql(variable: str = "?p") -> str:
    """Return the SPARQL NOT IN filter for schema predicates."""

    values = ", ".join(f"<{value}>" for value in sorted(EXCLUDED_PROJECTION_PREDICATES))
    return f"FILTER({variable} NOT IN ({values}))"


PROJECTION_DESCRIPTION = (
    "simple undirected IRI domain-relation projection; schema/type predicates "
    "excluded; direct sem:Event resources retained as isolated nodes"
)
