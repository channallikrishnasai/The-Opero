# OPERO — Development Phases (Master Roadmap)

| | |
|---|---|
| Document | PHASES.md (4 of 6) |
| Status | Living roadmap; ordered by dependency, not ambition |
| Evidence rule | A phase is marked IMPLEMENTED only with repository evidence (commit / files / tests) |

**Status legend:** `IMPLEMENTED` = verified in code · `PARTIAL` = some verified pieces, exit criteria unmet · `PLANNED` = not started · phase numbers are stable identifiers, not dates.

---

## Dependency overview

```text
PHASE 0  Repository baseline ─────────────────────────────── IMPLEMENTED
PHASE 1  Visual World Model ──────┐
PHASE 2  Visual Intent ───────────┤
PHASE 3  Asset Registry ──────────┼─► PHASE 4 Perception & Routing ─► PHASE 5 Three.js Bridge
                                  │            (all IMPLEMENTED)         │
                                  └──────────────────────────────────────┘
                                                                      ▼
                                              PHASE 6 Runtime stabilization ◄── DONE
                                                                      │
        ┌───────────────┬───────────────┬─────────────────────────────┤
        ▼               ▼               ▼                             ▼
 PHASE 7 Face↔3D   PHASE 8 Visual   PHASE 14 Semantic          PHASE 17 Performance
        │           Director         Retrieval                  (starts partial now)
        ▼               │                   │
 PHASE 16 Cinematic ◄───┘          PHASE 15 Visual Memory
        │
        ▼
 PHASE 9 Inspection ─► 10 Process/Causal ─► 11 Body/Systems ─► 12 Teaching ─► 13 ISL
 (schema exists)        (schema exists)      (needs assets)    (needs 10,11)  (needs 12 + verified data)

 PHASE 18 Accessibility (continuous from 7)   PHASE 19 Production hardening (last)
```

Ordering rationale: everything visual depends on 1–5 (done); **6 is the gate before any new feature work** because it owns the failing test, the version mismatch, and lint debt that would compound; the director (8) sequences transitions (7) before cinematic (16); teaching (12–13) needs inspected objects (9–11) and verified data sources.

---

## PHASE 0 — Repository Baseline

**Status: IMPLEMENTED** (CI, tests, packaging present; debt recorded in `ARCHITECTURE.md` §16)

| | |
|---|---|
| Goal | A buildable, tested, packaged repository that changes safely |
| Why | Nothing can be added credibly without a baseline that proves it didn't break |
| Dependencies | none |
| Scope | `pyproject.toml`, test suite, GitHub Actions CI, PyInstaller/NSIS packaging, docs (`README`, `CONTRIBUTING`, `docs/`) |
| Deliverables | full test suite; CI matrix 3.11–3.13 (`compileall` → `ruff F821` → `pytest`); `OPERO.spec`; `installer/opero.nsi` |
| Tests | `tests/` (27 files) green; the recorded `test_landing_page` failure was resolved in Phase 6B |
| Acceptance | CI runs on push/PR; package builds are reproducible via `packaging/build-windows.ps1` |
| Non-goals | Full lint cleanliness (owned by Phase 6); cross-platform packaging |
| Exit criteria | ✅ met at specification time, with Phase 6 debt explicitly tracked |

---

## PHASE 1 — Visual World Model

**Status: IMPLEMENTED** (commit `44906f1 feat(visual): add visual world model`)

| | |
|---|---|
| Goal | Deterministic, serializable, session-scoped state for what exists in the visual scene |
| Why | Without "what exists", every visual request would improvise objects — no identity, no reuse, no truth |
| Dependencies | Phase 0 |
| Scope | `core/visual/concepts.py`, `core/visual/world_model.py`, `data/visual_world/concepts/*.json` |
| Deliverables | JSON concept vocabulary; `Entity` with deterministic IDs (`apple_01`); transforms; part visibility; relationships; `to_dict`/`from_dict`; thread safety |
| Tests | `tests/test_visual_world_model.py` (20 tests: IDs, parts, transforms, relationships, serialization, concurrency, malformed concepts) |
| Acceptance | Unknown concepts raise; IDs are stable and unique under concurrency; round-trip serialization preserves the world |
| Non-goals | Rendering, physics, cross-session persistence, semantic embeddings |
| Exit criteria | ✅ met (commit `44906f1`) |

