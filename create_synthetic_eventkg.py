#!/usr/bin/env python3
"""Generate synthetic EventKG dataset with realistic structure."""

from pathlib import Path
from datetime import datetime, timedelta
import random

OUTPUT_DIR = Path("/Users/tadiwaom/Desktop/work/ekg/synthetic-event-kg")
NUM_EVENTS = 100
NUM_TEXT_EVENTS = 50
NUM_ENTITIES = 300

# Namespaces
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

EVENT_NAMES = [
    "World War II", "Moon Landing", "Fall of Berlin Wall", "French Revolution",
    "Industrial Revolution", "Renaissance", "Cold War", "American Civil War",
    "Olympic Games", "World Cup", "Presidential Election", "Royal Wedding",
    "Stock Market Crash", "Earthquake", "Hurricane", "Volcanic Eruption",
    "Scientific Discovery", "Space Mission", "Treaty Signing", "Independence Day"
]

ENTITY_NAMES = [
    "Winston Churchill", "Albert Einstein", "Marie Curie", "Nelson Mandela",
    "London", "Paris", "New York", "Tokyo", "Berlin", "Moscow",
    "United Nations", "European Union", "NATO", "World Bank",
    "Atlantic Ocean", "Pacific Ocean", "Mount Everest", "Sahara Desert"
]

def write_triple(f, s, p, o):
    """Write N-Triple."""
    f.write(f"<{s}> <{p}> {o} .\n")

