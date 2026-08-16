import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE_DIR = ROOT / "oekg-full" / "event_kg"
DEFAULT_CLEAN_DIR = ROOT / "oekg-event-layer-clean"

EVENT_LAYER_FILES = [
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

FILES_TO_CLEAN = {
    "relations_events_literals.nt",
    "text_events.nt",
}

VALID_ESCAPES = set('tbnrf"\'\\uU')


def clean_invalid_literal_escapes(line: str) -> tuple[str, int]:
    in_literal = False
    escaped = False
    changed = 0
    output = []

    for char in line:
        if in_literal:
            if escaped:
                if char not in VALID_ESCAPES:
                    output.append("\\")
                    changed += 1
                output.append(char)
                escaped = False
                continue

            if char == "\\":
                output.append(char)
                escaped = True
                continue

            if char == '"':
                in_literal = False

            output.append(char)
            continue

        output.append(char)
        if char == '"':
            in_literal = True

    if escaped:
        output.append("\\")
        changed += 1

    return "".join(output), changed


def hardlink_or_clean(name: str, source_dir: Path, clean_dir: Path) -> None:
    source = source_dir / name
    target = clean_dir / name
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        target.unlink()

    if name not in FILES_TO_CLEAN:
        try:
            target.hardlink_to(source)
            print(f"linked {name}")
        except OSError:
            shutil.copy2(source, target)
            print(f"copied {name}")
        return

    changed_lines = 0
    changed_escapes = 0
    with source.open("r", encoding="utf-8") as src, target.open("w", encoding="utf-8", newline="") as dst:
        for line in src:
            cleaned, changes = clean_invalid_literal_escapes(line)
            if changes:
                changed_lines += 1
                changed_escapes += changes
            dst.write(cleaned)

    print(f"cleaned {name}: {changed_lines} lines, {changed_escapes} escapes")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the parseable 13-file OEKG event-layer input."
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    clean_dir = args.clean_dir.resolve()
    missing = [name for name in EVENT_LAYER_FILES if not (source_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"OEKG event layer is missing {len(missing)} required files: {missing}"
        )
    for name in EVENT_LAYER_FILES:
        hardlink_or_clean(name, source_dir, clean_dir)


if __name__ == "__main__":
    main()