---

## PHASE 2 — Visual Intent

**Status: IMPLEMENTED** (commit `3298ac6 feat(visual): add visual intent schema`)

| | |
|---|---|
| Goal | A renderer-independent, validated contract that says WHAT to show, never HOW |
| Why | Separates reasoning from rendering; blocks executable content from crossing the AI boundary |
| Dependencies | Phase 1 |
| Scope | `core/visual/intent.py` |
| Deliverables | `VisualIntent` dataclass; modes/actions/camera/animation enums; combination validation; `from_dict`/`to_dict`; `resolve_entity_id` (never invents entities) |
| Tests | `tests/test_visual_intent.py` (20 tests incl. malformed payloads, FACE_ONLY restrictions, target rules, entity resolution) |
| Acceptance | Invalid combinations rejected with `IntentValidationError`; no field can carry code; serialization round-trips |
| Non-goals | Execution of intents (Phase 5), multi-intent sequencing (Phase 8) |
| Exit criteria | ✅ met (commit `3298ac6`) |

---

## PHASE 3 — Asset Registry

**Status: IMPLEMENTED** (commit `f0d498f feat(visual): add asset registry`)

| | |
|---|---|
| Goal | A truthful catalogue of 3D assets with provenance, licensing, and verification |
| Why | The real-object principle needs an authority: what assets exist, where they came from, whether they're verified |
| Dependencies | Phase 1 |
| Scope | `core/visual/assets.py`, `data/visual_world/assets/`, `data/visual_world/generate_apple_glb.py` |
| Deliverables | `AssetRecord`/`AssetRegistry`; GLB/GLTF formats; status + verification as separate axes; deterministic selection; path safety; JSON round-trip; bundled `apple_default` (CC0-1.0) |
| Tests | `tests/test_visual_assets.py` (14 tests incl. missing/duplicate/invalid, existence-vs-verification, deterministic multi-asset selection, path escapes) |
| Acceptance | Unavailable assets are structured states, not crashes; registry overrides stale concept references; licensing recorded |
| Non-goals | Asset generation/acquisition pipelines (Phase 14), CDN/remote fetching |
| Exit criteria | ✅ met (commit `f0d498f`) |

---

## PHASE 4 — Perception & Visual Routing

**Status: IMPLEMENTED** (commits `b3edaac feat(perception): add visual routing and desktop perception foundation`, `d18e979 fix(perception): stabilize screen capture contract`)

| | |
|---|---|
| Goal | (a) explicit, observation-only desktop perception; (b) deterministic routing of explicit visual requests to the visual layer |
| Why | Perception grounds answers in the real desktop; routing guarantees "show me an apple" never degrades into a web search |
| Dependencies | Phases 1–3 |
| Scope | `core/perception/` (screen, windows, context, errors); `core/visual/routing.py`; `SEARCH_GUARD_TOOLS` integration in `main.py` |
| Deliverables | One-shot `capture_screen` (bytes never serialized into contexts); window/browser metadata probes; `VisualRouter` with lexical matching + must-route rejection; `route_search_request` guard wired before dispatch |
| Tests | `tests/test_perception.py`, `tests/test_screen_capture.py`, `tests/test_visual_routing.py` (6 tests: routing, entity reuse, no-search guarantee, unknown-concept rejection, utterance extraction) |
| Acceptance | Captures never auto-forward; explicit visual request can never reach `web_search`/`youtube_video`/`browser_control` as a search |
| Non-goals | Continuous monitoring loops, model-based visual judgment (Phase 8) |
| Exit criteria | ✅ met (commits `b3edaac`, `d18e979`) |

---

## PHASE 5 — Three.js Visual Bridge

**Status: IMPLEMENTED (MVP) — RUNTIME VERIFIED (Phase 7 verification session)** (commit `b3affe3 feat(visual): bridge world model to threejs`; on-screen SHOW of `apple.glb` verified live in the canonical desktop app after the HUD-occlusion fix — `ARCHITECTURE.md` §7.7/§16.8)

