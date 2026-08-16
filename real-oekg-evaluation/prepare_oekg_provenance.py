"""Record exact OEKG source/cleaning provenance before adopting the existing TDB."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
CLI = HERE.parent / "ekg-eval-cli"
sys.path.insert(0, str(CLI))

from ekg_eval_cli.provenance import build_input_manifest, sha256_file


SOURCE = HERE / "oekg-full" / "event_kg"
CLEAN = HERE / "oekg-event-layer-clean"
FILES = [
    "events.nt",
    "events_descriptions_from_text_events.nt",
    "events_first_sentences.nt",
    "preferred_labels.nt",
    "property_labels.nt",
    "relations_events_literals.nt",
    "relations_events_other.nt",
    "relations_event_base.nt",
    "schema.nt",
    "text_events.nt",
    "types.nt",
    "types_ontology_dbpedia.nt",
    "type_labels_dbpedia.nt",
]


def changed_lines(source: Path, clean: Path) -> list[dict[str, object]]:
    changes = []
    with (
        source.open("rb") as source_stream,
        clean.open("rb") as clean_stream,
    ):
        for number, (before, after) in enumerate(
            zip(source_stream, clean_stream, strict=True), start=1
        ):
            if before != after:
                changes.append(
                    {
                        "line": number,
                        "source_line_sha256": hashlib.sha256(before).hexdigest(),
                        "clean_line_sha256": hashlib.sha256(after).hexdigest(),
                        "source_bytes": len(before),
                        "clean_bytes": len(after),
                    }
                )
    return changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adopt-tdb-triples", type=int)
    parser.add_argument("--adopt-tdb-events", type=int)
    args = parser.parse_args()
    clean_files = [CLEAN / name for name in FILES]
    clean_manifest = build_input_manifest(
        clean_files, CLEAN / ".ekg_eval_input_manifest.json"
    )
    clean_by_name = {Path(item["path"]).name: item for item in clean_manifest["files"]}

    source_files = []
    repairs: dict[str, list[dict[str, object]]] = {}
    for name in FILES:
        source = SOURCE / name
        clean = CLEAN / name
        same_file = os.path.samefile(source, clean)
        source_files.append(
            {
                "path": str(source.resolve()),
                "size_bytes": source.stat().st_size,
                "sha256": clean_by_name[name]["sha256"] if same_file else sha256_file(source),
                "same_physical_file_as_clean_copy": same_file,
            }
        )
        if not same_file:
            repairs[name] = changed_lines(source, clean)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_release": {
            "description": "OEKG V2.0 event-layer archive event_kg.tar.gz downloaded from Zenodo",
            "version": "OEKG V2.0",
            "release_date": "2021-01-31",
            "retrieved_date": "2026-08-02",
            "zenodo_record_url": "https://zenodo.org/record/4503163",
            "archive_path": str((HERE / "raw" / "event_kg.tar.gz").resolve()),
            "archive_sha256": sha256_file(HERE / "raw" / "event_kg.tar.gz"),
            "selected_event_layer_files": source_files,
        },
        "cleaning": {
            "script": str((HERE / "clean_oekg_literals.py").resolve()),
            "scope": (
                "Only invalid backslash escape sequences inside RDF literal lexical forms "
                "were escaped; all unchanged files are hard links to the source extraction."
            ),
            "changed_lines": repairs,
            "changed_line_count": sum(len(items) for items in repairs.values()),
        },
        "clean_input_manifest": clean_manifest,
    }
    if args.adopt_tdb_triples is not None or args.adopt_tdb_events is not None:
        if (args.adopt_tdb_triples, args.adopt_tdb_events) != (93_474_126, 954_554):
            raise RuntimeError(
                "The observed TDB counts do not match the previously loaded OEKG event layer; "
                "the database must not be adopted."
            )
        database_manifest = CLEAN / "databases" / "eventkg-db" / "ekg_eval_database_manifest.json"
        database_manifest.write_text(
            json.dumps(clean_manifest, indent=2) + "\n", encoding="utf-8"
        )
        manifest["tdb_verification"] = {
            "triple_count": args.adopt_tdb_triples,
            "direct_sem_event_count": args.adopt_tdb_events,
            "queries": [
                str((HERE / "queries" / "total_triples.rq").resolve()),
                str((HERE / "queries" / "sem_event_count.rq").resolve()),
            ],
            "database_manifest": str(database_manifest.resolve()),
        }
    output = HERE / "oekg-provenance-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
