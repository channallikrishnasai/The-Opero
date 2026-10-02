"""Concept vocabulary for the visual world model.

Concepts are data-driven: each JSON file under ``data/visual_world/concepts/``
describes one object concept (parts, default transform, asset reference).
Nothing is hardcoded in Python; adding a concept means adding a JSON file.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONCEPTS_DIR = Path(__file__).resolve().parents[2] / "data" / "visual_world" / "concepts"

_IDENTITY_TRANSFORM: dict[str, list[float]] = {
    "position": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0],
}


class VisualWorldError(Exception):
    """Base error for the visual world model."""


class ConceptError(VisualWorldError):
    """A concept file is malformed."""


class UnknownConceptError(VisualWorldError):
    """Raised when a requested concept is not in the vocabulary."""


@dataclass(frozen=True)
class Concept:
    name: str
    parts: tuple[str, ...]
    default_transform: dict[str, list[float]]
    asset: dict[str, Any] = field(default_factory=dict)
    description: str = ""


def _parse_concept(path: Path) -> Concept:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConceptError(f"{path.name}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ConceptError(f"{path.name}: concept must be a JSON object")

    parts = data.get("parts")
    if not isinstance(parts, list) or not parts or not all(isinstance(p, str) for p in parts):
        raise ConceptError(f"{path.name}: 'parts' must be a non-empty list of strings")

    raw_transform = data.get("default_transform", {})
    if not isinstance(raw_transform, dict):
        raise ConceptError(f"{path.name}: 'default_transform' must be an object")
    unknown_keys = set(raw_transform) - set(_IDENTITY_TRANSFORM)
    if unknown_keys:
        raise ConceptError(f"{path.name}: unknown transform keys {sorted(unknown_keys)}")
    default_transform = {key: list(raw_transform.get(key, default)) for key, default in _IDENTITY_TRANSFORM.items()}

    raw_asset = data.get("asset", {})
    if not isinstance(raw_asset, dict):
        raise ConceptError(f"{path.name}: 'asset' must be an object")

    return Concept(
        name=str(data.get("name", path.stem)),
        parts=tuple(parts),
        default_transform=default_transform,
        asset=raw_asset,
        description=str(data.get("description", "")),
    )


def load_concepts(directory: Path | None = None) -> dict[str, Concept]:
    """Read every ``*.json`` concept file from *directory* (default: the repo's concepts dir)."""
    directory = Path(directory) if directory is not None else CONCEPTS_DIR
    concepts: dict[str, Concept] = {}
    if not directory.is_dir():
        return concepts
    for path in sorted(directory.glob("*.json")):
        concept = _parse_concept(path)
        concepts[concept.name] = concept
    return concepts