| | |
|---|---|
| Goal | Move a validated intent from Python into the existing Three.js scene as one structured command |
| Why | Without the bridge, all previous phases are inert; this is the first end-to-end "apple appears" capability |
| Dependencies | Phases 1–4 |
| Scope | `core/visual/bridge.py`; Qt transport (`ui/proxy.py` → `ui/window.py` → `ui/widgets.py::execute_visual`); renderer handler `window.operoVisual` in `site/web_background/index.html`; `main.py` wiring (L560–566, L1347–1380) |
| Deliverables | Six wired actions (`SHOW HIDE ROTATE ZOOM FOCUS RETURN_TO_FACE`); base64 GLB transport with header validation; structured failure taxonomy; renderer-side GLTF loading, entity records, camera blend; no-op fallback without WebEngine |
| Tests | `tests/test_visual_bridge.py` (13 tests: real asset reaches renderer, entity reuse, structured failures for concept/asset/corruption/transport, hide/rotate/zoom/focus/return_to_face) |
| Acceptance | End-to-end: utterance → intent → entity → asset → command → scene; every failure path returns `{success:false, error, message}` |
| Non-goals | Remaining 8 intents + 9 camera presets + 11 animations (Phases 8–10); face↔object transition (Phase 7) |
| Exit criteria | ✅ MVP met (commit `b3affe3`); full action parity tracked under Phases 8–10 |

---

## PHASE 6 — Runtime Stabilization

**Status: COMPLETE (Phase 6A + 6B)** — 6A: Python >=3.11 enforced (startup guard `core/python_guard.py`, README/pyproject/CI aligned, stale 3.10 `venv/` + mixed bytecode purged, F821 gate green, guard tests added). 6B: landing-page contract reconciled to `public/` (test + `site/README.md` + README corrected), full suite green (213/213), ARCHITECTURE/CONTRIBUTING/PRD counts and runtime claims corrected, StrEnum shims recorded as a KEEP decision, F821-only lint policy documented. **Deviations:** the stale `apple.json` asset note refresh is deferred (the registry override is tested and operative — ARCHITECTURE §16.3); StrEnum "consolidation into one module" resolved instead as keep-by-decision (§16.2); full ruff/format cleanup remains recorded deferred debt (§16.5).

| | |
|---|---|
| Goal | Make the runtime honest and clean: no failing tests, one declared Python version, no silent cache traps, bounded lint debt |
| Why | Every future phase compounds this debt; the StrEnum/stale-`.pyc` incident and the failing landing test prove instability is already costing time |
| Dependencies | Phases 0–5 (in place) |
| Scope | Fix `tests/test_landing_page.py` vs `netlify.toml` divergence; decide Python floor (3.11 per `pyproject` vs 3.10 shims/README) and apply consistently; document/purge `__pycache__` hazards; refresh stale `apple.json` asset note; `ruff check`/`ruff format` policy (fix or formally defer with CI gate decisions); `StrEnum` shim consolidation into one compatibility module |
| Deliverables | Green full suite (213/213 at Phase 6B); single declared Python version across `pyproject`, README; lint policy documented (F821 gate enforced, broader debt deferred); `ARCHITECTURE.md` §16 items resolved or re-labeled |
| Tests | Full `pytest` green; CI lint gate unchanged or tightened deliberately |
| Acceptance | `python -m pytest tests -q` → 0 failures; no version contradictions in metadata; ruff debt plan recorded |
| Non-goals | New features; full reformat of 160 files **unless** the phase explicitly chooses the one-time format commit |
| Exit criteria | Full suite green (213/213 at Phase 6B); version story consistent; §16 contradictions resolved or re-labeled; CI enforces the agreed gates (F821) |

---

## PHASE 7 — Face ↔ 3D Transition

**Status: PLANNED** (only primitive hooks exist: `RETURN_TO_FACE` command; Qt face and WebGL scene are separate layers)

| | |
|---|---|
| Goal | Cinematic, honest transition between the OPERO face/default state and a visualization — and back |
| Why | Face-first principle (`PRD.md` §4) requires the face to yield to visualization *deliberately* and reclaim the stage when done |
| Dependencies | Phase 5; Phase 6 |
| Scope | Renderer: staged transition states (holographic energy → mesh/particle transform → camera move → object assembly); reverse on return; Qt/HUD coordination so the face doesn't double-render during a scene; `set_state("…")` transition palette |
| Deliverables | Transition state machine in `window.operoVisual` vocabulary; Python-side `VisualBridge` commands for transition phases; interruption safety (user abort returns to face mid-transition) |
| Tests | Bridge tests for new commands; renderer-side transition unit checks; failure: transition abort always lands on a usable face/default state |
| Acceptance | "show me an apple" visibly transitions face→scene; "go back to my face" reconstructs default state; no stuck-camera or black-screen path |
| Non-goals | Redesigning the avatar mesh; replacing the HUD; audio-reactive face redesign |
| Exit criteria | Documented transition sequence implemented, tested, and interruptible in both directions |

