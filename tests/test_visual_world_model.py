"""Tests for the visual world model (Phase 1)."""

import threading

import pytest

from core.visual import (
    ConceptError,
    Entity,
    UnknownConceptError,
    UnknownEntityError,
    UnknownPartError,
    VisualWorldModel,
    load_concepts,
)


@pytest.fixture
def model() -> VisualWorldModel:
    return VisualWorldModel()


def test_create_entity_uses_zero_padded_ids(model: VisualWorldModel) -> None:
    first = model.create_entity("apple")
    second = model.create_entity("apple")
    assert isinstance(first, Entity)
    assert first.id == "apple_01"
    assert second.id == "apple_02"


def test_create_entity_loads_concept_parts_and_transform(model: VisualWorldModel) -> None:
    entity = model.create_entity("apple")
    assert entity.concept == "apple"
    assert entity.parts == {"body": True, "stem": True, "leaf": True}
    assert entity.transform["position"] == [0.0, 0.0, 0.0]
    assert entity.transform["rotation"] == [0.0, 0.0, 0.0]
    assert entity.transform["scale"] == [1.0, 1.0, 1.0]


def test_create_unknown_concept_raises(model: VisualWorldModel) -> None:
    with pytest.raises(UnknownConceptError, match="dragon"):
        model.create_entity("dragon")


def test_get_entity(model: VisualWorldModel) -> None:
    created = model.create_entity("apple")
    fetched = model.get_entity("apple_01")
    assert fetched.id == created.id == "apple_01"
    assert fetched.parts == created.parts


def test_get_unknown_entity_raises(model: VisualWorldModel) -> None:
    with pytest.raises(UnknownEntityError, match="apple_99"):
        model.get_entity("apple_99")


def test_update_transform(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    updated = model.update_transform("apple_01", position=[1.0, 2.0, 3.0], rotation=[0.0, 90.0, 0.0])
    assert updated.transform["position"] == [1.0, 2.0, 3.0]
    assert updated.transform["rotation"] == [0.0, 90.0, 0.0]
    assert updated.transform["scale"] == [1.0, 1.0, 1.0]
    assert model.get_entity("apple_01").transform["position"] == [1.0, 2.0, 3.0]


def test_update_transform_rejects_bad_input(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    with pytest.raises(ValueError, match="3 components"):
        model.update_transform("apple_01", position=[1.0, 2.0])
    with pytest.raises(ValueError, match="at least one"):
        model.update_transform("apple_01")
    with pytest.raises(UnknownEntityError):
        model.update_transform("apple_99", position=[0.0, 0.0, 0.0])


def test_set_part_visibility(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    updated = model.set_part_visibility("apple_01", "leaf", False)
    assert updated.parts["leaf"] is False
    assert model.get_entity("apple_01").parts["leaf"] is False


def test_set_part_visibility_unknown_part_raises(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    with pytest.raises(UnknownPartError, match="core"):
        model.set_part_visibility("apple_01", "core", True)


def test_relationships(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    model.create_entity("apple")
    relationship = model.add_relationship("apple_01", "apple_02", kind="part-of")
    assert relationship == {"source": "apple_01", "target": "apple_02", "kind": "part-of"}
    assert model.get_relationships("apple_01") == [relationship]
    assert model.get_relationships("apple_02") == [relationship]


def test_relationship_requires_existing_entities(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    with pytest.raises(UnknownEntityError):
        model.add_relationship("apple_01", "apple_02")


def test_reset_clears_entities_and_counters(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    model.create_entity("apple")
    model.reset()
    with pytest.raises(UnknownEntityError):
        model.get_entity("apple_01")
    assert model.create_entity("apple").id == "apple_01"


def test_serialization_round_trip(model: VisualWorldModel) -> None:
    model.create_entity("apple")
    model.update_transform("apple_01", position=[5.0, 0.0, 0.0])
    model.set_part_visibility("apple_01", "stem", False)
    model.create_entity("apple")
    model.add_relationship("apple_01", "apple_02", kind="near")

    restored = VisualWorldModel.from_dict(model.to_dict())

    entity = restored.get_entity("apple_01")
    assert entity.transform["position"] == [5.0, 0.0, 0.0]
    assert entity.parts["stem"] is False
    assert restored.get_relationships("apple_01")[0]["kind"] == "near"
    assert restored.create_entity("apple").id == "apple_03"


def test_from_dict_rejects_unknown_concept() -> None:
    payload = {
        "version": 1,
        "entities": [{"id": "dragon_01", "concept": "dragon", "transform": {}, "parts": {}}],
        "relationships": [],
    }
    with pytest.raises(UnknownConceptError, match="dragon"):
        VisualWorldModel.from_dict(payload)


def test_from_dict_rejects_dangling_relationship() -> None:
    payload = {
        "version": 1,
        "entities": [],
        "relationships": [{"source": "apple_01", "target": "apple_02", "kind": "near"}],
    }
    with pytest.raises(UnknownEntityError):
        VisualWorldModel.from_dict(payload)


def test_concepts_come_from_json_directory() -> None:
    concepts = load_concepts()
    assert "apple" in concepts
    apple = concepts["apple"]
    assert apple.parts == ("body", "stem", "leaf")
    assert apple.default_transform["scale"] == [1.0, 1.0, 1.0]
    assert apple.asset["path"] is None
    assert apple.asset["status"] == "pending"


def test_missing_concepts_directory_is_empty(tmp_path) -> None:
    assert load_concepts(tmp_path / "does-not-exist") == {}


def test_malformed_concept_raises_concept_error(tmp_path) -> None:
    (tmp_path / "bad.json").write_text('{"parts": "not-a-list"}', encoding="utf-8")
    with pytest.raises(ConceptError, match="bad.json"):
        load_concepts(tmp_path)


def test_concurrent_creates_are_unique() -> None:
    model = VisualWorldModel()
    ids: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(10):
                ids.append(model.create_entity("apple").id)
        except BaseException as exc:  # pragma: no cover - defensive
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(ids) == 80
    assert len(set(ids)) == 80
