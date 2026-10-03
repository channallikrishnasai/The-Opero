"""Semantic Asset Registry: maps visual concepts to available 3D asset metadata.

Phase 3 of the visual subsystem. The registry answers "what visual asset
represents this concept?" and never renders, downloads, or loads models.
Existence and verification are tracked separately: a file can exist while the
asset remains UNVERIFIED, and an AVAILABLE asset must have a real file.
Paths are project-relative and portable; absolute paths and root escapes
are rejected.
"""

import json
import threading
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields, replace
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from .concepts import Concept, UnknownConceptError, VisualWorldError, load_concepts

# Python 3.10 compatible StrEnum implementation
class StrEnum(str, Enum):
    """String enum base class for Python 3.10 compatibility."""
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_E = TypeVar("_E", bound=StrEnum)


class AssetError(VisualWorldError):
    """Base error for the asset registry."""


class AssetValidationError(AssetError):
    """Asset metadata is structurally or semantically invalid."""


class UnknownAssetError(AssetError):
    """Raised when an asset id is not registered."""


class DuplicateAssetError(AssetError):
    """Raised when registering an asset id twice."""


class AssetFormat(StrEnum):
    GLB = "glb"
    GLTF = "gltf"


class AssetStatus(StrEnum):
    AVAILABLE = "available"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


_STATUS_RANK = {
    AssetStatus.AVAILABLE: 0,
    AssetStatus.PENDING: 1,
    AssetStatus.UNAVAILABLE: 2,
    AssetStatus.INVALID: 3,
}


def _coerce_enum(enum_cls: type[_E], value: object, field_name: str) -> _E:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value.lower())
        except ValueError:
            pass
    options = [member.value for member in enum_cls]
    raise AssetValidationError(f"invalid {field_name} {value!r}; valid values: {options}")


