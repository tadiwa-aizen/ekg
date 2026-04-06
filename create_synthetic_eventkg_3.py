#!/usr/bin/env python3
"""Generate synthetic-event-kg-3: valid but low-quality EKG.

Scores poorly across ALL 9 evaluation dimensions while remaining
a structurally valid EventKG-format dataset.
"""

from pathlib import Path
from datetime import datetime, timedelta
import random

random.seed(42)

OUTPUT_DIR = Path("/Users/tadiwaom/Desktop/work/ekg/synthetic-event-kg-3")
NUM_EVENTS = 120
NUM_TEXT_EVENTS = 30
NUM_ENTITIES = 80

EKG = "https://eventkg.l3s.uni-hannover.de/resource/"
EKGS = "https://eventkg.l3s.uni-hannover.de/schema/"
SEM = "http://semanticweb.cs.vu.nl/2009/11/sem/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
WD = "http://www.wikidata.org/entity/"
WDP = "http://www.wikidata.org/prop/direct/"
DBR = "http://dbpedia.org/resource/"
DCTERMS = "http://purl.org/dc/terms/"
TIME = "http://www.w3.org/2006/time#"

# Only 3 names = terrible label uniqueness
EVENT_NAMES = ["War", "Election", "Disaster"]
ENTITY_NAMES = ["Person", "Place", "Organization"]


def write_triple(f, s, p, o):
    f.write(f"<{s}> <{p}> {o} .\n")


