"""Assets for the 3D renderer, derived from the same measured head geometry the
QPainter avatar uses (core/avatar_mesh.build_head → face_model.obj).

One topology, two renderers: the JSON payload this module builds is what the
WebGL scene consumes to place face/mesh/particles — so the 3D presence has the
exact same real human proportions as the 2D fallback, with no duplicated data.

The payload is pure numbers (no code): the renderer is the only place allowed
to interpret it.
"""

from __future__ import annotations

import json
from typing import Any

from core.visual.registry import ANCHORS


def _landmark_centres(mesh: dict) -> dict[str, Any]:
    """Compute world-like anchor points from the head mesh (normalised units).

    The raw landmark rings from avatar_mesh index into the face vertices
    (verts are normalised so +y is up, ears on ±x, +z out of the face).
    """
    verts = mesh["verts"]
    lm = mesh["landmarks"]
    out: dict[str, Any] = {}
    n = verts.shape[0]

    def _avg(ids):
        import numpy as np
        idx = [i for i in ids if 0 <= i < n]
        return np.asarray(verts[idx]).mean(axis=0).tolist() if idx else [0.0, 0.0, 0.0]

    out["head"] = [0.0, 0.55, 0.0]
    out["face"] = [0.0, 0.05, 0.45]
    out["left_eye"] = _avg(lm.get("eye_l", []))
    out["right_eye"] = _avg(lm.get("eye_r", []))
    out["neck"] = _avg(list(range(mesh.get("n_head", n), n)))

    # Ear landmarks are part of the canonical MediaPipe 468 model but are not in
    # the avatar_mesh ring table; safe defaults keep the vocabulary complete.
    out.setdefault("left_ear", [float(verts[234][0]) if 234 < n else -0.7,
                                float(verts[234][1]) if 234 < n else 0.02,
                                float(verts[234][2]) if 234 < n else 0.4])
    out.setdefault("right_ear", [float(verts[454][0]) if 454 < n else 0.7,
                                 float(verts[454][1]) if 454 < n else 0.02,
                                 float(verts[454][2]) if 454 < n else 0.4])
    return out


def face_mesh_payload() -> dict:
    """Compact JSON-ready payload for the WebGL avatar (calls avatar_mesh once)."""
    from core.avatar_mesh import get_head_mesh

    mesh = get_head_mesh()

    def _epoch(attr: str) -> list:
        arr = mesh[attr].reshape(-1)
        return [float(x) for x in arr]

    payload = {
        "verts": _epoch("verts"),
        "faces": _epoch("faces"),
        "edges": _epoch("edges"),
        "jaw": _epoch("jaw"),
        "brow": _epoch("brow"),
        "fade": _epoch("fade"),
        "n_face": int(mesh["n_face"]),
        "n_head": int(mesh["n_head"]),
        "span": [float(mesh["span"][0]), float(mesh["span"][1])],
        "anchors": _landmark_centres(mesh),
    }
    return payload


FACE_ANCHORS: tuple[str, ...] = ANCHORS