def _normalize_path(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AssetValidationError(f"asset path must be a non-empty string or None, got {value!r}")
    candidate = Path(value)
    if candidate.is_absolute():
        raise AssetValidationError(f"asset path must be relative to the project, got {value!r}")
    root = PROJECT_ROOT.resolve()
    resolved = (PROJECT_ROOT / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise AssetValidationError(f"asset path escapes the project root: {value!r}")
    return resolved.relative_to(root).as_posix()


def _file_exists(path: str | None) -> bool:
    return path is not None and (PROJECT_ROOT / path).is_file()


def _selection_key(asset: "AssetRecord") -> tuple[int, int, int, str]:
    """Deterministic ordering: verified, available, default, then asset id."""
    return (
        0 if asset.verification_status is VerificationStatus.VERIFIED else 1,
        _STATUS_RANK[asset.status],
        0 if asset.is_default else 1,
        asset.asset_id,
    )


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    concept_id: str
    path: str | None = None
    format: AssetFormat = AssetFormat.GLB
    status: AssetStatus = AssetStatus.PENDING
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    source: str = ""
    license: str = ""
    is_default: bool = False
    available_parts: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("asset_id", "concept_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise AssetValidationError(f"{name} must be a non-empty string, got {value!r}")
        for name in ("source", "license"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise AssetValidationError(f"{name} must be a string, got {value!r}")
        object.__setattr__(self, "format", _coerce_enum(AssetFormat, self.format, "format"))
        object.__setattr__(self, "status", _coerce_enum(AssetStatus, self.status, "status"))
        object.__setattr__(
            self,
            "verification_status",
            _coerce_enum(VerificationStatus, self.verification_status, "verification_status"),
        )
        object.__setattr__(self, "path", _normalize_path(self.path))
        if not isinstance(self.is_default, bool):
            raise AssetValidationError(f"is_default must be a bool, got {type(self.is_default).__name__}")
        if isinstance(self.available_parts, str) or not all(
            isinstance(part, str) and part for part in self.available_parts
        ):
            raise AssetValidationError("available_parts must be an iterable of non-empty strings")
        object.__setattr__(self, "available_parts", tuple(self.available_parts))
        if not isinstance(self.metadata, dict):
            raise AssetValidationError(f"metadata must be a dict, got {type(self.metadata).__name__}")
        try:
            json.dumps(self.metadata)
        except (TypeError, ValueError) as exc:
            raise AssetValidationError(f"metadata must be JSON-serializable: {exc}") from exc

    @property
    def is_available(self) -> bool:
        return self.status is AssetStatus.AVAILABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "concept_id": self.concept_id,
            "path": self.path,
            "format": self.format.value,
            "status": self.status.value,
            "verification_status": self.verification_status.value,
            "source": self.source,
            "license": self.license,
            "is_default": self.is_default,
            "available_parts": list(self.available_parts),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetRecord":
        if not isinstance(data, dict):
            raise AssetValidationError(f"asset record must be a dict, got {type(data).__name__}")
        known_fields = {spec.name for spec in fields(cls)}
        unknown = set(data) - known_fields
        if unknown:
            raise AssetValidationError(f"unknown asset fields: {sorted(str(item) for item in unknown)}")
        for required in ("asset_id", "concept_id"):
            if required not in data:
                raise AssetValidationError(f"asset record missing required field {required!r}")
        return cls(**data)


def _concept_asset_record(concept: Concept) -> AssetRecord:
    """Derive a structured asset record from a concept's asset reference (never fakes availability)."""
    raw = concept.asset or {}
    path_value = raw.get("path")
    format_value = raw.get("format")
    if format_value is None and isinstance(path_value, str):
        suffix = Path(path_value).suffix.lower().removeprefix(".")
        if suffix in {member.value for member in AssetFormat}:
            format_value = suffix
    metadata = {"note": raw["note"]} if "note" in raw else {}
    return AssetRecord(
        asset_id=f"{concept.name}_default",
        concept_id=concept.name,
        path=path_value,
        format=format_value or AssetFormat.GLB,
        status=raw.get("status", AssetStatus.PENDING.value),
        verification_status=VerificationStatus.UNVERIFIED,
        source="concept",
        is_default=True,
        available_parts=concept.parts,
        metadata=metadata,
    )


class AssetRegistry:
    """Deterministic registry of asset metadata; never downloads or renders."""

    def __init__(self, concepts: Mapping[str, Concept] | None = None) -> None:
        self._lock = threading.RLock()
        self._assets: dict[str, AssetRecord] = {}
        self._concepts = dict(concepts) if concepts is not None else load_concepts()

    def register_asset(self, asset: AssetRecord) -> AssetRecord:
        if not isinstance(asset, AssetRecord):
            raise AssetValidationError(f"register_asset expects an AssetRecord, got {type(asset).__name__}")
        with self._lock:
            if asset.asset_id in self._assets:
                raise DuplicateAssetError(f"asset {asset.asset_id!r} is already registered")
            self.validate_asset(asset)
            self._assets[asset.asset_id] = asset
        return asset

    def get_asset(self, asset_id: str) -> AssetRecord:
        with self._lock:
            asset = self._assets.get(asset_id)
        if asset is None:
            raise UnknownAssetError(f"unknown asset {asset_id!r}")
        return asset

    def find_for_concept(self, concept_id: str) -> AssetRecord:
        with self._lock:
            candidates = [asset for asset in self._assets.values() if asset.concept_id == concept_id]
            if candidates:
                return min(candidates, key=_selection_key)
            concept = self._concepts.get(concept_id)
        if concept is None:
            raise UnknownConceptError(f"unknown concept {concept_id!r}; known concepts: {sorted(self._concepts)}")
        record = _concept_asset_record(concept)
        if record.status is AssetStatus.AVAILABLE and not _file_exists(record.path):
            record = replace(
                record, status=AssetStatus.UNAVAILABLE, metadata={**record.metadata, "reason": "file not found"}
            )
        return record

    def list_assets(self, concept_id: str | None = None) -> list[AssetRecord]:
        with self._lock:
            records = [asset for asset in self._assets.values() if concept_id is None or asset.concept_id == concept_id]
        return sorted(records, key=lambda asset: asset.asset_id)

    def remove_asset(self, asset_id: str) -> AssetRecord:
        with self._lock:
            asset = self._assets.get(asset_id)
            if asset is None:
                raise UnknownAssetError(f"unknown asset {asset_id!r}")
            del self._assets[asset_id]
        return asset

    def validate_asset(self, asset: AssetRecord) -> None:
        if asset.status is AssetStatus.AVAILABLE and not _file_exists(asset.path):
            raise AssetValidationError(
                f"AVAILABLE asset {asset.asset_id!r} requires an existing file; path={asset.path!r}"
            )
        if asset.verification_status is VerificationStatus.VERIFIED and not _file_exists(asset.path):
            raise AssetValidationError(
                f"VERIFIED asset {asset.asset_id!r} requires an existing file; path={asset.path!r}"
            )

    def reset(self) -> None:
        with self._lock:
            self._assets.clear()

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            ordered = sorted(self._assets.values(), key=lambda asset: asset.asset_id)
            return {"version": 1, "assets": [asset.to_dict() for asset in ordered]}

    @classmethod
    def from_dict(cls, data: dict[str, Any], concepts: Mapping[str, Concept] | None = None) -> "AssetRegistry":
        if not isinstance(data, dict):
            raise AssetValidationError(f"asset registry payload must be a dict, got {type(data).__name__}")
        unknown = set(data) - {"version", "assets"}
        if unknown:
            raise AssetValidationError(f"unknown registry fields: {sorted(str(item) for item in unknown)}")
        raw_assets = data.get("assets", [])
        if not isinstance(raw_assets, list):
            raise AssetValidationError(f"assets must be a list, got {type(raw_assets).__name__}")
        registry = cls(concepts=concepts)
        for raw in raw_assets:
            registry.register_asset(AssetRecord.from_dict(raw))
        return registry


# The project's own model files. Exactly one entry — a data-driven manifest
# earns its file when a second asset arrives.
_BUNDLED_ASSETS: tuple[AssetRecord, ...] = (
    AssetRecord(
        asset_id="apple_default",
        concept_id="apple",
        path="data/visual_world/assets/apple.glb",
        format=AssetFormat.GLB,
        status=AssetStatus.AVAILABLE,
        source="procedurally authored for OPERO (data/visual_world/generate_apple_glb.py)",
        license="CC0-1.0",
        is_default=True,
        available_parts=("body", "stem", "leaf"),
    ),
)


def register_bundled_assets(registry: AssetRegistry) -> list[AssetRecord]:
    """Register project-authored model files (idempotent; skips missing files).

    Explicit call, never automatic: a bare AssetRegistry must stay
    metadata-only so derived-record behaviour and its tests remain truthful.
    """
    registered: list[AssetRecord] = []
    for asset in _BUNDLED_ASSETS:
        if not _file_exists(asset.path):
            continue
        try:
            registered.append(registry.register_asset(asset))
        except DuplicateAssetError:
            continue
    return registered