def random_date_clustered():
    """75% of dates in 1950s, 25% scattered."""
    if random.random() < 0.75:
        start, end = datetime(1950, 1, 1), datetime(1959, 12, 31)
    else:
        start, end = datetime(1900, 1, 1), datetime(2023, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def format_date(date, granularity='day'):
    if granularity == 'year':
        return f'"{date.year}"^^<{XSD}gYear>'
    else:
        return f'"{date.year}-{date.month:02d}-{date.day:02d}"^^<{XSD}date>'


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Generating synthetic-event-kg-3 (low quality)...")

    # events.nt — 30% missing labels, ~20% get sameAs
    print("[1/15] events.nt")
    with open(OUTPUT_DIR / "events.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            eid = f"{EKG}event_{4000000 + i}"
            name = random.choice(EVENT_NAMES)
            write_triple(f, eid, f"{RDF}type", f"<{SEM}Event>")
            if random.random() < 0.70:
                f.write(f'<{eid}> <{RDFS}label> "{name}"@en .\n')
            if random.random() < 0.10:
                write_triple(f, eid, f"{OWL}sameAs", f"<{WD}Q{random.randint(1000, 999999)}>")
            if random.random() < 0.10:
                write_triple(f, eid, f"{OWL}sameAs", f"<{DBR}{name}>")

    # text_events.nt — minimal, no dates/descriptions/actors
    print("[2/15] text_events.nt")
    with open(OUTPUT_DIR / "text_events.nt", 'w') as f:
        for i in range(NUM_TEXT_EVENTS):
            eid = f"{EKG}event_{4500000 + i}"
            write_triple(f, eid, f"{RDF}type", f"<{EKGS}TextEvent>")
            write_triple(f, eid, f"{EKGS}extractedFrom",
                         f"<https://en.wikipedia.org/wiki/{random.choice(EVENT_NAMES)}>")

    # entities.nt — mostly disconnected from events
    print("[3/15] entities.nt")
    with open(OUTPUT_DIR / "entities.nt", 'w') as f:
        for i in range(NUM_ENTITIES):
            entity_id = f"{EKG}entity_{i}"
            write_triple(f, entity_id, f"{RDF}type", f"<{SEM}Actor>")
            f.write(f'<{entity_id}> <{RDFS}label> "{random.choice(ENTITY_NAMES)}"@en .\n')

    # relations_events_base.nt — only 60% get dates, 50% year-only, clustered in 1950s
    print("[4/15] relations_events_base.nt")
    with open(OUTPUT_DIR / "relations_events_base.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            eid = f"{EKG}event_{4000000 + i}"
            if random.random() < 0.60:
                date = random_date_clustered()
                gran = 'year' if random.random() < 0.50 else 'day'
                f.write(f'<{eid}> <{SEM}hasBeginTimeStamp> {format_date(date, gran)} .\n')
                write_triple(f, eid, f"{EKGS}startUnitType",
                             f"<{TIME}unit{gran.capitalize()}>")

    # relations_events_other.nt — only 20 relations, only first 10 events → first 5 entities
    print("[5/15] relations_events_other.nt")
    with open(OUTPUT_DIR / "relations_events_other.nt", 'w') as f:
        for i in range(20):
            rid = f"{EKG}relation_{i}"
            eid = f"{EKG}event_{4000000 + random.randint(0, 9)}"
            entity_id = f"{EKG}entity_{random.randint(0, 4)}"
            write_triple(f, rid, f"{RDF}type", f"<{EKGS}Relation>")
            write_triple(f, rid, f"{RDF}subject", f"<{eid}>")
            write_triple(f, rid, f"{RDF}object", f"<{entity_id}>")
            write_triple(f, rid, f"{SEM}roleType", f"<{WDP}P710>")

    # relations_events_literals.nt — almost empty
    print("[6/15] relations_events_literals.nt")
    with open(OUTPUT_DIR / "relations_events_literals.nt", 'w') as f:
        for i in range(5):
            eid = f"{EKG}event_{4000000 + i}"
            f.write(f'<{eid}> <{RDFS}comment> "Comment."@en .\n')

    # relations_entities_base.nt — tiny, isolated cluster
    print("[7/15] relations_entities_base.nt")
    with open(OUTPUT_DIR / "relations_entities_base.nt", 'w') as f:
        for i in range(10):
            rid = f"{EKG}relation_{1000 + i}"
            write_triple(f, rid, f"{RDF}type", f"<{EKGS}Relation>")
            write_triple(f, rid, f"{RDF}subject", f"<{EKG}entity_{random.randint(0, 4)}>")
            write_triple(f, rid, f"{RDF}object", f"<{EKG}entity_{random.randint(0, 4)}>")
            write_triple(f, rid, f"{SEM}roleType", f"<{WDP}P26>")

    # relations_entities_temporal.nt — tiny
    print("[8/15] relations_entities_temporal.nt")
    with open(OUTPUT_DIR / "relations_entities_temporal.nt", 'w') as f:
        for i in range(5):
            rid = f"{EKG}relation_{2000 + i}"
            date = random_date_clustered()
            write_triple(f, rid, f"{RDF}type", f"<{EKGS}Relation>")
            write_triple(f, rid, f"{RDF}subject", f"<{EKG}entity_{random.randint(0, 4)}>")
            write_triple(f, rid, f"{RDF}object", f"<{EKG}entity_{random.randint(0, 4)}>")
            write_triple(f, rid, f"{SEM}roleType", f"<{WDP}P54>")
            f.write(f'<{rid}> <{SEM}hasBeginTimeStamp> {format_date(date)} .\n')

    # relations_entities_other.nt — tiny
    print("[9/15] relations_entities_other.nt")
    with open(OUTPUT_DIR / "relations_entities_other.nt", 'w') as f:
        for i in range(5):
            write_triple(f, f"{EKG}entity_{random.randint(0, 4)}",
                         f"{WDP}P27", f"<{EKG}entity_{random.randint(0, 4)}>")

    # types.nt
    print("[10/15] types.nt")
    with open(OUTPUT_DIR / "types.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            write_triple(f, f"{EKG}event_{4000000 + i}", f"{RDF}type", f"<{SEM}Event>")
        for i in range(NUM_TEXT_EVENTS):
            write_triple(f, f"{EKG}event_{4500000 + i}", f"{RDF}type", f"<{EKGS}TextEvent>")
        for i in range(NUM_ENTITIES):
            write_triple(f, f"{EKG}entity_{i}", f"{RDF}type", f"<{SEM}Actor>")

    # preferred_labels.nt — only 70% get labels (match events.nt gaps)
    print("[11/15] preferred_labels.nt")
    with open(OUTPUT_DIR / "preferred_labels.nt", 'w') as f:
        random.seed(42)  # Same seed as events.nt so the 30% gaps align
        for i in range(NUM_EVENTS):
            name = random.choice(EVENT_NAMES)
            if random.random() < 0.70:  # Same 70% threshold as events.nt
                f.write(f'<{EKG}event_{4000000 + i}> <{RDFS}label> "{name}"@en .\n')
        for i in range(NUM_ENTITIES):
            f.write(f'<{EKG}entity_{i}> <{RDFS}label> "{random.choice(ENTITY_NAMES)}"@en .\n')

    # events_first_sentences.nt — only 5
    print("[12/15] events_first_sentences.nt")
    with open(OUTPUT_DIR / "events_first_sentences.nt", 'w') as f:
        for i in range(5):
            f.write(f'<{EKG}event_{4000000 + i}> <{DCTERMS}description> "A thing happened."@en .\n')

    # events_descriptions_from_text_events.nt — only 3
    print("[13/15] events_descriptions_from_text_events.nt")
    with open(OUTPUT_DIR / "events_descriptions_from_text_events.nt", 'w') as f:
        for i in range(3):
            f.write(f'<{EKG}event_{4500000 + i}> <{DCTERMS}description> "Text event."@en .\n')

    # property_labels.nt
    print("[14/15] property_labels.nt")
    with open(OUTPUT_DIR / "property_labels.nt", 'w') as f:
        f.write(f'<{WDP}P710> <{RDFS}label> "participant"@en .\n')
        f.write(f'<{WDP}P26> <{RDFS}label> "spouse"@en .\n')
        f.write(f'<{WDP}P54> <{RDFS}label> "member of"@en .\n')

    # types_ontology_dbpedia.nt
    print("[15/15] types_ontology_dbpedia.nt")
    with open(OUTPUT_DIR / "types_ontology_dbpedia.nt", 'w') as f:
        write_triple(f, "http://dbpedia.org/ontology/Event", f"{RDFS}subClassOf", f"<{SEM}Event>")
        write_triple(f, "http://dbpedia.org/ontology/Person", f"{RDFS}subClassOf", f"<{SEM}Actor>")

    # Copy schema files from real EventKG
    print("\nCopying schema files...")
    source_dir = Path("/Users/tadiwaom/Desktop/work/ekg/event-kg")
    for filename in ["schema.ttl", "schema.nt", "void.ttl", "graphs.ttl"]:
        source = source_dir / filename
        if source.exists():
            with open(source) as sf:
                content = sf.read()
            with open(OUTPUT_DIR / filename, 'w') as df:
                df.write(content)
            print(f"  Copied {filename}")

    total_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob('*'))
    print(f"\n✅ synthetic-event-kg-3 created!")
    print(f"   Location: {OUTPUT_DIR}")
    print(f"   Size: {total_size / 1024:.1f} KB")


if __name__ == '__main__':
    main()
