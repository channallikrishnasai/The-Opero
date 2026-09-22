import re

src = open("The-Opero/site/web_background/three.min.js", encoding="utf-8", errors="ignore").read()

# Names of interest (exported as t.<Name> or t.<Name>=class ...)
wanted = [
    "Points", "PointsMaterial", "LineSegments", "PointSegments", "EdgesGeometry",
    "CircleGeometry", "Float32BufferAttribute", "MeshBasicMaterial",
    "LineBasicMaterial", "PointsMaterial", "Group", "Mesh", "Line", "Scene",
    "PerspectiveCamera", "BufferGeometry", "TorusGeometry", "IcosahedronGeometry",
    "SphereGeometry", "OctahedronGeometry", "PlaneGeometry", "BoxGeometry",
    "RingsGeometry", "CylinderGeometry", "ConeGeometry", "CapsuleGeometry",
    "ShaderMaterial", "AdditiveBlending", "SubtractiveBlending", "DoubleSide",
    "BackSide", "FrontSide", "QuadsGeometry", "Vector3", "Color", "PointsGeometry",
]

# The export tail is all `t.NAME=...` assignments.  Find each generically.
found = {}
for name in wanted:
    found[name] = ("t.%s=" % name) in src

# Also find method names used for vertex updates on buffer attributes.
for meth in ["setDirty", "putRawArray", "updateDataBuffer", "markUpload",
             "setNeedsUpload", "copyFromVector3Array", "convertFromVector3Array",
             "cloneData", "deflate"]:
    found[meth] = ("%s(" % meth) in src

for k, v in found.items():
    print(("%-28s %s" % (k, "FOUND" if v else "missing")))

# Any PointsMaterial-like export nearby
m = re.search(r"t\.([A-Za-z]+Material)=class", src)
print("sample material export:", m.group(1) if m else None)