---

## PHASE 8 — Visual Director

**Status: PLANNED** (role reserved in `core/visual/intent.py` docstring; nothing named Visual Director exists)

| | |
|---|---|
| Goal | A component that decides HOW to visualize: applies the `PRD.md` §5 criteria, sequences intents, enforces budgets |
| Why | The lexical router answers only "was this explicitly requested"; value judgments (spatial/structural/causal…) and multi-step explanations need an orchestrated layer |
| Dependencies | Phase 2 (intent), Phase 5 (bridge), Phase 6 |
| Scope | New `core/visual/director.py` (name as implemented): consume router output + model-classified intent; produce ordered `VisualIntent` sequences; per-sequence step/time/asset budgets; interrupt handling; wire the remaining validated actions (MOVE, HIGHLIGHT, ISOLATE, CUTAWAY, PAUSE, RESUME, REPLAY, SLOW) through bridge + renderer |
| Deliverables | Director with deterministic fallback (router behavior preserved when director unavailable); action-parity between schema, bridge, and renderer; camera preset wiring (INSPECTION, SIDE, TOP_DOWN, …) |
| Tests | Director decision tests (criterion → intent); budget-exhaustion tests; schema↔bridge↔renderer parity tests; regression: routing behavior unchanged |
| Acceptance | No sequence exceeds configured budgets; every schema action either executes or returns structured `unsupported_action`; visual requests still never reach search |
| Non-goals | Teaching modes (12); cinematic pacing (16); changing the action system |
| Exit criteria | Director green on its test matrix; parity report shows zero silent gaps |

---

## PHASE 9 — Object Inspection

**Status: PLANNED (schema PARTIAL)** — `OBJECT_INSPECTION` mode, `CUTAWAY`/`ISOLATE` actions, `INSPECTION` camera preset exist in `core/visual/intent.py` but return `unsupported_action` downstream

| | |
|---|---|
| Goal | "Show me inside" — cutaway, isolate parts, inspect components of a real object |
| Why | First high-value explanatory mode beyond show/rotate; exercises parts model end-to-end |
| Dependencies | Phase 8 (director wiring); concept vocabulary needs ≥1 multi-part inspectable asset beyond the apple |
| Scope | Renderer cutaway (clip plane or part hiding), isolation focus, part labels; bridge support for CUTAWAY/ISOLATE/HIGHLIGHT; concept enrichment (parts with metadata) |
| Deliverables | Inspection scenes for available assets; part-level targeting through `target_part`; camera INSPECT preset behavior |
| Tests | Bridge/renderer tests per action; part visibility integration; structured failure when a concept lacks the requested part |
| Acceptance | "hide everything except the piston" style commands work on assets that declare those parts; missing parts fail explicitly |
| Non-goals | Full engine anatomy (needs assets from Phase 11 library work); physics |
| Exit criteria | ≥2 assets fully inspectable with tests; no `unsupported_action` for inspection verbs declared in scope |

---

## PHASE 10 — Process & Causal Visualization

**Status: PLANNED (schema PARTIAL)** — `PROCESS` and `CAUSAL_CHAIN` modes exist as enum values only

