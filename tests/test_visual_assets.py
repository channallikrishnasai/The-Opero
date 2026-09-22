"""Face-mesh payload: the 3D renderer consumes the exact geometry the 2D
QPainter avatar uses — one topology, two renderers.  These tests keep the
serialisation compact, JSON-safe and anchored."""
from __future__ import annotations

import json

from core.visual.assets import face_mesh_payload


def test_payload_is_compact_and_json_safe():
    payload = face_mesh_payload()
    text = json.dumps(payload, separators=(",", ":"))
    assert isinstance(text, str)
    # 468 verts + cranium/neck, faces + thinned edges — well under any bridge
    # limit (the whole payload must fit one runJavaScript call comfortably).
    assert len(text) < 200_000
    keys = {"verts", "faces", "edges", "jaw", "brow", "fade",
            "n_face", "n_head", "span", "anchors"}
    assert keys <= set(payload)


def test_anchors_come_from_measured_geometry():
    payload = face_mesh_payload()
    anchors = payload["anchors"]
    assert "left_eye" in anchors and "right_eye" in anchors
    # In the measured model +y is up: crown above face, eyes above the mouth.
    assert anchors["head"][1] > anchors["face"][1]
    assert anchors["left_eye"][1] > anchors["face"][1]
    # Eyes are nearly symmetric about the midline.
    assert abs(anchors["left_eye"][0] + anchors["right_eye"][0]) < 0.01


def test_registry_objects_have_builders_on_both_sides():
    """Every registry object must be whitelisted here AND have a JS builder.
    The JS side is scanned textually (no node needed in CI)."""
    import re
    from pathlib import Path
    from core.visual.registry import OBJECTS

    root = Path(__file__).resolve().parent.parent
    js = (root / "site" / "web_background" / "avatar3d.js").read_text(encoding="utf-8")
    for oid in OBJECTS:
        assert re.search(r"case \"%s\":" % re.escape(oid), js), \
            f"avatar3d.js has no builder for registry object '{oid}'"