"""Session-scoped visual world model: entities, transforms, part visibility, relationships.

Additive Phase 1 subsystem. No rendering, no Qt, no network: the world model is
pure in-memory state with dict serialization so later phases can persist it.
"""

import threading
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .concepts import Concept, UnknownConceptError, VisualWorldError, load_concepts


class UnknownEntityError(VisualWorldError):
    """Raised when an entity id is not present in the world model."""


class UnknownPartError(VisualWorldError):
    """Raised when a part name does not belong to an entity's concept."""


@dataclass
class Entity:
    id: str
    concept: str
    transform: dict[str, list[float]] = field(default_factory=dict)
    parts: dict[str, bool] = field(default_factory=dict)
    visible: bool = True


class VisualWorldModel:
    """Deterministic, thread-safe store of instantiated entities."""

    def __init__(self, concepts_dir: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._concepts: dict[str, Concept] = load_concepts(concepts_dir)
        self._entities: dict[str, Entity] = {}
        self._counters: dict[str, int] = {}
        self._relationships: list[dict[str, str]] = []

    def create_entity(self, concept_name: str) -> Entity:
        with self._lock:
            concept = self._concepts.get(concept_name)
            if concept is None:
                raise UnknownConceptError(f"unknown concept {concept_name!r}; known concepts: {sorted(self._concepts)}")
            number = self._counters.get(concept_name, 0) + 1
            self._counters[concept_name] = number
            entity = Entity(
                id=f"{concept_name}_{number:02d}",
                concept=concept_name,
                transform=deepcopy(concept.default_transform),
                parts={part: True for part in concept.parts},
            )
            self._entities[entity.id] = entity
            return deepcopy(entity)

    def get_entity(self, entity_id: str) -> Entity:
        with self._lock:
            return deepcopy(self._require_entity(entity_id))

    def update_transform(
        self,
        entity_id: str,
        *,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
    ) -> Entity:
        updates = {"position": position, "rotation": rotation, "scale": scale}
        with self._lock:
            entity = self._require_entity(entity_id)
            applied = False
            for key, value in updates.items():
                if value is None:
                    continue
                if len(value) != 3:
                    raise ValueError(f"{key} must have 3 components, got {len(value)}")
                entity.transform[key] = [float(component) for component in value]
                applied = True
            if not applied:
                raise ValueError("update_transform requires at least one of position/rotation/scale")
            return deepcopy(entity)

    def set_part_visibility(self, entity_id: str, part: str, visible: bool) -> Entity:
        with self._lock:
            entity = self._require_entity(entity_id)
            if part not in entity.parts:
                raise UnknownPartError(f"unknown part {part!r} for {entity_id}; parts: {sorted(entity.parts)}")
            entity.parts[part] = bool(visible)
            return deepcopy(entity)

    def set_visible(self, entity_id: str, visible: bool) -> Entity:
        with self._lock:
            entity = self._require_entity(entity_id)
            entity.visible = bool(visible)
            return deepcopy(entity)

    def add_relationship(self, source_id: str, target_id: str, kind: str = "related") -> dict[str, str]:
        with self._lock:
            self._require_entity(source_id)
            self._require_entity(target_id)
            relationship = {"source": source_id, "target": target_id, "kind": kind}
            self._relationships.append(relationship)
            return dict(relationship)

    def get_relationships(self, entity_id: str) -> list[dict[str, str]]:
        with self._lock:
            self._require_entity(entity_id)
            return [
                dict(relationship)
                for relationship in self._relationships
                if entity_id in (relationship["source"], relationship["target"])
            ]

    def reset(self) -> None:
        with self._lock:
            self._entities.clear()
            self._counters.clear()
            self._relationships.clear()

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": 1,
                "entities": [
                    {
                        "id": entity.id,
                        "concept": entity.concept,
                        "transform": deepcopy(entity.transform),
                        "parts": dict(entity.parts),
                        "visible": entity.visible,
                    }
                    for entity in self._entities.values()
                ],
                "relationships": [dict(relationship) for relationship in self._relationships],
            }

    @classmethod
    def from_dict(cls, data: dict[str, Any], concepts_dir: Path | None = None) -> "VisualWorldModel":
        model = cls(concepts_dir=concepts_dir)
        with model._lock:
            for raw in data.get("entities", []):
                entity = Entity(
                    id=str(raw["id"]),
                    concept=str(raw["concept"]),
                    transform={key: list(value) for key, value in raw.get("transform", {}).items()},
                    parts={key: bool(value) for key, value in raw.get("parts", {}).items()},
                    visible=bool(raw.get("visible", True)),
                )
                if entity.concept not in model._concepts:
                    raise UnknownConceptError(
                        f"unknown concept {entity.concept!r} in serialized entity {entity.id!r}; "
                        f"known concepts: {sorted(model._concepts)}"
                    )
                if entity.id in model._entities:
                    raise VisualWorldError(f"duplicate entity id {entity.id!r}")
                model._entities[entity.id] = entity
                prefix, separator, tail = entity.id.rpartition("_")
                if separator and tail.isdigit():
                    model._counters[prefix] = max(model._counters.get(prefix, 0), int(tail))
            for raw in data.get("relationships", []):
                relationship = {
                    "source": str(raw["source"]),
                    "target": str(raw["target"]),
                    "kind": str(raw.get("kind", "related")),
                }
                if relationship["source"] not in model._entities or relationship["target"] not in model._entities:
                    raise UnknownEntityError(f"relationship references unknown entity: {relationship}")
                model._relationships.append(relationship)
        return model

    def _require_entity(self, entity_id: str) -> Entity:
        entity = self._entities.get(entity_id)
        if entity is None:
            raise UnknownEntityError(f"unknown entity {entity_id!r}")
        return entity
