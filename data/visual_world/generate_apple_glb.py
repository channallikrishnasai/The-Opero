"""Author data/visual_world/assets/apple.glb — OPERO's bundled apple model.

Run:  python data/visual_world/generate_apple_glb.py

Provenance: procedurally authored for OPERO (this file is the source).
License:    CC0-1.0 — public domain dedication, no third-party geometry.

Geometry: a lathed apple body (cratered poles, faint five-lobe ridges), a
curved tapered stem, and a drooping leaf — three primitives, scalar PBR
materials, uint16 indices. That is exactly the GLB subset the renderer's
reader in site/web_background/index.html accepts: POSITION / NORMAL /
indices, no textures, no animation, no byteStride.
"""

import json
import math
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parent / "assets" / "apple.glb"

BODY_SEGMENTS = 36
STEM_SEGMENTS = 10
STEM_RINGS = 9
LEAF_SEGMENTS = 24


def _catmull(p0, p1, p2, p3, t):
    out = []
    for a, b, c, d in zip(p0, p1, p2, p3, strict=True):
        out.append(
            0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t * t * t)
        )
    return tuple(out)


def _smooth(profile, steps=4):
    pts = [profile[0]] + list(profile) + [profile[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        for s in range(steps):
            out.append(_catmull(pts[i - 1], pts[i], pts[i + 1], pts[i + 2], s / steps))
    out.append(tuple(profile[-1]))
    return out


def _lathe(profile, segments):
    positions, indices, rings = [], [], []
    for r, y in profile:
        if r <= 1e-6:
            rings.append([len(positions)])
            positions.append((0.0, y, 0.0))
        else:
            ids = []
            for j in range(segments):
                phi = 2 * math.pi * j / segments
                rr = r * (1.0 + 0.012 * math.cos(5 * phi))  # faint apple lobes
                ids.append(len(positions))
                positions.append((rr * math.cos(phi), y, rr * math.sin(phi)))
            rings.append(ids)
    for a, b in zip(rings, rings[1:], strict=False):
        if len(a) == 1:
            for j in range(segments):
                indices += [a[0], b[j], b[(j + 1) % segments]]
        elif len(b) == 1:
            for j in range(segments):
                indices += [a[j], b[0], a[(j + 1) % segments]]
        else:
            for j in range(segments):
                j2 = (j + 1) % segments
                indices += [a[j], b[j], b[j2], a[j], b[j2], a[j2]]
    return positions, indices


def _stem():
    positions, rings = [], []
    for i in range(STEM_RINGS):
        t = i / (STEM_RINGS - 1)
        cx = 0.075 * t * t + 0.015 * t
        cy = 0.58 + 0.37 * t
        cz = 0.03 * t
        radius = 0.05 - 0.024 * t
        ids = []
        for j in range(STEM_SEGMENTS):
            phi = 2 * math.pi * j / STEM_SEGMENTS
            ids.append(len(positions))
            positions.append((cx + radius * math.cos(phi), cy, cz + radius * math.sin(phi)))
        rings.append(ids)
    tip = len(positions)
    positions.append((0.09, 0.95, 0.03))
    indices = []
    for a, b in zip(rings, rings[1:], strict=False):
        for j in range(STEM_SEGMENTS):
            j2 = (j + 1) % STEM_SEGMENTS
            indices += [a[j], b[j], b[j2], a[j], b[j2], a[j2]]
    top = rings[-1]
    for j in range(STEM_SEGMENTS):
        indices += [top[j], tip, top[(j + 1) % STEM_SEGMENTS]]
    return positions, indices


def _leaf():
    axis = _unit((0.9, -0.18, 0.4))
    side = _unit((axis[2], 0.0, -axis[0]))  # horizontal perpendicular
    normal = _cross(axis, side)  # points up
    base = (0.0497, 0.846, 0.0216)  # stem attachment (t = 0.72)
    length, width = 0.5, 0.15
    center = tuple(base[k] + axis[k] * length * 0.42 for k in range(3))
    hx, hy = length / 2, width / 2
    positions, boundary = [center], []
    for j in range(LEAF_SEGMENTS):
        theta = 2 * math.pi * j / LEAF_SEGMENTS
        u, v = hx * math.cos(theta), hy * math.sin(theta)
        frac = (u + hx) / (2 * hx)
        p = [center[k] + axis[k] * u + side[k] * v for k in range(3)]
        for k in range(3):
            p[k] += normal[k] * 0.03 * (1 - (v / hy) ** 2)  # raised midrib
        p[1] -= 0.07 * frac * frac  # tip droop
        boundary.append(len(positions))
        positions.append(tuple(p))
    indices = []
    for j in range(LEAF_SEGMENTS):
        indices += [0, boundary[j], boundary[(j + 1) % LEAF_SEGMENTS]]
    return positions, indices


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normals(positions, indices):
    acc = [[0.0, 0.0, 0.0] for _ in positions]
    for i in range(0, len(indices), 3):
        ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
        a, b, c = positions[ia], positions[ib], positions[ic]
        n = _cross(
            (b[0] - a[0], b[1] - a[1], b[2] - a[2]),
            (c[0] - a[0], c[1] - a[1], c[2] - a[2]),
        )
        for idx in (ia, ib, ic):
            for k in range(3):
                acc[idx][k] += n[k]
    out = []
    for n in acc:
        length = math.sqrt(sum(c * c for c in n))
        out.append(tuple(c / length for c in n) if length > 1e-9 else (0.0, 1.0, 0.0))
    return out


def _pad4(data, filler):
    return data + bytes([filler]) * (-len(data) % 4)


def build() -> bytes:
    body_profile = _smooth(
        [
            (0.00, -0.74),
            (0.26, -0.76),
            (0.52, -0.70),
            (0.76, -0.55),
            (0.92, -0.33),
            (1.00, -0.08),
            (1.01, 0.16),
            (0.97, 0.38),
            (0.88, 0.56),
            (0.72, 0.68),
            (0.52, 0.71),
            (0.30, 0.66),
            (0.14, 0.63),
            (0.00, 0.62),
        ]
    )
    parts = [
        (
            "body",
            *_lathe(body_profile, BODY_SEGMENTS),
            {"baseColorFactor": [0.70, 0.06, 0.05, 1.0], "roughnessFactor": 0.38},
            False,
        ),
        ("stem", *_stem(), {"baseColorFactor": [0.30, 0.19, 0.08, 1.0], "roughnessFactor": 0.90}, False),
        ("leaf", *_leaf(), {"baseColorFactor": [0.14, 0.42, 0.10, 1.0], "roughnessFactor": 0.70}, True),
    ]

    bin_chunks, buffer_views, accessors, primitives, materials = [], [], [], [], []
    offset = 0
    for name, positions, indices, pbr, double_sided in parts:
        normals = _normals(positions, indices)
        pos_bytes = _pad4(struct.pack("<%sf" % (len(positions) * 3), *[c for p in positions for c in p]), 0)
        nrm_bytes = _pad4(struct.pack("<%sf" % (len(normals) * 3), *[c for n in normals for c in n]), 0)
        idx_bytes = _pad4(struct.pack(f"<{len(indices)}H", *indices), 0)

        view_ids = []
        for chunk in (pos_bytes, nrm_bytes, idx_bytes):
            buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(chunk)})
            view_ids.append(len(buffer_views) - 1)
            offset += len(chunk)
        bin_chunks += [pos_bytes, nrm_bytes, idx_bytes]

        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        accessors.append(
            {
                "bufferView": view_ids[0],
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )
        accessors.append({"bufferView": view_ids[1], "componentType": 5126, "count": len(normals), "type": "VEC3"})
        accessors.append({"bufferView": view_ids[2], "componentType": 5123, "count": len(indices), "type": "SCALAR"})
        primitives.append(
            {
                "attributes": {"POSITION": len(accessors) - 3, "NORMAL": len(accessors) - 2},
                "indices": len(accessors) - 1,
                "material": len(materials),
                "mode": 4,
            }
        )
        materials.append({"name": name, "pbrMetallicRoughness": pbr, "doubleSided": double_sided})

    binary = b"".join(bin_chunks)
    gltf = {
        "asset": {"version": "2.0", "generator": "opero data/visual_world/generate_apple_glb.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "apple", "mesh": 0}],
        "meshes": [{"name": "apple", "primitives": primitives}],
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binary)}],
    }
    json_chunk = _pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), 0x20)
    bin_chunk = _pad4(binary, 0x00)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return (
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(bin_chunk), 0x004E4942)
        + bin_chunk
    )