def random_date():
    """Generate random date between 1900-2023."""
    start = datetime(1900, 1, 1)
    end = datetime(2023, 12, 31)
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def format_date(date, granularity='day'):
    """Format date with granularity."""
    if granularity == 'year':
        return f'"{date.year}-01-01"^^<{XSD}date>'
    elif granularity == 'month':
        return f'"{date.year}-{date.month:02d}-01"^^<{XSD}date>'
    else:
        return f'"{date.year}-{date.month:02d}-{date.day:02d}"^^<{XSD}date>'

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Generating synthetic EventKG at {OUTPUT_DIR}")
    
    # Generate events.nt
    print("\n[1/15] events.nt")
    with open(OUTPUT_DIR / "events.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            event_id = f"{EKG}event_{2595270 + i}"
            name = random.choice(EVENT_NAMES)
            
            write_triple(f, event_id, f"{RDF}type", f"<{SEM}Event>")
            write_triple(f, event_id, f"{OWL}sameAs", f"<{WD}Q{random.randint(1000, 999999)}>")
            write_triple(f, event_id, f"{OWL}sameAs", f"<{DBR}{name.replace(' ', '_')}>")
            f.write(f'<{event_id}> <{RDFS}label> "{name}"@en .\n')
            
            if random.random() > 0.5:
                f.write(f'<{event_id}> <{RDFS}label> "{name} (de)"@de .\n')
    
    # Generate text_events.nt
    print("[2/15] text_events.nt")
    with open(OUTPUT_DIR / "text_events.nt", 'w') as f:
        for i in range(NUM_TEXT_EVENTS):
            event_id = f"{EKG}event_{2892396 + i}"
            name = random.choice(EVENT_NAMES)
            date = random_date()
            granularity = random.choice(['year', 'month', 'day'])
            
            write_triple(f, event_id, f"{RDF}type", f"<{EKGS}TextEvent>")
            write_triple(f, event_id, f"{EKGS}extractedFrom", f"<https://en.wikipedia.org/wiki/{name.replace(' ', '_')}>")
            f.write(f'<{event_id}> <{SEM}hasBeginTimeStamp> {format_date(date, granularity)} .\n')
            write_triple(f, event_id, f"{EKGS}startUnitType", f"<{TIME}unit{granularity.capitalize()}>")
            f.write(f'<{event_id}> <{DCTERMS}description> "Description of {name}."@en .\n')
            
            # Link to entities
            for _ in range(random.randint(1, 3)):
                entity_id = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
                write_triple(f, event_id, f"{SEM}hasActor", f"<{entity_id}>")
    
    # Generate entities.nt
    print("[3/15] entities.nt")
    with open(OUTPUT_DIR / "entities.nt", 'w') as f:
        for i in range(NUM_ENTITIES):
            entity_id = f"{EKG}entity_{i}"
            name = random.choice(ENTITY_NAMES)
            
            write_triple(f, entity_id, f"{RDF}type", f"<{SEM}Actor>")
            write_triple(f, entity_id, f"{OWL}sameAs", f"<{WD}Q{random.randint(1000, 999999)}>")
            f.write(f'<{entity_id}> <{RDFS}label> "{name}"@en .\n')
    
    # Generate relations_events_base.nt
    print("[4/15] relations_events_base.nt")
    with open(OUTPUT_DIR / "relations_events_base.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            event_id = f"{EKG}event_{2595270 + i}"
            date = random_date()
            granularity = random.choice(['year', 'month', 'day'])
            
            f.write(f'<{event_id}> <{SEM}hasBeginTimeStamp> {format_date(date, granularity)} .\n')
            write_triple(f, event_id, f"{EKGS}startUnitType", f"<{TIME}unit{granularity.capitalize()}>")
            
            if random.random() > 0.5:
                end_date = date + timedelta(days=random.randint(1, 365))
                f.write(f'<{event_id}> <{SEM}hasEndTimeStamp> {format_date(end_date, granularity)} .\n')
                write_triple(f, event_id, f"{EKGS}endUnitType", f"<{TIME}unit{granularity.capitalize()}>")
    
    # Generate relations_events_other.nt
    print("[5/15] relations_events_other.nt")
    with open(OUTPUT_DIR / "relations_events_other.nt", 'w') as f:
        for i in range(200):
            relation_id = f"{EKG}relation_{i}"
            event_id = f"{EKG}event_{2595270 + random.randint(0, NUM_EVENTS-1)}"
            entity_id = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            prop = random.choice([f"{WDP}P710", f"{WDP}P276", f"{WDP}P17", f"{WDP}P170"])
            
            write_triple(f, relation_id, f"{RDF}type", f"<{EKGS}Relation>")
            write_triple(f, relation_id, f"{RDF}subject", f"<{event_id}>")
            write_triple(f, relation_id, f"{RDF}object", f"<{entity_id}>")
            write_triple(f, relation_id, f"{SEM}roleType", f"<{prop}>")
    
    # Generate relations_events_literals.nt
    print("[6/15] relations_events_literals.nt")
    with open(OUTPUT_DIR / "relations_events_literals.nt", 'w') as f:
        for i in range(NUM_EVENTS // 2):
            event_id = f"{EKG}event_{2595270 + i}"
            f.write(f'<{event_id}> <{RDFS}comment> "Description of event {i}."@en .\n')
    
    # Generate relations_entities_base.nt
    print("[7/15] relations_entities_base.nt")
    with open(OUTPUT_DIR / "relations_entities_base.nt", 'w') as f:
        for i in range(100):
            relation_id = f"{EKG}relation_{1000 + i}"
            subj = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            obj = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            
            write_triple(f, relation_id, f"{RDF}type", f"<{EKGS}Relation>")
            write_triple(f, relation_id, f"{RDF}subject", f"<{subj}>")
            write_triple(f, relation_id, f"{RDF}object", f"<{obj}>")
            write_triple(f, relation_id, f"{SEM}roleType", f"<{WDP}P26>")
    
    # Generate relations_entities_temporal.nt
    print("[8/15] relations_entities_temporal.nt")
    with open(OUTPUT_DIR / "relations_entities_temporal.nt", 'w') as f:
        for i in range(80):
            relation_id = f"{EKG}relation_{2000 + i}"
            subj = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            obj = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            date = random_date()
            
            write_triple(f, relation_id, f"{RDF}type", f"<{EKGS}Relation>")
            write_triple(f, relation_id, f"{RDF}subject", f"<{subj}>")
            write_triple(f, relation_id, f"{RDF}object", f"<{obj}>")
            write_triple(f, relation_id, f"{SEM}roleType", f"<{WDP}P54>")
            f.write(f'<{relation_id}> <{SEM}hasBeginTimeStamp> {format_date(date)} .\n')
            write_triple(f, relation_id, f"{EKGS}startUnitType", f"<{TIME}unitDay>")
    
    # Generate relations_entities_other.nt
    print("[9/15] relations_entities_other.nt")
    with open(OUTPUT_DIR / "relations_entities_other.nt", 'w') as f:
        for i in range(60):
            subj = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            obj = f"{EKG}entity_{random.randint(0, NUM_ENTITIES-1)}"
            prop = random.choice([f"{WDP}P27", f"{WDP}P19", f"{WDP}P20"])
            write_triple(f, subj, prop, f"<{obj}>")
    
    # Generate types.nt
    print("[10/15] types.nt")
    with open(OUTPUT_DIR / "types.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            event_id = f"{EKG}event_{2595270 + i}"
            write_triple(f, event_id, f"{RDF}type", f"<{SEM}Event>")
        for i in range(NUM_TEXT_EVENTS):
            event_id = f"{EKG}event_{2892396 + i}"
            write_triple(f, event_id, f"{RDF}type", f"<{EKGS}TextEvent>")
        for i in range(NUM_ENTITIES):
            entity_id = f"{EKG}entity_{i}"
            write_triple(f, entity_id, f"{RDF}type", f"<{SEM}Actor>")
    
    # Generate preferred_labels.nt
    print("[11/15] preferred_labels.nt")
    with open(OUTPUT_DIR / "preferred_labels.nt", 'w') as f:
        for i in range(NUM_EVENTS):
            event_id = f"{EKG}event_{2595270 + i}"
            name = random.choice(EVENT_NAMES)
            f.write(f'<{event_id}> <{RDFS}label> "{name}"@en .\n')
        for i in range(NUM_ENTITIES):
            entity_id = f"{EKG}entity_{i}"
            name = random.choice(ENTITY_NAMES)
            f.write(f'<{entity_id}> <{RDFS}label> "{name}"@en .\n')
    
    # Generate events_first_sentences.nt
    print("[12/15] events_first_sentences.nt")
    with open(OUTPUT_DIR / "events_first_sentences.nt", 'w') as f:
        for i in range(NUM_EVENTS // 3):
            event_id = f"{EKG}event_{2595270 + i}"
            f.write(f'<{event_id}> <{DCTERMS}description> "First sentence about event {i}."@en .\n')
    
    # Generate events_descriptions_from_text_events.nt
    print("[13/15] events_descriptions_from_text_events.nt")
    with open(OUTPUT_DIR / "events_descriptions_from_text_events.nt", 'w') as f:
        for i in range(NUM_TEXT_EVENTS // 2):
            event_id = f"{EKG}event_{2892396 + i}"
            f.write(f'<{event_id}> <{DCTERMS}description> "Description from text event {i}."@en .\n')
    
    # Generate property_labels.nt
    print("[14/15] property_labels.nt")
    with open(OUTPUT_DIR / "property_labels.nt", 'w') as f:
        props = [
            (f"{WDP}P710", "participant"),
            (f"{WDP}P276", "location"),
            (f"{WDP}P17", "country"),
            (f"{WDP}P170", "creator"),
            (f"{WDP}P26", "spouse"),
            (f"{WDP}P54", "member of")
        ]
        for prop, label in props:
            f.write(f'<{prop}> <{RDFS}label> "{label}"@en .\n')
    
    # Generate types_ontology_dbpedia.nt
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
            with open(source) as f:
                content = f.read()
            with open(OUTPUT_DIR / filename, 'w') as f:
                f.write(content)
            print(f"  Copied {filename}")
    
    # Summary
    total_size = sum(f.stat().st_size for f in OUTPUT_DIR.glob('*'))
    print(f"\n✅ Synthetic EventKG created!")
    print(f"   Location: {OUTPUT_DIR}")
    print(f"   Size: {total_size / 1024:.1f} KB")
    print(f"   Files: {len(list(OUTPUT_DIR.glob('*.nt')))} .nt files")

if __name__ == '__main__':
    main()
