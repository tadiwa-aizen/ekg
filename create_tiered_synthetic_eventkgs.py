#!/usr/bin/env python3
"""Generate three deterministic synthetic EventKG-style datasets.

The profiles are intentionally tiered for evaluation validation:
dataset 1 is high quality, dataset 2 is medium quality, and dataset 3 is
low quality. The generated files follow the same file layout as the earlier
synthetic EventKG folders so the existing CLI can evaluate them unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import random
import shutil
import json


ROOT = Path(__file__).resolve().parent

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

FILES = [
    "events.nt",
    "text_events.nt",
    "entities.nt",
    "relations_events_base.nt",
    "relations_events_other.nt",
    "relations_events_literals.nt",
    "relations_entities_base.nt",
    "relations_entities_temporal.nt",
    "relations_entities_other.nt",
    "types.nt",
    "preferred_labels.nt",
    "events_first_sentences.nt",
    "events_descriptions_from_text_events.nt",
    "property_labels.nt",
    "types_ontology_dbpedia.nt",
    "schema.nt",
    "schema.ttl",
    "void.ttl",
    "graphs.ttl",
]


@dataclass(frozen=True)
class Profile:
    folder: str
    event_prefix: int
    text_prefix: int
    events: int
    text_events: int
    entities: int
    label_rate: float
    date_rate: float
    place_rate: float
    external_rate: float
    description_rate: float
    relation_rate: float
    relation_min: int
    relation_max: int
    unique_name_count: int
    near_variant_rate: float = 0.0
    type_error_rate: float = 0.0
    interval_rate: float = 0.0
    invalid_interval_rate: float = 0.0
    clustered_dates: bool = False
    year_only_rate: float = 0.0


PROFILES = [
    Profile(
        folder="synthetic-event-kg",
        event_prefix=2600000,
        text_prefix=2900000,
        events=100,
        text_events=40,
        entities=320,
        label_rate=1.00,
        date_rate=1.00,
        place_rate=0.95,
        external_rate=1.00,
        description_rate=0.90,
        relation_rate=0.95,
        relation_min=3,
        relation_max=5,
        unique_name_count=100,
        near_variant_rate=0.00,
        type_error_rate=0.00,
        interval_rate=0.80,
        invalid_interval_rate=0.00,
    ),
    Profile(
        folder="synthetic-event-kg-2",
        event_prefix=3000000,
        text_prefix=3500000,
        events=120,
        text_events=35,
        entities=180,
        label_rate=0.75,
        date_rate=0.70,
        place_rate=0.55,
        external_rate=0.60,
        description_rate=0.50,
        relation_rate=0.65,
        relation_min=1,
        relation_max=3,
        unique_name_count=55,
        near_variant_rate=0.20,
        type_error_rate=0.25,
        interval_rate=0.60,
        invalid_interval_rate=0.15,
        clustered_dates=False,
        year_only_rate=0.20,
    ),
    Profile(
        folder="synthetic-event-kg-3",
        event_prefix=4000000,
        text_prefix=4500000,
        events=120,
        text_events=25,
        entities=80,
        label_rate=0.45,
        date_rate=0.40,
        place_rate=0.10,
        external_rate=0.12,
        description_rate=0.10,
        relation_rate=0.20,
        relation_min=0,
        relation_max=1,
        unique_name_count=8,
        near_variant_rate=0.60,
        type_error_rate=0.75,
        interval_rate=0.40,
        invalid_interval_rate=0.50,
        clustered_dates=True,
        year_only_rate=0.55,
    ),
]


def uri(value: str) -> str:
    return f"<{value}>"


def triple(f, s: str, p: str, o: str) -> None:
    f.write(f"{uri(s)} {uri(p)} {o} .\n")


def literal(value: str, lang: str | None = None) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    suffix = f"@{lang}" if lang else ""
    return f'"{escaped}"{suffix}'


def date_literal(date: datetime, year_only: bool) -> str:
    if year_only:
        return f'"{date.year}"^^{uri(XSD + "gYear")}'
    return f'"{date.year}-{date.month:02d}-{date.day:02d}"^^{uri(XSD + "date")}'


def random_date(rng: random.Random, clustered: bool) -> datetime:
    if clustered and rng.random() < 0.75:
        start, end = datetime(1950, 1, 1), datetime(1959, 12, 31)
    else:
        start, end = datetime(1900, 1, 1), datetime(2023, 12, 31)
    return start + timedelta(days=rng.randint(0, (end - start).days))


EVENT_MODIFIERS = [
    "Aurora", "Borealis", "Cedar", "Delta", "Emerald", "Frontier", "Granite",
    "Harbour", "Ivory", "Juniper", "Kestrel", "Lagoon", "Meridian", "Nimbus",
    "Orchid", "Pioneer", "Quartz", "Riverton", "Solstice", "Tamarind",
]
EVENT_TOPICS = [
    "Accord", "Assembly", "Biennale", "Congress", "Discovery", "Election",
    "Exhibition", "Festival", "Flood", "Forum", "Launch", "Marathon", "Mission",
    "Referendum", "Rescue", "Summit", "Tournament", "Tribunal", "Volcanic Eruption",
    "Workshop",
]


def event_name(index: int, unique_count: int, near_variant_rate: float = 0.0) -> str:
    base_index = index % unique_count
    modifier = EVENT_MODIFIERS[base_index % len(EVENT_MODIFIERS)]
    topic = EVENT_TOPICS[
        (base_index * 7 + base_index // len(EVENT_MODIFIERS)) % len(EVENT_TOPICS)
    ]
    base = f"{modifier} {topic}"
    if index >= unique_count:
        cycle_position = ((index - unique_count) % 100) / 100
        if cycle_position < near_variant_rate:
            return base + "s"
    return base


def entity_name(index: int) -> str:
    return f"Synthetic Entity {index:03d}"


def clean_output(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        target = folder / filename
        if target.exists():
            target.unlink()
    db = folder / "databases"
    if db.exists():
        shutil.rmtree(db)


def copy_or_write_schema(folder: Path, output_root: Path) -> None:
    source = output_root / "synthetic-event-kg" / "schema.nt"
    if source.exists() and source.parent != folder:
        for filename in ["schema.nt", "schema.ttl", "void.ttl", "graphs.ttl"]:
            src = source.parent / filename
            if src.exists():
                shutil.copyfile(src, folder / filename)
    else:
        with (folder / "schema.nt").open("w", encoding="utf-8") as f:
            triple(f, SEM + "Event", RDFS + "subClassOf", uri(SEM + "Event"))
            triple(f, EKGS + "TextEvent", RDFS + "subClassOf", uri(SEM + "Event"))
            for cls in ["MilitaryEvent", "PoliticalEvent", "CulturalEvent"]:
                triple(f, EKGS + cls, RDFS + "subClassOf", uri(SEM + "Event"))
            triple(f, SEM + "hasPlace", RDFS + "domain", uri(SEM + "Event"))
            triple(f, SEM + "hasPlace", RDFS + "range", uri(SEM + "Place"))
        (folder / "schema.ttl").write_text(
            "@prefix sem: <http://semanticweb.cs.vu.nl/2009/11/sem/> .\n"
            "@prefix ekgs: <https://eventkg.l3s.uni-hannover.de/schema/> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "ekgs:TextEvent rdfs:subClassOf sem:Event .\n"
            "ekgs:MilitaryEvent rdfs:subClassOf sem:Event .\n"
            "ekgs:PoliticalEvent rdfs:subClassOf sem:Event .\n"
            "ekgs:CulturalEvent rdfs:subClassOf sem:Event .\n"
            "sem:hasPlace rdfs:domain sem:Event ; rdfs:range sem:Place .\n",
            encoding="utf-8",
        )
        (folder / "void.ttl").write_text("", encoding="utf-8")
        (folder / "graphs.ttl").write_text("", encoding="utf-8")


def generate(profile: Profile, output_root: Path = ROOT) -> None:
    rng = random.Random(profile.event_prefix)
    folder = output_root / profile.folder
    clean_output(folder)
    copy_or_write_schema(folder, output_root)

    labels: dict[int, str] = {}
    dates: dict[int, datetime] = {}
    places: dict[int, int] = {}
    linked: set[int] = set()
    place_entity_count = max(5, profile.entities // 5)

    with (folder / "events.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.events):
            eid = EKG + f"event_{profile.event_prefix + i}"
            name = event_name(i, profile.unique_name_count, profile.near_variant_rate)
            triple(f, eid, RDF + "type", uri(SEM + "Event"))
            if rng.random() < profile.label_rate:
                labels[i] = name
                f.write(f"{uri(eid)} {uri(RDFS + 'label')} {literal(name, 'en')} .\n")
            if rng.random() < profile.external_rate:
                linked.add(i)
                triple(f, eid, OWL + "sameAs", uri(WD + f"Q{profile.event_prefix + i}"))
                if rng.random() < 0.85:
                    triple(f, eid, OWL + "sameAs", uri(DBR + name.replace(" ", "_")))

    with (folder / "relations_events_base.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.events):
            eid = EKG + f"event_{profile.event_prefix + i}"
            if rng.random() < profile.date_rate:
                date = random_date(rng, profile.clustered_dates)
                dates[i] = date
                year_only = rng.random() < profile.year_only_rate
                f.write(f"{uri(eid)} {uri(SEM + 'hasBeginTimeStamp')} {date_literal(date, year_only)} .\n")
                if rng.random() < profile.interval_rate:
                    invalid_interval = rng.random() < profile.invalid_interval_rate
                    if year_only:
                        end_year = date.year - 1 if invalid_interval else date.year + 1
                        end_date = datetime(end_year, 1, 1)
                    else:
                        offset = timedelta(days=rng.randint(3, 180))
                        end_date = date - offset if invalid_interval else date + offset
                    f.write(
                        f"{uri(eid)} {uri(SEM + 'hasEndTimeStamp')} "
                        f"{date_literal(end_date, year_only)} .\n"
                    )
                unit = "unitYear" if year_only else "unitDay"
                triple(f, eid, EKGS + "startUnitType", uri(TIME + unit))
            if rng.random() < profile.place_rate:
                if rng.random() < profile.type_error_rate:
                    place_id = rng.randint(place_entity_count, profile.entities - 1)
                else:
                    place_id = rng.randint(0, place_entity_count - 1)
                places[i] = place_id
                triple(f, eid, SEM + "hasPlace", uri(EKG + f"entity_{place_id}"))

    with (folder / "relations_events_other.nt").open("w", encoding="utf-8") as f:
        relation_id = 0
        for i in range(profile.events):
            if rng.random() >= profile.relation_rate:
                continue
            count = rng.randint(profile.relation_min, profile.relation_max)
            for _ in range(count):
                rid = EKG + f"relation_{relation_id}"
                eid = EKG + f"event_{profile.event_prefix + i}"
                ent = EKG + f"entity_{rng.randint(0, profile.entities - 1)}"
                triple(f, rid, RDF + "type", uri(EKGS + "Relation"))
                triple(f, rid, RDF + "subject", uri(eid))
                triple(f, rid, RDF + "object", uri(ent))
                triple(f, rid, SEM + "roleType", uri(rng.choice([WDP + "P710", WDP + "P276", WDP + "P17"])))
                relation_id += 1

    with (folder / "relations_events_literals.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.events):
            if rng.random() < profile.description_rate:
                eid = EKG + f"event_{profile.event_prefix + i}"
                f.write(f"{uri(eid)} {uri(RDFS + 'comment')} {literal(f'Description of {event_name(i, profile.unique_name_count, profile.near_variant_rate)}.', 'en')} .\n")

    with (folder / "entities.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.entities):
            ent = EKG + f"entity_{i}"
            entity_type = "Place" if i < place_entity_count else "Actor"
            triple(f, ent, RDF + "type", uri(SEM + entity_type))
            f.write(f"{uri(ent)} {uri(RDFS + 'label')} {literal(entity_name(i), 'en')} .\n")
            if i < int(profile.entities * profile.external_rate):
                triple(f, ent, OWL + "sameAs", uri(WD + f"Q{900000 + i}"))

    with (folder / "text_events.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.text_events):
            eid = EKG + f"event_{profile.text_prefix + i}"
            name = f"Text {event_name(i, profile.unique_name_count)}"
            triple(f, eid, RDF + "type", uri(EKGS + "TextEvent"))
            triple(f, eid, EKGS + "extractedFrom", uri(f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}"))
            if rng.random() < profile.label_rate:
                f.write(f"{uri(eid)} {uri(RDFS + 'label')} {literal(name, 'en')} .\n")
            if rng.random() < profile.date_rate:
                date = random_date(rng, profile.clustered_dates)
                year_only = rng.random() < profile.year_only_rate
                f.write(f"{uri(eid)} {uri(SEM + 'hasBeginTimeStamp')} {date_literal(date, year_only)} .\n")
                unit = "unitYear" if year_only else "unitDay"
                triple(f, eid, EKGS + "startUnitType", uri(TIME + unit))
            if rng.random() < profile.place_rate:
                if rng.random() < profile.type_error_rate:
                    place_id = rng.randint(place_entity_count, profile.entities - 1)
                else:
                    place_id = rng.randint(0, place_entity_count - 1)
                triple(f, eid, SEM + "hasPlace", uri(EKG + f"entity_{place_id}"))
            if rng.random() < profile.external_rate:
                triple(f, eid, OWL + "sameAs", uri(WD + f"Q{profile.text_prefix + i}"))
                if rng.random() < 0.85:
                    triple(f, eid, OWL + "sameAs", uri(DBR + name.replace(" ", "_")))
            if rng.random() < profile.description_rate:
                f.write(f"{uri(eid)} {uri(DCTERMS + 'description')} {literal(f'Text description for {name}.', 'en')} .\n")

    with (folder / "relations_entities_base.nt").open("w", encoding="utf-8") as f:
        for i in range(max(5, profile.entities // 3)):
            rid = EKG + f"relation_{1000 + i}"
            triple(f, rid, RDF + "type", uri(EKGS + "Relation"))
            triple(f, rid, RDF + "subject", uri(EKG + f"entity_{rng.randint(0, profile.entities - 1)}"))
            triple(f, rid, RDF + "object", uri(EKG + f"entity_{rng.randint(0, profile.entities - 1)}"))
            triple(f, rid, SEM + "roleType", uri(WDP + "P26"))

    with (folder / "relations_entities_temporal.nt").open("w", encoding="utf-8") as f:
        for i in range(max(3, profile.entities // 5)):
            rid = EKG + f"relation_{2000 + i}"
            triple(f, rid, RDF + "type", uri(EKGS + "Relation"))
            triple(f, rid, RDF + "subject", uri(EKG + f"entity_{rng.randint(0, profile.entities - 1)}"))
            triple(f, rid, RDF + "object", uri(EKG + f"entity_{rng.randint(0, profile.entities - 1)}"))
            triple(f, rid, SEM + "roleType", uri(WDP + "P54"))
            f.write(f"{uri(rid)} {uri(SEM + 'hasBeginTimeStamp')} {date_literal(random_date(rng, profile.clustered_dates), False)} .\n")

    with (folder / "relations_entities_other.nt").open("w", encoding="utf-8") as f:
        for _ in range(max(3, profile.entities // 6)):
            triple(
                f,
                EKG + f"entity_{rng.randint(0, profile.entities - 1)}",
                rng.choice([WDP + "P27", WDP + "P19", WDP + "P20"]),
                uri(EKG + f"entity_{rng.randint(0, profile.entities - 1)}"),
            )

    with (folder / "types.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.events):
            triple(f, EKG + f"event_{profile.event_prefix + i}", RDF + "type", uri(SEM + "Event"))
        for i in range(profile.text_events):
            triple(f, EKG + f"event_{profile.text_prefix + i}", RDF + "type", uri(EKGS + "TextEvent"))
        for i in range(profile.entities):
            entity_type = "Place" if i < place_entity_count else "Actor"
            triple(f, EKG + f"entity_{i}", RDF + "type", uri(SEM + entity_type))

    with (folder / "preferred_labels.nt").open("w", encoding="utf-8") as f:
        for i, name in labels.items():
            f.write(f"{uri(EKG + f'event_{profile.event_prefix + i}')} {uri(RDFS + 'label')} {literal(name, 'en')} .\n")
        for i in range(profile.entities):
            f.write(f"{uri(EKG + f'entity_{i}')} {uri(RDFS + 'label')} {literal(entity_name(i), 'en')} .\n")

    with (folder / "events_first_sentences.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.events):
            if rng.random() < profile.description_rate:
                f.write(f"{uri(EKG + f'event_{profile.event_prefix + i}')} {uri(DCTERMS + 'description')} {literal(f'First sentence for event {i}.', 'en')} .\n")

    with (folder / "events_descriptions_from_text_events.nt").open("w", encoding="utf-8") as f:
        for i in range(profile.text_events):
            if rng.random() < profile.description_rate:
                f.write(f"{uri(EKG + f'event_{profile.text_prefix + i}')} {uri(DCTERMS + 'description')} {literal(f'Text-event description {i}.', 'en')} .\n")

    with (folder / "property_labels.nt").open("w", encoding="utf-8") as f:
        for prop, label in [
            (WDP + "P710", "participant"),
            (WDP + "P276", "location"),
            (WDP + "P17", "country"),
            (WDP + "P26", "spouse"),
            (WDP + "P54", "member of"),
        ]:
            f.write(f"{uri(prop)} {uri(RDFS + 'label')} {literal(label, 'en')} .\n")

    with (folder / "types_ontology_dbpedia.nt").open("w", encoding="utf-8") as f:
        triple(f, "http://dbpedia.org/ontology/Event", RDFS + "subClassOf", uri(SEM + "Event"))
        triple(f, "http://dbpedia.org/ontology/Person", RDFS + "subClassOf", uri(SEM + "Actor"))

    (folder / "generation_manifest.json").write_text(
        json.dumps(
            {
                "generator": str(Path(__file__).resolve()),
                "random_seed": profile.event_prefix,
                "profile": profile.__dict__,
                "degradation_operations": {
                    "missing_labels": 1.0 - profile.label_rate,
                    "missing_temporal_values": 1.0 - profile.date_rate,
                    "missing_places": 1.0 - profile.place_rate,
                    "missing_external_links": 1.0 - profile.external_rate,
                    "missing_descriptions": 1.0 - profile.description_rate,
                    "reduced_relations": 1.0 - profile.relation_rate,
                    "repeated_base_labels": max(
                        0, profile.events - profile.unique_name_count
                    ),
                    "near_variant_rate_on_repeated_labels": profile.near_variant_rate,
                    "type_error_rate_on_place_links": profile.type_error_rate,
                    "interval_rate": profile.interval_rate,
                    "invalid_interval_rate": profile.invalid_interval_rate,
                    "year_only_rate": profile.year_only_rate,
                    "clustered_dates": profile.clustered_dates,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"{profile.folder}: events={profile.events}, labels={len(labels)}, "
        f"dates={len(dates)}, places={len(places)}, linked_events={len(linked)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the three deterministic synthetic EKG profiles."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT,
        help="Parent directory for synthetic-event-kg, -2, and -3.",
    )
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    for profile in PROFILES:
        generate(profile, output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