def self_check(glb: bytes) -> None:
    assert struct.unpack_from("<I", glb, 0)[0] == 0x46546C67, "bad magic"
    assert struct.unpack_from("<I", glb, 4)[0] == 2, "bad version"
    assert struct.unpack_from("<I", glb, 8)[0] == len(glb), "length mismatch"
    json_len = struct.unpack_from("<I", glb, 12)[0]
    doc = json.loads(glb[20 : 20 + json_len].decode("utf-8"))
    binary = glb[20 + json_len + 8 :]
    assert doc["asset"]["version"] == "2.0"
    assert len(doc["meshes"][0]["primitives"]) == 3, "expected body, stem, leaf"
    triangles = 0
    xs, ys, zs = [], [], []
    for prim in doc["meshes"][0]["primitives"]:
        pos = doc["accessors"][prim["attributes"]["POSITION"]]
        view = doc["bufferViews"][pos["bufferView"]]
        start = view["byteOffset"]
        coords = struct.unpack_from("<%sf" % (pos["count"] * 3), binary, start)
        assert start + view["byteLength"] <= len(binary), "buffer view out of range"
        xs += list(coords[0::3])
        ys += list(coords[1::3])
        zs += list(coords[2::3])
        idx = doc["accessors"][prim["indices"]]
        triangles += idx["count"] // 3
    assert triangles > 1600, f"only {triangles} triangles — a lathe apple needs thousands"
    assert max(map(abs, xs)) < 1.15 and max(map(abs, zs)) < 1.15, "model must fit the anchor"
    assert min(ys) >= -0.8 and max(ys) <= 1.0, "unexpected vertical extent"


if __name__ == "__main__":
    glb = build()
    self_check(glb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(glb)
    print(f"wrote {OUT} ({len(glb):,} bytes) — self-check passed")
