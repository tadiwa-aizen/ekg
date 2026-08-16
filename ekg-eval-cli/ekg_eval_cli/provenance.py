"""Reproducibility manifests for inputs, software, and cached artefacts."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import hashlib
import json
import platform
import subprocess


MANIFEST_VERSION = 1
SOURCE_SUFFIXES = {".py", ".toml", ".ini", ".txt"}
SOURCE_FILENAMES = {"setup.py", "LICENSE", "README.md"}


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def build_input_manifest(
    paths: Iterable[Path], cache_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Build a stable input manifest, reusing cached hashes only when metadata matches."""

    ordered = sorted((Path(path) for path in paths), key=lambda value: str(value.resolve()))
    cached_files: Dict[str, Dict[str, Any]] = {}
    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_files = {item["path"]: item for item in cached.get("files", [])}
        except (OSError, ValueError, KeyError, TypeError):
            cached_files = {}

    files = []
    for path in ordered:
        item = _file_metadata(path)
        previous = cached_files.get(item["path"])
        if (
            previous
            and previous.get("size_bytes") == item["size_bytes"]
            and previous.get("mtime_ns") == item["mtime_ns"]
            and previous.get("sha256")
        ):
            item["sha256"] = previous["sha256"]
        else:
            item["sha256"] = sha256_file(path)
        files.append(item)

    aggregate = hashlib.sha256()
    for item in files:
        aggregate.update(item["path"].encode("utf-8"))
        aggregate.update(str(item["size_bytes"]).encode("ascii"))
        aggregate.update(item["sha256"].encode("ascii"))

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "files": files,
        "aggregate_sha256": aggregate.hexdigest(),
    }
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def git_state(start_path: Path) -> Dict[str, Any]:
    """Return the containing repository revision and dirty state when available."""

    try:
        root = subprocess.run(
            ["git", "-C", str(start_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        revision = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", root, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return {"repository_root": root, "commit": revision, "dirty": bool(status.strip())}
    except (OSError, subprocess.CalledProcessError):
        return {"repository_root": None, "commit": None, "dirty": None}


def build_source_manifest(project_path: Path) -> Dict[str, Any]:
    """Hash the executable first-party source used for a run.

    A Git revision alone is insufficient when the working tree is dirty. This
    manifest makes every result traceable to the exact local implementation.
    Generated data, caches, virtual environments, and result files are excluded.
    """

    project_path = Path(project_path).resolve()
    excluded_parts = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "venv",
        ".venv",
    }
    candidates = []
    for path in project_path.rglob("*"):
        if not path.is_file() or any(part in excluded_parts for part in path.parts):
            continue
        if path.suffix.lower() in SOURCE_SUFFIXES or path.name in SOURCE_FILENAMES:
            candidates.append(path)

    files = []
    aggregate = hashlib.sha256()
    for path in sorted(candidates, key=lambda value: value.relative_to(project_path).as_posix()):
        relative = path.relative_to(project_path).as_posix()
        digest = sha256_file(path)
        size = path.stat().st_size
        files.append({"path": relative, "size_bytes": size, "sha256": digest})
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(str(size).encode("ascii"))
        aggregate.update(digest.encode("ascii"))
    return {
        "manifest_version": MANIFEST_VERSION,
        "aggregate_sha256": aggregate.hexdigest(),
        "files": files,
    }


def package_versions(names: Iterable[str]) -> Dict[str, Optional[str]]:
    """Return installed distribution versions for experiment dependencies."""

    versions: Dict[str, Optional[str]] = {}
    for name in names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def build_run_provenance(
    nt_files: Iterable[Path],
    parameters: Dict[str, Any],
    project_path: Path,
    source_snapshot: Optional[Dict[str, Any]] = None,
    git_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the provenance block embedded in every result file."""

    nt_files = list(nt_files)
    input_cache = nt_files[0].parent / ".ekg_eval_input_manifest.json"
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": build_input_manifest(nt_files, input_cache),
        "parameters": parameters,
        "git": git_snapshot if git_snapshot is not None else git_state(project_path),
        "source_snapshot": (
            source_snapshot
            if source_snapshot is not None
            else build_source_manifest(project_path)
        ),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": package_versions(
                [
                    "click",
                    "duckdb",
                    "networkx",
                    "numba",
                    "numpy",
                    "python-dateutil",
                    "rapidfuzz",
                    "rdflib",
                    "requests",
                ]
            ),
        },
    }