| | |
|---|---|
| Goal | Render ordered processes and causal chains as spatial scenes (stages, arrows, propagation) |
| Why | Causal/explanatory value criteria (`PRD.md` §5 #3, #6) — the main non-object explanation type |
| Dependencies | Phase 8; Phase 5 |
| Scope | Node/edge scene primitives in the existing renderer (built from JSON data, not generated code); director modes `PROCESS`/`CAUSAL_CHAIN`; template scene layouts |
| Deliverables | Declarative process/causal scene schema (data → scene); replay/slow controls (already in intent enum) wired |
| Tests | Data→scene validation; malformed graph structured failure; determinism (same data → same scene) |
| Acceptance | A 3–5 stage process and a 3-node causal chain render, replay, and return to face with full test coverage |
| Non-goals | Arbitrary node-graph editor; physics simulation of chains |
| Exit criteria | Both modes demonstrated end-to-end with tests |

---

## PHASE 11 — Body / System Visualization

**Status: PLANNED** (no anatomy concepts, assets, or data exist)

| | |
|---|---|
| Goal | Anatomically honest body-system scenes: heart, lungs, systems with motion cycles |
| Why | Relational + temporal value criteria; the flagship teaching domain in `PRD.md` §7 |
| Dependencies | Phase 9 (inspection), Phase 10 (process cycles); Asset Registry provenance rules (`RULES.md` §4); verified medical sources (`RULES.md` §5) |
| Scope | Concept JSONs + verified/provenanced anatomy assets; beat/breath animation as declarative cycles; labels |
| Deliverables | ≥2 verified anatomy assets registered & verified; concept definitions with parts; heart-cycle and lung-cycle scenes |
| Tests | Registry provenance completeness (no asset without source/license); scene determinism; factual-source metadata presence |
| Acceptance | Anatomy scenes render only from assets marked verified with recorded sources; no fabricated structures |
| Non-goals | Diagnostic/medical advice; patient-specific content; unverified model zoos |
| Exit criteria | Two verified anatomy scenes shipped with provenance tests green |

---

## PHASE 12 — Teaching / Instruction Mode

**Status: PLANNED** (schema PARTIAL: `INSTRUCTION` mode + `narration_sync` flag exist as fields only)

| | |
|---|---|
| Goal | Structured lessons: OPERO introduces → demonstrates → labels → narrates synchronized → replays → quizes |
| Why | Converts visualization into instruction; foundation for ISL (13) and personalized learning (`MEMORY.md` §3) |
| Dependencies | Phase 8 (sequencing), Phase 10 (procedural scenes), Phase 11 (for anatomy content), Phase 6 |
| Scope | Lesson script schema (steps: show/camera/label/narrate/quiz); playback controller through director; narration sync via `narration_sync`; progress recording in memory (user-facing, controllable) |
| Deliverables | `INSTRUCTION` mode executable; lesson data format; replay/slow/isolate controls; practice-step prompts |
| Tests | Lesson validation (steps, targets, budgets); playback interruption returns to face; progress persistence tests |
| Acceptance | A sample lesson runs start→finish with narration sync and replays deterministically |
| Non-goals | Curriculum generation by the model without review; ISL specifics (Phase 13) |
| Exit criteria | One complete lesson executed end-to-end with tests |

---

## PHASE 13 — ISL Teaching

**Status: PLANNED** (no ISL data, hand rigs, or sign assets exist)

| | |
|---|---|
| Goal | Teach Indian Sign Language with 3D hands: LEFT/RIGHT labels, synchronized narration, replay/slow/camera/isolate, practice mode |
| Why | Signature use case (`PRD.md` §8); highest bar for factual integrity in the product |
| Dependencies | Phase 12 (lesson engine); hand rig assets with finger-level parts; **verified ISL data from authoritative sources (ISLRTC or cited equivalents)** |
| Scope | Hand model assets (provenanced); sign data format with per-sign provenance; lesson playback; practice prompts; strict refusal when no verified sign exists |
| Deliverables | ≥1 verified sign lesson; provenance record per sign (source, citation, verification state); refusal path tested |
| Tests | **Data-truth tests**: every rendered sign has provenance fields; missing-source signs refuse; Gemini output never enters sign-form data |
| Acceptance | A sign is demonstrated only from verified data; `RULES.md` §5 compliance demonstrated by tests |
| Non-goals | Full ISL corpus; automatic sign generation; model-authored gestures |
| Exit criteria | Verified lesson shipped; fabrication-prevention tests green |

---

## PHASE 14 — Semantic / Visual Retrieval

**Status: PLANNED** (only lexical `search_memory` exists today)

| | |
|---|---|
| Goal | Retrieve concepts, assets, and past scenes by meaning — while keeping semantic space distinct from geometry |
| Why | "Show me something like the thing from yesterday" needs similarity, not exact keys; also the image→concept→3D entry point |
| Dependencies | Phase 1 (world model), Phase 3 (registry), Phase 6 |
| Scope | Embedding index for **concept/asset/lesson metadata only** (not geometry); mapping layer meaning → concept → entity (representations 1→2, `ARCHITECTURE.md` §7.8); optional image→concept classification wired to registry lookup |
| Deliverables | Retrieval API with provenance-tagged results; explicit separation tests (embedding ≠ mesh); image→concept→asset demonstrator |
| Tests | Retrieval ranking sanity; provenance on every result; **no fabricated concept matches** (unknown → structured miss) |
| Acceptance | Similarity queries return registry-backed objects or honest misses; documents never claim geometry is derived from embeddings |
| Non-goals | Vector DB dependency without justification (`RULES.md` §1.9); text→3D generation |
| Exit criteria | Retrieval demonstrator green with provenance tests; separation-of-representations test suite |

---

## PHASE 15 — Visual Memory

**Status: PLANNED (serialization PARTIAL)** — world model `to_dict`/`from_dict` exist; nothing persists across sessions

| | |
|---|---|
| Goal | Remember what the user saw: entities, scenes, outcomes, teaching progress — with identity continuity (`apple_01` stays `apple_01`) |
| Why | Personalized teaching (`MEMORY.md` §3) and "the object from yesterday" need durable visual history |
| Dependencies | Phase 1 (serialization), Phase 14 (retrieval), Phase 12 (progress records) |
| Scope | Session-end persistence of world-model snapshots; `VisualMemory` records (`entity_id, concept_id, session_id, properties, transform, relationships, visual_state, provenance` — `MEMORY.md` §4); restoration semantics (restored ≠ live: re-hydration must re-validate assets); user controls (view/clear/export) |
| Deliverables | Persistence adapter behind the existing `to_dict`/`from_dict`; memory overlay integration; bounds (retention limits, cleanup) |
| Tests | Store-recreation round trips; stale-asset handling on restore; user deletion actually deletes; no fabricated history |
| Acceptance | A scene survives app restart with honest status for assets that disappeared; clearing visual memory removes it |
| Non-goals | Rewriting `memory_manager.py`; cross-machine sync; hidden persistence |
| Exit criteria | Restart-survival + clear + provenance tests green |

---

## PHASE 16 — Cinematic Story Mode

**Status: PLANNED** (renderer has a `CINEMATIC` palette state; nothing drives it)

| | |
|---|---|
| Goal | Directed explanations: camera choreography, staged reveals, pacing — story-grade but honest |
| Why | Highest explanatory-value experiences (`PRD.md` §7 "cinematic explanation") |
| Dependencies | Phase 7 (transitions), Phase 8 (director), Phase 10 (content graphs) |
| Scope | Director timeline API (camera keyframes from the existing preset vocabulary + blends); stage timing; narration hooks; strict budgets so cinema never hides that data ended |
| Deliverables | Story playback over the existing renderer; abort/return-to-face at any stage; `CINEMATIC` state finally driven |
| Tests | Timeline validation; abort mid-story returns to face; no fabricated continuation past content end |
| Acceptance | A 3-stage story plays, pauses, aborts, and returns cleanly; pausing a story never leaves camera locked |
| Non-goals | Video export; timeline editor UI (future) |
| Exit criteria | One scripted story end-to-end with abort tests green |

---

## PHASE 17 — Performance / LOD / Caching

**Status: PARTIAL (IMPLEMENTED pieces)** — renderer already has adaptive quality (FPS-gated `applyQuality`), `document.hidden` pause, `dt` clamping, bloom lerp smoothing; the rest is PLANNED

| | |
|---|---|
| Goal | Visuals stay smooth on modest hardware: LOD, pooling, culling, lazy loading, caching, throttling, resolution scaling, cleanup |
| Why | A stuttering explanation undermines trust more than no explanation (`DESIGN.md` §9) |
| Dependencies | Phase 5 (baseline scene), grows with 7–16 |
| Scope | Metrics (frame time, GPU, asset bytes); asset cache with size ceiling (bridge file-URL switch past ~500 KB, already flagged in code); instancing/pooling for nodes; frustum culling audits; animation throttling under load; disposal of hidden objects; resolution scaling rung |
| Deliverables | Performance budget document + measured baselines; cache layer with eviction; object lifecycle audit (no leaks after N show/hide cycles) |
| Tests | Leak test (show/hide cycles → object count stable); cache eviction test; quality-rung regression test |
| Acceptance | 60-second mixed scene session with stable memory; budgets met on reference hardware |
| Non-goals | New renderer; WebGPU migration |
| Exit criteria | Leak + budget tests green; measured report attached to the phase |

---

## PHASE 18 — Accessibility

**Status: PLANNED** (no reduced-motion, keyboard-nav, or contrast audit exists for the visual system)

| | |
|---|---|
| Goal | The visual system is usable by people who need reduced motion, keyboard control, high contrast, or no animation at all |
| Why | Product requirement (`PRD.md` §1.5); color/animation must never be the only channel (`DESIGN.md` §7) |
| Dependencies | Phase 7 (transition must have a non-animated path); continuous from then |
| Scope | Reduced-motion setting (kills particle/transition animation, keeps information); full keyboard path for scene controls; contrast-checked palette; text labels for every visual state; non-animation alternatives (static labeled diagram fallback); ARIA-ish labeling in the WebEngine page |
| Deliverables | Accessibility settings surface; fallback renderer path (static labeled view); state→text transcripts of scenes |
| Tests | Reduced-motion flag suppresses animation commands; keyboard traversal coverage; contrast values recorded |
| Acceptance | Every visual state reachable and understandable with animation disabled and keyboard only |
| Non-goals | Screen-reader certification (track separately); OS-level accessibility integration |
| Exit criteria | Checklist in `DESIGN.md` §8 fully demonstrated with tests |

---

## PHASE 19 — Production Hardening

**Status: PARTIAL (IMPLEMENTED pieces)** — installer (NSIS + PyInstaller), CI matrix, boot sentry/crash records, shutdown handlers exist; the rest is PLANNED

| | |
|---|---|
| Goal | Ship-quality operations: reliability, upgrade safety, observability, supportability |
| Why | A demo that crashes on upgrade is not an operating layer |
| Dependencies | All prior phases (or at least 0–8 for a first hardening pass) |
| Scope | Structured diagnostics surface (`diagnostics` object in the 3D page extended app-wide); crash-report redaction (never leak keys/tokens — `RULES.md` §5); upgrade/migration for memory + visual persistence (15); secret hygiene audit (`config/.email_key` handling, API key stores); release checklist; performance/accessibility gates in CI |
| Deliverables | Redacted diagnostic bundle; migration tests for on-disk stores; release runbook (`docs/OPERATOR_RUNBOOK.md` extended) |
| Tests | Migration tests; redaction tests (keys never appear in diagnostics); upgrade smoke test |
| Acceptance | Install → run → upgrade → run path verified; diagnostics contain no secrets |
| Non-goals | Telemetry/cloud backend; multi-user licensing |
| Exit criteria | Release checklist executed once with recorded evidence |

---

## Summary

| Phase | Name | Status |
|---|---|---|
| 0 | Repository Baseline | IMPLEMENTED |
| 1 | Visual World Model | IMPLEMENTED (`44906f1`) |
| 2 | Visual Intent | IMPLEMENTED (`3298ac6`) |
| 3 | Asset Registry | IMPLEMENTED (`f0d498f`) |
| 4 | Perception & Visual Routing | IMPLEMENTED (`b3edaac`, `d18e979`) |
| 5 | Three.js Visual Bridge | IMPLEMENTED MVP (`b3affe3`) |
| 6 | Runtime Stabilization | **IMPLEMENTED (6A `05874b1` + 6B)** |
| 7 | Face ↔ 3D Transition | PLANNED (hooks exist) |
| 8 | Visual Director | PLANNED (role reserved) |
| 9 | Object Inspection | PLANNED (schema partial) |
| 10 | Process & Causal | PLANNED (schema partial) |
| 11 | Body / System | PLANNED |
| 12 | Teaching / Instruction | PLANNED (schema partial) |
| 13 | ISL Teaching | PLANNED |
| 14 | Semantic / Visual Retrieval | PLANNED |
| 15 | Visual Memory | PLANNED (serialization partial) |
| 16 | Cinematic Story Mode | PLANNED (palette only) |
| 17 | Performance / LOD / Caching | PARTIAL (adaptive quality exists) |
| 18 | Accessibility | PLANNED |
| 19 | Production Hardening | PARTIAL (installer/CI/sentry exist) |
