"""Tests for the semantic Asset Registry (Phase 3)."""

import pytest

from core.visual import (
    AssetFormat,
    AssetRecord,
    AssetRegistry,
    AssetStatus,
    AssetValidationError,
    Concept,
    DuplicateAssetError,
    UnknownAssetError,
    UnknownConceptError,
    VerificationStatus,
)


def test_asset_registration() -> None:
    registry = AssetRegistry(concepts={})
    asset = AssetRecord(asset_id="apple_default", concept_id="apple", status="pending")
    assert registry.register_asset(asset) is asset
    assert registry.get_asset("apple_default") is asset


def test_asset_lookup() -> None:
    registry = AssetRegistry(concepts={})
    registry.register_asset(AssetRecord(asset_id="apple_default", concept_id="apple"))
    assert registry.get_asset("apple_default").concept_id == "apple"
    assert registry.find_for_concept("apple").asset_id == "apple_default"


def test_registered_asset_preferred_over_concept_reference() -> None:
    registry = AssetRegistry()
    registry.register_asset(AssetRecord(asset_id="apple_custom", concept_id="apple"))
    assert registry.find_for_concept("apple").asset_id == "apple_custom"


def test_missing_asset_is_explicit() -> None:
    registry = AssetRegistry(concepts={})
    with pytest.raises(UnknownAssetError, match="nope"):
        registry.get_asset("nope")
    with pytest.raises(UnknownConceptError, match="dragon"):
        registry.find_for_concept("dragon")


def test_duplicate_asset_id_rejected() -> None:
    registry = AssetRegistry(concepts={})
    registry.register_asset(AssetRecord(asset_id="apple_default", concept_id="apple"))
    with pytest.raises(DuplicateAssetError, match="apple_default"):
        registry.register_asset(AssetRecord(asset_id="apple_default", concept_id="apple"))


def test_invalid_format_rejected() -> None:
    with pytest.raises(AssetValidationError, match="format"):
        AssetRecord(asset_id="x_default", concept_id="x", format="obj")


def test_invalid_status_rejected() -> None:
    with pytest.raises(AssetValidationError, match="status"):
        AssetRecord(asset_id="x_default", concept_id="x", status="maybe")
    with pytest.raises(AssetValidationError, match="verification_status"):
        AssetRecord(asset_id="x_default", concept_id="x", verification_status="trusted")


def test_invalid_path_rejected() -> None:
    with pytest.raises(AssetValidationError, match="relative to the project"):
        AssetRecord(asset_id="x_default", concept_id="x", path="C:/Users/someone/model.glb")
    with pytest.raises(AssetValidationError, match="escapes the project root"):
        AssetRecord(asset_id="x_default", concept_id="x", path="../../outside.glb")


def test_relative_path_handling() -> None:
    normalized = AssetRecord(
        asset_id="apple_a", concept_id="apple", path="data/visual_world/../visual_world/assets/apple.glb"
    )
    assert normalized.path == "data/visual_world/assets/apple.glb"
    backslashes = AssetRecord(asset_id="apple_b", concept_id="apple", path="data\\visual_world\\assets\\apple.glb")
    assert backslashes.path == "data/visual_world/assets/apple.glb"


def test_verification_is_separate_from_existence(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.visual.assets.PROJECT_ROOT", tmp_path)
    (tmp_path / "exists.glb").write_bytes(b"glTF")
    registry = AssetRegistry(concepts={})

    unverified = AssetRecord(asset_id="m_default", concept_id="m", path="exists.glb", status="available")
    registry.register_asset(unverified)
    assert unverified.verification_status is VerificationStatus.UNVERIFIED

    with pytest.raises(AssetValidationError, match="VERIFIED"):
        registry.register_asset(
            AssetRecord(asset_id="v_default", concept_id="v", path="gone.glb", verification_status="verified")
        )
    with pytest.raises(AssetValidationError, match="AVAILABLE"):
        registry.register_asset(AssetRecord(asset_id="a_default", concept_id="a", path="gone.glb", status="available"))


def test_multiple_assets_deterministic_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.visual.assets.PROJECT_ROOT", tmp_path)
    (tmp_path / "model.glb").write_bytes(b"glTF")
    registry = AssetRegistry(concepts={})

    registry.register_asset(AssetRecord(asset_id="apple_b", concept_id="apple", path="model.glb", status="available"))
    registry.register_asset(
        AssetRecord(
            asset_id="apple_a", concept_id="apple", path="model.glb", status="pending", verification_status="verified"
        )
    )
    assert registry.find_for_concept("apple").asset_id == "apple_a"

    registry.register_asset(
        AssetRecord(
            asset_id="apple_0", concept_id="apple", path="model.glb", status="pending", verification_status="verified"
        )
    )
    assert registry.find_for_concept("apple").asset_id == "apple_0"

    registry.register_asset(
        AssetRecord(
            asset_id="apple_z",
            concept_id="apple",
            path="model.glb",
            status="pending",
            verification_status="verified",
            is_default=True,
        )
    )
    assert registry.find_for_concept("apple").asset_id == "apple_z"


def test_serialization_round_trip() -> None:
    registry = AssetRegistry(concepts={})
    registry.register_asset(
        AssetRecord(
            asset_id="apple_default",
            concept_id="apple",
            path="data/visual_world/assets/apple.glb",
            status="pending",
            source="manual",
            license="CC0",
            is_default=True,
            available_parts=("body", "stem"),
            metadata={"note": "seed"},
        )
    )
    payload = registry.to_dict()
    restored = AssetRegistry.from_dict(payload, concepts={})
    assert restored.to_dict() == payload
    assert restored.get_asset("apple_default").available_parts == ("body", "stem")

    with pytest.raises(DuplicateAssetError):
        AssetRegistry.from_dict({"assets": payload["assets"] + payload["assets"]})
    with pytest.raises(AssetValidationError, match="missing required field"):
        AssetRecord.from_dict({"concept_id": "apple"})


def test_unavailable_asset_is_structured_state() -> None:
    registry = AssetRegistry()
    apple = registry.find_for_concept("apple")
    assert apple.asset_id == "apple_default"
    assert apple.status is AssetStatus.PENDING
    assert apple.verification_status is VerificationStatus.UNVERIFIED
    assert not apple.is_available
    assert apple.path is None
    assert apple.format is AssetFormat.GLB
    assert apple.source == "concept"
    assert apple.is_default
    assert apple.available_parts == ("body", "stem", "leaf")

    pear = Concept(name="pear", parts=("flesh",), default_transform={}, asset={"status": "available", "path": "p.glb"})
    lying = AssetRegistry(concepts={"pear": pear})
    found = lying.find_for_concept("pear")
    assert found.status is AssetStatus.UNAVAILABLE
    assert found.metadata.get("reason") == "file not found"


def test_reset_listing_and_removal() -> None:
    registry = AssetRegistry(concepts={})
    registry.register_asset(AssetRecord(asset_id="b_second", concept_id="two"))
    registry.register_asset(AssetRecord(asset_id="a_first", concept_id="one"))

    assert [asset.asset_id for asset in registry.list_assets()] == ["a_first", "b_second"]
    assert [asset.asset_id for asset in registry.list_assets("one")] == ["a_first"]

    registry.remove_asset("a_first")
    with pytest.raises(UnknownAssetError):
        registry.get_asset("a_first")

    registry.reset()
    assert registry.list_assets() == []
