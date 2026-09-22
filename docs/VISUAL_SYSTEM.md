# OPERO Visual Intelligence System

> Voice → understanding → visualisation → interaction. The 3D environment is a
> first-class communication channel, not an animation collection.

This document is the architecture reference for OPERO's visual layer. It is
implemented in stages; each stage ends green (tests, app runs, voice safe).

---

## 1. Where it lives

| Layer | Path | Role |
|---|---|---|
| Vocabulary + validator | `core/visual/registry.py`, `core/visual/intent.py` | The only things Gemini may say to the renderer |
| Director + events    | `core/visual/director.py`, `core/visual/events.py` | Validates, directs, falls back, never blocks voice |
| Assets               | `core/visual/assets.py`, `core/avatar_mesh.py` | One measured head geometry → JSON payload, both renderers |
| Gemini entry         | `actions/visualizer.py` (auto-discovered TOOL) | `visualize` tool call → validated intent |
| Qt bridge            | `ui/widgets.py` (`WebGLBackground`), `ui/window.py` | Directive + face payload into the 3D page |
| 3D renderer          | `site/web_background/index.html` + `avatar3d.js` | Real-time Three.js/WebGL scene (galaxy + presence) |
| 2D fallback          | `core/avatar.py`, `ui/widgets.py` (HudCanvas) | Unchanged; active when WebGL is unavailable |

## 2. Pipeline (Gemini NEVER renders)

```
Gemini "visualize(...)"            -- controlled words only
  -> core.visual.validate_intent() -- hard reject: unknown object/material/
                                      camera/mode/anchor/colour, bad bounds,
                                      oversized story, non-object args
  -> VisualIntent (dataclass)
  -> VisualDirector.apply_intent() -- emits events, sends directive, timers
  -> directive (pure data, e.g. {"op":"show","subject":"apple", ...})
  -> WebGLBackground.apply_intent() -> window.applyIntent(dir) in the page
  -> avatar3d.js builds the scene
```

No path exists from Gemini (or any string it controls) to execution of
rendering code, filesystem paths or shell commands. Directives only carry ids
from `core/visual/registry.py`.

## 3. The intent vocabulary (summary)

* `mode`: object_explanation · accessory · story · process · diagram · data ·
  system_action · transition
* `subject`: apple · sphere · cube · torus · cone · cylinder · capsule · icosa ·
  planet · sun · moon · sunglasses · watch · ring · necklace · hat · tree ·
  ground (each maps 1:1 to a builder in `avatar3d.js` — enforced by
  `tests/test_visual_assets.py`)
* `material`: holographic · glass · metal · matte · emissive · particle ·
  transparent
* `camera`: default · portrait · focus · orbit · zoom · closeup · wide ·
  top_down · side · inspection · cinematic · follow
* `animation`: rotate · assemble · dissolve · pulse · orbit · bounce ·
  highlight · scan · float · idle
* `color`: named token (gold, red, plant_green, ocean, …) or `#rrggbb`
* `attach`: body anchors (face, left_wrist, left_index, neck, head, …)
* `highlight`: tokens incl. interior reveals (`core`, `seeds`, `cutaway`, …)
* `story`: bounded (≤8 scenes · ≤6 objects) list of `{scene, appear, remove,
  duration}` with `scene` ∈ environments

Every validator bound lives in `LIMITS` (`registry.py`).

## 4. Safety

* **Visual intent is NOT authorisation.** The `visualize` action only shows
  things. Destructive commands still pass through OPERO's existing
  confirmation gate (`core/confirm.py`) untouched.
* Visualisation failure degrades to voice-only: the director catches every
  path, logs, publishes a `visual_error` event, and continues.
* No bridge → no-op (`renderer_mode=2d` / no WebGL / headless CI) with the
  QPainter avatar running exactly as before.

## 5. Renderer notes (avatar3d.js)

* The 3D presence shares the existing galaxy scene/renderer/camera
  (`window.__operoWorld`); no second WebGL context, no new dependency.
* The face is built from the *same* measured head geometry as the 2D avatar
  (`core/avatar_mesh` → JSON payload via `push_face_mesh`).
* All animation is transform-space (group rotation/scale/opacity + staged
  draw-ranges) — no per-frame vertex buffer writes; GPU-friendly.
* Particle morph (face ⇄ object) = paired static clouds cross-fading + scale
  growth (assemble) / shrink (dissolve) + object mesh fade-in.
* Camera rig owns the camera only while a scene is live; the galaxy loop
  resumes its own drift the rest of the time.
* Every public entry (`setFaceMesh`, `applyIntent`) is try/catch wrapped and
  reports into `getVisualDiagnostics()`.

## 6. Stage roadmap

- [x] **Phase 1** 3D avatar renderer (particles, wireframe, eyes, jaw/brow,
      blink, breath, look-at, states LISTENING/THINKING/PROCESSING/SPEAKING/
      VISUALIZING/STORY/RETURN)
- [x] **Phase 2** 3D object visualisations (procedural primitives +
      apple/planet/sun/moon + interior cutaway)
- [x] **Phase 3** semantic transitions (particle dissolve/assemble face⇄object,
      return-to-avatar)
- [x] **Phase 4** camera + animation system (12 modes, orbit, scan, pulse)
- [x] **Phase 9** Gemini → Visual Intent via the `visualize` action + strict
      validation
- [ ] **Phase 5** body rig with full anchor set (shoulders/wrist/fingers…)
      — anchors already in the vocabulary; the head mesh supplies
      eye/ear/face/neck today
- [ ] **Phase 6** accessory polish (walk-in animation, per-part material swap
      without rebuild, camera inspection)
- [ ] **Phase 7** multi-object scenes (object grouping, spatial layouts)
- [ ] **Phase 8** story/cinematic scenes (richer envs, characters, timeline
      sync with narration)
- [ ] **Phase 10** performance ladder + telemetry (particle budgets, LOD,
      resolution scaling, complexity caps)

## 7. Verify

```powershell
python -m pytest tests/test_visual_intent.py tests/test_visual_director.py tests/test_visual_assets.py -q
python -m compileall -q core/visual actions/visualizer.py main.py ui/widgets.py ui/window.py
node --check site/web_background/avatar3d.js
```

Manual smoke (on a WebGL-capable machine): run `python main.py`, say "What is
an apple?" or call `visualize` with `{"subject":"apple","mode":
"object_explanation"}` from a tool; the scene should morph avatar → red apple,
orbit, then dissolve back. `getVisualDiagnostics()` in the page console shows
the last directive and any renderer errors.