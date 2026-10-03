# OPERO — Technical Architecture

| | |
|---|---|
| Document | ARCHITECTURE.md (2 of 6) |
| Status | Authoritative for CURRENT architecture |
| Evidence rule | Every CURRENT claim verified against code at specification time (branch `abc`; last audited at commit `05874b1`, reconciled in Phase 6B) |
| Labels | **CURRENT** = verified in code · **PLANNED** = specified, not implemented · **DEFERRED** = intentionally postponed |

Related: `PRD.md`, `RULES.md`, `PHASES.md`, `DESIGN.md`, `MEMORY.md`.

---

## 1. System overview

```text
┌────────────── OPERO desktop process (Python 3.11+, enforced at startup) ───────────────┐
│ main.py ── OperaLive (live session controller)                                         │
│   ├── OWNS the Gemini Live session inline AND the effective dispatcher:                │
│   │     TOOL_DECLARATIONS (main.py L325) → _execute_tool (main.py L1338, tool-call     │
│   │     loop L1850) → inline tools / action registry / plugin registry                 │
│   ├── core/live_reconnect.py · core/echo.py · core/viseme.py · core/wake_word.py       │
│   ├── core/assemblyai_voice.py  (AssemblyAI path, function-level import)               │
│   ├── core/action_loader.py ── actions/*.py  (TOOL dict discovery)                     │
│   ├── core/plugin_loader.py ── plugins/*.py                                            │
│   │     └── safety: core/confirm.py · core/undo.py (UI-issued, never model-forgeable)  │
│   ├── core/visual/  router → intent → world model → assets → bridge                    │
│   ├── core/perception/  PARTIAL — one lazy import (get_active_window) in               │
│   │        actions/screen_processor.py; otherwise test-only                             │
│   └── memory/memory_manager.py  bounded, categorized recall                            │
│                                                                                        │
│ ui/ ── OperaUI (ui/proxy.py) → MainWindow (ui/window.py, PyQt6)                        │
│   ├── HudCanvas (ui/widgets.py)  face / orb / core centrepiece                          │
│   ├── WebGLBackground (ui/widgets.py)  QWebEngineView → 3D page                         │
│   └── overlays / theme / panels                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │  structured JSON visual commands (never AI-generated executable JS)
        ▼
 Three.js r128 scene (WebGL): galaxy background + window.operoVisual(cmd)

ORPHANED / NOT ON CURRENT RUNTIME PATH (retained deliberately, not wired; see §3):
 core/session.py · core/session_reconnect.py · core/tool_dispatch.py · core/stt.py ·
 core/tts.py · core/audio_pipeline.py · core/llm_client.py · core/validator.py
```

Two hard boundaries define the system:

1. **Action path vs visual path** — actions run through the dispatcher and safety gates; visuals run through the intent/bridge pipeline into the renderer. Neither crosses into the other (`RULES.md` §1.4–1.5).
2. **Python vs JavaScript** — Python owns reasoning, intent, world model, registry, safety, orchestration; JavaScript/Three.js owns rendering, scene, camera, animation, GPU (§12).

---

## 2. Desktop architecture — CURRENT

| Layer | Implementation |
|---|---|
| Entry point | `main.py` → `main()` (L2604): boot sentry, `OperaUI("face.png")`, runner thread runs `asyncio.run(opero.run())`, Qt loop via `ui.root.mainloop()` (shim in `ui/proxy.py` → `QApplication.exec`) |
| Application class | `OperaLive` (`main.py` L557): Gemini Live session, tool dispatch, visual bridge, monitors, greeting/news flows |
| UI framework | PyQt6 (`PyQt6>=6.6,<7`); main window `ui/window.py` `MainWindow` |
| Window contents | header (title/clock/date), left SYS MONITOR panel, centre HUD canvas, right panel (activity log, file upload, command input, microphone button), collapsible results/news panel — all CURRENT (`_build_*_panel`; panel docstring L1644) |
| 3D background | `WebGLBackground` QWebEngineView (`ui/widgets.py` L1516+) loading `site/web_background/index.html`; no-op transparent widget when PyQt6-WebEngine is absent |
| Thread model | Runner thread (async) + Qt main thread; cross-thread via Qt signals (`ui/proxy.py`, `_bg_sig`); `VoiceGate` and visual registries use locks |
| Shutdown | `_ShutdownHandler` (`main.py` L494): registered callbacks, SIGINT/SIGTERM, atexit |

**PLANNED:** no replacement of the desktop shell is scheduled; future phases extend it additively (`RULES.md` §1.7).

---

## 3. Python architecture — CURRENT

```text
main.py                 composition root + live session (OperaLive)
                        owns the Gemini Live session AND the effective dispatch
                        (TOOL_DECLARATIONS L325, _execute_tool L1338)
core/
  session.py            ORPHANED / NOT ON CURRENT RUNTIME PATH — Gemini Live
                        connect/reconnect; main.py runs its own inline session
  session_reconnect.py  ORPHANED (imported only by the orphaned session.py)
  tool_dispatch.py      ORPHANED (imported only by session.py); its
                        TOOL_DECLARATIONS/ToolDispatcher copy is dead — the live
                        declarations live in main.py L325
  gemini.py             PARTIAL — one-shot Gemini calls imported by
                        file-processing actions (docx_tools, file_processor,
                        pdf_tools, mobile_autopilot); not on the live-session path
  action_loader.py      actions/*.py discovery: module TOOL dict → validated
                        dispatch (wired: main.py L651, run at L1506)
  plugin_loader.py      plugins/*.py twin of action_loader (wired: main.py L659)
  validator.py          ORPHANED — imported only by tests/test_validator.py;
                        dispatch does not invoke it (parameter contract is the
                        Gemini function schema plus per-action checks)
  confirm.py            UI-issued confirmation the model cannot forge (wired)
  undo.py · learned_rules.py   wired (undo in dispatch L1408+; learned rules
                        applied as prompt injections, main.py L296)
  voice_state.py        VoiceGate: IDLE/LISTENING/THINKING/SPEAKING + generation counter
  stt.py                ORPHANED — STT is Gemini-native streaming + assemblyai_voice
  tts.py                ORPHANED — not imported by the application
  assemblyai_voice.py   wired (function-level import, main.py L2361/L2446)
  audio_pipeline.py     ORPHANED
  llm_client.py         ORPHANED (no importers)
  echo/viseme/wake_word/hotkey/audio_devices   wired
  perception/           PARTIAL — observation-only screen/windows/browser capture;
                        production use = one lazy get_active_window import
                        (actions/screen_processor.py L490), otherwise test-only
  visual/               world_model, intent, assets, routing, bridge, concepts (wired)
  avatar.py · avatar_mesh.py · gradient_orb.py      HUD centrepieces
  task_manager · recovery · health · boot_sentry   task_manager journals every
                        action run (action_loader); boot_sentry wired (main.py L78)
actions/                52 modules; 37 expose a module-level TOOL dict →
                        37 active discovered actions (measured Phase 6B)
plugins/                6 active plugins: calendar_scheduler, calorie_counter,
                        daily_briefing, pushup_counter, spotify_controller,
                        upload_video (plus _template)
memory/                 memory_manager.py (JSON categories), config_manager.py
ui/                     PyQt6 shell (window, widgets, overlays, theme, proxy);
                        ui.py is a legacy re-export shim, shadowed by the ui/ package
dashboard/              auxiliary FastAPI server · brahma_connect/ gateway
whatsapp_bridge/        Node.js WhatsApp bridge (separate runtime)
```

Tool contract (CURRENT, `core/action_loader.py`): each `actions/*.py` exposes

```python
TOOL = {
    "name": "open_app",                    # unique; validated ^[a-zA-Z_][a-zA-Z0-9_]{0,63}$
    "description": "...",                  # what Gemini reads to route
    "parameters": {"type": "OBJECT", ...}, # Gemini function-declaration schema
    "handler": open_app,                   # callable
}
```

Discovery runs once at startup; import/validation errors are logged and the file skipped — discovery never raises.

---

## 4. UI architecture — CURRENT

| Piece | File | Role |
|---|---|---|
| `OperaUI` | `ui/proxy.py` | Owns `QApplication`, `mainloop()` shim, thread-safe signal bridges (`set_visual_command`, call prompts) |
| `MainWindow` | `ui/window.py` | Layout, panels, HUD state fan-out (`_apply_state`), centrepiece cycling face→orb→core (L2387), background control signals |
| `HudCanvas` | `ui/widgets.py` | Paints the centrepiece; THINKING/PROCESSING accelerate motion; mouth driven by audio amplitude. Stacked **over** `WebGLBackground` (`QStackedLayout(StackAll)`, `ui/window.py`) — when a WebGL layer is present the HUD sets `webgl_backed=True`, which skips its opaque background fill so the 3D layer stays visible (Phase 7 fix: the opaque fill used to fully occlude the galaxy/visual entities on the canonical desktop) |
| `WebGLBackground` | `ui/widgets.py` L1516 | QWebEngineView host; `set_state`, `set_features`, `set_active_feature`, `set_automations`, `execute_visual` |
| Overlays | `ui/overlays.py` | Setup, `ConfirmBanner`, incoming-call banner, memory overlay, pairing QR, automation studio, mini mode |
| Theme | `ui/theme.py` | Palette `C`, theme/accent application, retheme |

**State fan-out (CURRENT):** `MainWindow._apply_state(state)` sets `hud.state` / `hud.speaking` and forwards the same string to the 3D background — one state string drives both the face and the galaxy palette.

---

## 5. Voice architecture — CURRENT

```text
microphone ─► audio pipeline ─► VoiceGate.accept_mic / accept_transcript ─► Gemini Live / AssemblyAI
                                      ▲                                          │
TTS output ─► begin_speaking() ───────┘                                          │
             end_speaking() / interrupt() ◄──────────────────────────────────────┘
```

- **`core/voice_state.py` — `VoiceGate`**: the single gate between OPERO's speakers and its mic. States `IDLE / LISTENING / THINKING / SPEAKING`. Speech beginning bumps a **generation counter**; anything captured under an older generation is stale and rejected — this kills the TTS self-hearing loop even when a transcript lands after the acoustic tail (`tests/test_voice_state.py`, `tests/test_echo.py`).
- Wake word (`core/wake_word.py`), hotkey (`core/hotkey.py`), mute → `MUTED` state (`ui/window.py` L2936).
- STT: Gemini-native streaming plus AssemblyAI path (`core/assemblyai_voice.py`, optional extra `voice`).
- TTS: Gemini Live native session audio — the receive loop drives playback and the viseme stream (`main.py` L585); `core/tts.py` (Edge/ElevenLabs engines) exists but is **ORPHANED — not imported by the application**; visemes/transcripts drive the avatar mouth (`core/viseme.py`).
- Barge-in interruption, microphone lifecycle, and generation handling are gate concerns — authoritative rules in `RULES.md` §6.

---

## 6. Action architecture — CURRENT

```text
Gemini function call (main.py L1850–1854)
      ↓
main.py _execute_tool (L1338)   ← the effective dispatcher (CURRENT)
      ↓
search guard / visual routing first (core/visual/routing.py, main.py L1350+)
      ↓
inline TOOL_DECLARATIONS (main.py L325)
   ── or ── action registry run (core/action_loader → actions/*.py,
              main.py L1500–1506; journals via core/task_manager)
   ── or ── plugin registry run (core/plugin_loader → plugins/*.py,
              main.py L1518–1521)
      ↓
safety / confirmation (core/confirm.py)  ← token issued by the UI, never the model
      ↓
execution (handler) ── undo stack (core/undo.py)
      ↓
structured FunctionResponse back to the session + activity log
```

- **`core/tool_dispatch.py` (ToolDispatcher) is ORPHANED / NOT ON CURRENT RUNTIME PATH** — imported only by the orphaned `core/session.py`; the live declarations and dispatch live in `main.py` (L325, L1338). Parameter validation is the Gemini function schema plus per-action checks — `core/validator.py` is imported only by its test. Learned rules (`core/learned_rules.py`) are applied as prompt injections (`main.py` L296), not as dispatch-time validation.

- **Confirmation design** (`core/confirm.py`): an action calls `request(...)`; the module hands the UI a CONFIRM/CANCEL banner and returns immediately; only the user's CONFIRM runs the stored callable. The model never sees a token, so it cannot forge one. Reversible operations should use `undo` instead of asking.
- Confirmation is actively used (CURRENT: `actions/computer_settings.py`, `actions/gmail.py`, `actions/instagram_messaging.py`, …).
- **The visual path never enters this pipeline**: for `SEARCH_GUARD_TOOLS`, visual routing happens *before* dispatch (`main.py` L1350+), and renderer commands have no side effects outside the 3D scene.

---

## 7. Visual architecture — CURRENT

### 7.1 Data flow

```text
User: "show me an apple"
      ↓
Visual Router (core/visual/routing.py)        lexical, deterministic, no model call
      │  matches explicit phrasing; SEARCH_GUARD_TOOLS never reaches web/image search
      ▼
VisualIntent (core/visual/intent.py)          mode=OBJECT action=SHOW concept_id="apple"
      ↓
Visual World Model (world_model.py)           creates/reuses entity "apple_01"
      ↓
Asset Registry (core/visual/assets.py)        find_for_concept("apple") → apple_default (AVAILABLE)
      ↓
Visual Bridge (core/visual/bridge.py)         one JSON command + base64 GLB payload
      ↓
Qt transport (proxy → window → widgets.execute_visual)
      │  JSON data only — `window.operoVisual({...})` — never AI-generated executable JS
      ▼
Three.js (site/web_background/index.html)     GLTFLoader → scene object; structured result dict
```

Integration points (CURRENT): `main.py` L560–566 builds `VisualBridge(_visual_router.world, _visual_router.registry, ui.set_visual_command)` and registers bundled assets; `main.py` L1350–1380 intercepts search-tool calls that name a visual concept and executes the bridge instead.

### 7.2 Visual Intent — CURRENT

`core/visual/intent.py`: a validated, deterministic, **renderer-independent** dataclass. It says WHAT; never contains executable content (no JavaScript, shaders, eval'able Python) and never references a renderer.

| Field | Values (CURRENT) |
|---|---|
| `mode` | `FACE_ONLY`, `OBJECT`, `OBJECT_INSPECTION`, `PROCESS`, `CAUSAL_CHAIN`, `INSTRUCTION` |
| `action` | `SHOW HIDE FOCUS ZOOM ROTATE MOVE HIGHLIGHT ISOLATE CUTAWAY RETURN_TO_FACE PAUSE RESUME REPLAY SLOW` |
| `camera` | `DEFAULT FOCUS ZOOM ORBIT CLOSEUP WIDE INSPECTION SIDE TOP_DOWN` |
| `animation` | `NONE APPEAR DISAPPEAR ROTATE MOVE HIGHLIGHT PULSE ASSEMBLE DISASSEMBLE EXPLODE IMPLODE` |
| targets | `concept_id`, `entity_id`, `target_part` + free-form `parameters`; `narration_sync` flag |

Validation rules (`tests/test_visual_intent.py`): object actions forbidden in `FACE_ONLY`; object actions require a target; entity/concept mismatch rejected; unknown fields rejected on `from_dict`; camera/animation enums coerced or rejected. `resolve_entity_id` never invents entities — it fails with `EntityResolutionError` when nothing live matches.

**Note:** the schema is wider than the execution surface — the bridge wires only 6 actions (§7.7).

### 7.3 Visual World Model — CURRENT

`core/visual/world_model.py`: deterministic, thread-safe, **session-scoped in-memory** store. No rendering, no Qt, no network.

| Aspect | Behavior |
|---|---|
| Concepts | Loaded from JSON files in `data/visual_world/concepts/` via `core/visual/concepts.py` (data-driven; adding a concept = adding a JSON file) |
| Entities | `Entity(id, concept, transform, parts, visible)`; created only from known concepts (`UnknownConceptError` otherwise) |
| Entity IDs | Deterministic zero-padded counters: `apple_01`, `apple_02`, … (`{concept}_{NN:02d}`); counters restored on `from_dict` |
| Transforms | `position / rotation / scale`, each exactly-3 float components; validated (`update_transform`) |
| Part visibility | Per-part booleans initialized from the concept's `parts` list; unknown part → `UnknownPartError` |
| Visibility | Whole-entity `visible` flag; `set_visible` used by bridge SHOW/HIDE |
| Relationships | `{source, target, kind}` rows; both endpoints must exist; `get_relationships(entity)` |
| Persistence | **Serialization exists** (`to_dict` / `from_dict`, version 1) but nothing persists it automatically — the model resets with the process (session-scoped). Cross-session persistence is PLANNED (`MEMORY.md` §4) |
| Concurrency | `threading.RLock`; concurrent creates produce unique IDs (`tests/test_visual_world_model.py`) |

### 7.4 Asset system — CURRENT

`core/visual/assets.py`: the registry that makes the real-object principle enforceable.

| Aspect | Behavior |
|---|---|
| Formats | `GLB`, `GLTF` (`AssetFormat`); the renderer loads GLB only |
| Asset record | `AssetRecord`: `asset_id`, `concept_id`, `path`, `format`, `status`, `source`, `license`, `is_default`, `available_parts`, verification fields |
| Status | `AVAILABLE / PENDING / UNAVAILABLE / INVALID` (`AssetStatus`) — structured, never silent |
| Verification | `VERIFIED / UNVERIFIED` tracked **separately from existence**: a file can exist while the asset is UNVERIFIED; an AVAILABLE asset must have a real file (`validate_asset`) |
| Concept association | `find_for_concept(name)`: registered assets beat the concept's inline `asset` reference; deterministic ordering `_selection_key` = verified → status rank → default → asset id |
| Provenance | `source` (e.g. "procedurally authored for OPERO (data/visual_world/generate_apple_glb.py)") and `license` (e.g. `CC0-1.0`) are first-class fields |
| Path safety | Paths must be project-relative; absolute paths and root escapes rejected |
| Bundled assets | `register_bundled_assets(registry)` — explicit, idempotent, skips missing files (CURRENT: `apple_default` → `data/visual_world/assets/apple.glb`) |
| Serialization | `to_dict` / `from_dict` with strict unknown-field rejection; round-trip tested |
| Missing assets | Structured failure `missing_asset` from the bridge — never a placeholder primitive |

Current vocabulary: exactly **one** concept JSON (`data/visual_world/concepts/apple.json`). Its inline `asset` block is a stale "pending" reference; the registered `apple_default` record is what actually serves SHOW (this override is deliberate and tested: `test_registered_asset_preferred_over_concept_reference`).

### 7.5 Visual Router — CURRENT

`core/visual/routing.py`: deterministic, lexical (no model call), testable.

- **Matching:** `_HEAD_RE` accepts "show/display/visualize/render (me|us) (a|an|the…) NOUN" with polite prefixes; leading/trailing "3D" modifiers are stripped; a "3D" marker anywhere or a strong verb (`visualize/visualise/render`) makes the request **must-route**: an unknown noun then raises `UnknownConceptError` instead of falling through to search.
- **Termination:** a routed request ends at `VisualRouteResult {intent, entity_id, asset_id, asset_status}` — no renderer attached at this layer.
- **Search guard:** `SEARCH_GUARD_TOOLS = {browser_control, web_search, youtube_video}`; `route_search_request(name, args, utterance)` is called from `main.py` before dispatch, so an explicit visual request **never becomes a search**.
- **Entity reuse:** routed entities are reused, not duplicated (`test_routed_entity_is_reused_not_duplicated`).
- **Singleton:** `get_visual_router()` (double-checked lock) shares one world/registry; `main.py` L563–566 attaches the bridge to the same instances.

### 7.6 Failure model — CURRENT

Every visual path returns structured results; nothing raises across the Qt boundary:

| Failure | Shape |
|---|---|
| Unknown concept (must-route) | `UnknownConceptError` → tool response `routed_to: "visual", status: "unknown_concept"` (`main.py`) |
| Unknown entity / no target | `{success:false, error:"unknown_entity", message}` |
| No available asset | `{success:false, error:"missing_asset", message}` (real-object rule: no primitive substitute) |
| Non-GLB asset | `{success:false, error:"invalid_asset"}` |
| Corrupt GLB | `{success:false, error:"asset_load_failed"}` (header magic/version/length checked in Python **and** loader in JS) |
| Transport/renderer down | `{success:false, error:"renderer_unavailable"}` — face/UI stays usable |
| Unsupported action | `{success:false, error:"unsupported_action"}` |

Success shape: `{success:true, action, entity_id?, asset_id?}`.

### 7.7 Visual Bridge — CURRENT

`core/visual/bridge.py`: resolves a `VisualIntent` against world model + registry, then dispatches **exactly one** JSON command per call.

- **Wired actions:** `SUPPORTED_ACTIONS = {SHOW, HIDE, ROTATE, ZOOM, FOCUS, RETURN_TO_FACE}`. Everything else in the intent schema returns `unsupported_action` (the schema is ahead of the wire — future phases close this gap, `PHASES.md` 8–10).
- **SHOW ordering:** asset resolved **first** — a failed SHOW leaves no orphan entity; then entity create/reuse, `set_visible(True)`, command `{action, entity, asset, transform, data_base64}`.
- **GLB transport:** asset bytes travel base64-encoded on SHOW only (one object, ~72 KB; bridge comment: switch to a file-URL fetch past ~500 KB — ponytail note with a known ceiling).
- **Renderer validation:** JS side (`window.operoVisual`) returns structured `visualFail(...)` dicts for invalid commands, unknown entities, and unsupported actions; `window.__operoVisualReady` signals readiness.
- **Verification status:** the bridge chain is covered by `tests/test_visual_bridge.py` (transport, ordering, failure shapes); **RUNTIME VERIFIED (Phase 7)** in the canonical desktop app: a dispatched SHOW returns `{"action":"show","ok":true,"entity":"apple_01"}` from `window.operoVisual`, the apple anchor lands in the camera frustum, and the apple + galaxy render on screen (verified after the HUD-occlusion fix, §16.8). Manual-vs-automated boundary: the in-app conversational path (typed utterance → Gemini tool call → search guard → route → bridge) was observed live once; repeated live attempts are nondeterministic because of Gemini tool-choice variance and Live-session drops, so the segment tests + CDP scene probes are the repeatable evidence.

### 7.8 Semantic representation — PLANNED (constraint is CURRENT)

**Semantic embedding space ≠ physical 3D geometry.** A vector that says "apple is near fruit" carries no information about the apple's stem position. OPERO must never collapse these layers.

OPERO may eventually maintain five coordinated representations of the same knowledge:

| # | Representation | Answers | Status |
|---|---|---|---|
| 1 | Semantic vector | what this *means*, similarity to other things | PLANNED (text memory scoring exists as a crude lexical stand-in: `search_memory` in `memory/memory_manager.py`) |
| 2 | Visual representation | what this *looks like* in OPERO's scene | CURRENT (entity state: transform, parts, visibility) |
| 3 | 3D geometry | the actual mesh/asset | CURRENT for one asset (GLB); acquisition pipelines PLANNED |
| 4 | Behavior representation | how this *acts/changes* over time | DEFERRED (no physics/animation semantics yet; animation styles are intent-level keywords only) |
| 5 | Relationship graph | how this *connects* to other things | PARTIAL (world-model `{source,target,kind}` rows CURRENT; a richer semantic graph PLANNED) |

How they interact (design intent): reasoning works in representation 1; the router/registry translate *meaning* → *entity* (1→2); the bridge binds *entity* → *geometry* (2→3); future phases add *behavior* (4) and keep *relationships* (5) queryable from both sides. Each transition must be explicit and testable — no implicit "the embedding is the shape".

### 7.9 Visual Director — PLANNED

The intent module's own docstring reserves this role: *"The future Visual Director decides HOW to execute an intent; the World Model owns WHAT currently exists."* The Director will:

- apply the `PRD.md` §5 visualization-intelligence criteria (spatial/structural/causal/… value) before emitting an intent — model judgment, not just lexical matching;
- sequence multi-step explanations (camera moves, narration sync, replays);
- enforce limits (budget for steps, interruption cost, performance);
- never bypass the asset registry or the action system's safety gates.

Nothing named "Visual Director" exists in the codebase today.

---

## 8. Perception architecture — PARTIAL

`core/perception/` — **observation only**:

> **Runtime status:** NOT on the live-session path. The only production importer is a single lazy `from core.perception import get_active_window` inside `actions/screen_processor.py` (L490); `main.py`'s screen/camera capture (`_capture_screenshot`, `_capture_camera`) uses PIL/mss directly. Everything else is exercised by `tests/test_perception.py` / `tests/test_screen_capture.py` only.

| Module | Capability |
|---|---|
| `screen.py` | `capture_screen()` one-shot PNG + `ScreenCapture` metadata (`to_dict` deliberately excludes image bytes) |
| `windows.py` | `get_active_window()`, `get_open_windows()` → `WindowInfo` |
| `context.py` | `get_screen_context()`, `probe_browser()` → `PerceptionContext` / `BrowserContext` (metadata-level) |
| `errors.py` | `PerceptionError`, `PerceptionUnavailableError` |

Standing constraints (module docstring, tested by `tests/test_perception.py`, `tests/test_screen_capture.py`): nothing polls, caches, or auto-forwards captures; captures happen only when explicitly called; browser/app control stays in the action engine behind its existing confirmation gates.

The older capture tool (`screen_process` inline tool in `main.py`'s `TOOL_DECLARATIONS`, L345) remains the Gemini-facing path — it sends the image **for that call only**.

---

## 9. Memory architecture — CURRENT (summary)

Full design: `MEMORY.md`. Verified now:

- `memory/memory_manager.py` — JSON store with categories, bounded trimming (`_trim_to_limit`), prompt formatting with priority/interleaving, lexical `search_memory`, `remember`/`forget`, session summaries (`save_session_summary`, `pop_last_session`), UI listing.
- `memory/config_manager.py` — configuration persistence.
- `memory/boot_sentry/` — boot-state snapshot/rollback for crash recovery (not user memory).
- Tests: `tests/test_memory_manager.py`, `tests/test_config_manager.py`.

No embedding index, no vector store, no visual memory file exists (PLANNED — `MEMORY.md` §4–5).

---

## 10. Three.js architecture — CURRENT

The **one and only** renderer: `site/web_background/index.html` (~1,243 lines), hosted in Qt's `QWebEngineView`. There is no second renderer and none may be added (`RULES.md` §1.2).

| Aspect | Implementation |
|---|---|
| Library | Offline **Three.js r128** (`three.min.js`) + post-processing add-ons in dependency order: `EffectComposer`, `RenderPass`, `ShaderPass`, `UnrealBloomPass`, `LuminosityHighPassShader`, `CopyShader`, `OrbitControls` — all vendored in `site/web_background/` |
| WebGL | `THREE.WebGLRenderer({antialias, powerPreference:"high-performance"})`; WebGL enabled via `QWebEngineSettings` |
| Scene | Backdrop: gradient sky sphere, distant stars, galaxy point cloud (audio-reactive uniforms), dust lanes, nebula, orbit rings, central "core" (inner/panel/wire/shell meshes), feature-node rings, automation chains |
| Camera | `THREE.PerspectiveCamera(52°)` + `OrbitControls`; state-driven dolly targets; `camBlendGoal` blends for focus/zoom; `return_to_face` resets the blend |
| Animation loop | `requestAnimationFrame` `animate()`: fixed `dt` clamp, state palette lerp, audio amplitude smoothing, feature pulse decay; **pauses when `document.hidden`** |
| Effects | `UnrealBloomPass` via `EffectComposer`; strength lerps with state + energy |
| Visual command bridge | `window.operoVisual(cmd)` (L1119): `show` (GLTFLoader from base64 → entity record), `hide`, `rotate` (speed), `focus`, `zoom`, `return_to_face`; structured `visualFail(...)` results; `window.__operoVisualReady = true` |
| State palette | `STATES` map: `IDLE ONLINE LISTENING THINKING SPEAKING EXECUTING WORKING SCANNING MUTED SLEEPING CINEMATIC ERROR` — each with hot/mid/dim/accent colors, spin, bloom, camera distance, warp, arcs |
| Adaptive quality | FPS sampled per second; two consecutive seconds < 26 fps drops a quality rung (`applyQuality`) |
| Other inputs | Python pushes HUD data via the same widget: `set_state`, `set_features`, `set_active_feature`, `set_automations`, `set_active_automation`, `set_system_stats`, audio amplitude |

**Do not propose a second renderer.** All future visual work extends this page and the Python bridge (`RULES.md` §1.2–1.3).

---

## 11. Avatar architecture — CURRENT

| Piece | File | Role |
|---|---|---|
| `HoloAvatar` | `core/avatar.py` (~784 lines) | Holographic head: state expression, gaze/saccades, blink, brow/lid control, mouth from amplitude + visemes, `glance()` API, surface/wire/realistic paint passes |
| Head mesh | `core/avatar_mesh.py` + `core/face_model.obj` | Human head geometry for the face render |
| Gradient orb | `core/gradient_orb.py` | Alternative HUD centrepiece |
| Reactor core | drawn by `HudCanvas`/window code | Third centrepiece; "turns with the state and moves with your voice" |
| Cycling | `ui/window.py` L2387+ | face → orb → core → face (menu labels L2370–2380) |

State expression (CURRENT): `THINKING/PROCESSING` → eyes look away slowly, brows lower, blinks slow; `SLEEPING/STANDBY/OFFLINE` → lids down, no blinks; `LISTENING` → brows lift, eyes on user; speaking glow follows audio amplitude; mute forces glow off.

**PLANNED:** face↔3D cinematic transitions (`PHASES.md` 7) — today the face (Qt) and the galaxy (WebGL) live in different layers.

---

## 12. Runtime boundary — CURRENT (normative)

```text
Python owns                                  JavaScript / Three.js owns
────────────────────────────                 ──────────────────────────────
reasoning & intent extraction                rendering (WebGL draw calls)
tool dispatch & safety gates                 scene graph & object lifecycle
visual routing & VisualIntent                camera animation & blending
world model (WHAT exists)                    GPU-side effects (bloom, shaders)
asset registry (provenance/truth)            frame loop & quality scaling
bridge command construction                  base64 GLB → mesh loading
orchestration & state fan-out                palette interpolation
```

Rules at the boundary:

1. **Transport is JSON data only.** Python emits `window.operoVisual({...})` with a serialized dict — never string-concatenated code (`ui/widgets.py` `execute_visual` docstring: "JSON data only — never executable JavaScript").
2. **Neither side executes arbitrary code generated by Gemini.** The model produces function calls (Python side) or nothing that reaches the renderer; the renderer only interprets its fixed command vocabulary.
3. **Failures stay structured.** JS returns result dicts; Python converts them to tool responses; nothing throws across the boundary.
4. **Truth lives in Python.** The scene may not claim an object exists unless the world model + asset registry said so first.

---

## 13. Safety architecture — CURRENT

| Control | Implementation |
|---|---|
| Confirmation the model cannot forge | `core/confirm.py` — token issued by the UI; only the user's CONFIRM executes the stored callable; nothing blocks the Qt thread |
| Undo over ask | `core/undo.py` — reversible operations prefer undo; confirm is reserved for genuinely irreversible acts |
| Input validation | `core/validator.py` + per-tool Zod-like schema validation in dispatch |
| Learned rules | `core/learned_rules.py` (bounded, user-controllable) |
| Perception isolation | `core/perception/` never auto-forwards captures; bytes excluded from serialized contexts |
| Visual isolation | Renderer commands have no side effects outside the 3D scene; the visual system never calls dispatch/execute paths (`RULES.md` §1.5) |
| Search guard | Explicit visual requests cannot reach web/image search (`SEARCH_GUARD_TOOLS`) |
| Crash/boot safety | `core/boot_sentry.py` snapshots + rollback; `core/recovery.py` |

**PLANNED:** risk-tiered policy for visual mutations is unnecessary (the scene is not infrastructure) — but any future capability that touches the *machine* from a visual context must route through the action system's gates, not around them.

---

## 14. Packaging architecture — CURRENT

| Piece | File |
|---|---|
| Project metadata | `pyproject.toml` (name `opero`, `requires-python >=3.11`, PyQt6/gemini/etc. deps; dev/voice/windows extras) |
| PyInstaller | `OPERO.spec`; hooks `hooks/rthook_opero_qt.py`; `core/installer.py` |
| Windows installer | `installer/opero.nsi` (NSIS); `packaging/build-windows.ps1`, `packaging/publish-release.ps1` |
| Setup script | `setup.py` |
| Runtime hardening | `core/patches.py` (Python >=3.11 startup guard via `core/python_guard.py`, CREATE_NO_WINDOW subprocess patch, code-page handling); Qt DLL search-path pinning (commit history) |

---

## 15. Testing architecture — CURRENT

| Piece | Detail |
|---|---|
| Runner | `pytest` (`testpaths = ["tests"]` in `pyproject.toml`) |
| Suite | 214 tests across 27 files (measured Phase 7); visual suite covers world model, intent, assets, routing, bridge (77 tests); plus perception, voice/echo, memory, confirm, dispatch loaders, recovery, Python guard |
| CI | `.github/workflows/ci.yml`: Python **3.11/3.12/3.13** matrix → `pip install -e ".[dev]"` → `python -m compileall` → `ruff check . --select F821` → `pytest tests -q` — F821 gate **GREEN (0 findings)** since Phase 6A |
| Lint scope | CI enforces **F821 (undefined names) only** — deliberate policy, currently passing. Full `ruff check` reports 1,844 pre-existing findings (measured after Phase 6A); `ruff format --check` reports 160 files would reformat. Neither is enforced by CI; the broader cleanup is deferred technical debt (`PHASES.md` 6, §16.5), not a passing gate |
| JS checks | No automated JS test harness; `node --check` passes for `whatsapp_bridge/bridge.js` and `_site_verify.cjs`; the Three.js page has an in-page `diagnostics` object |

---

## 16. Known contradictions & gaps — CURRENT (honesty list)

Recorded so no document pretends they don't exist:

1. **RESOLVED (Phase 6B) — landing-page contract:** repository evidence (deliberate commit `b6b791c` "publish public via Netlify" + subsequent feature commits to `public/`) shows `public/` is the intended Netlify deployment directory; `site/` is the retained original landing page and the desktop HUD's asset home. `tests/test_landing_page.py` now asserts the current contract (`publish = "public"`); the full suite is green (213/213).
2. **RESOLVED (Phase 6A) — Python version story:** `pyproject.toml`, CI, and `README.md` all state >=3.11; a startup guard (`core/python_guard.py`, invoked from `core/patches.py` before any project module) rejects older interpreters with a clear message (proven against a real Python 3.10.11 interpreter); the stale 3.10 `venv/` and mixed `__pycache__` bytecode were removed. The Python 3.10 crash class (observed in `FATAL_CRASH.log` as a deep `asyncio` `TaskGroup` traceback) is closed.
   **StrEnum decision (Phase 6B): KEEP the three shims** (`core/visual/assets.py`, `core/visual/intent.py`, `core/voice_state.py`). They subclass `str, Enum` and differ from stdlib `enum.StrEnum` in `str()`/format output (class-qualified vs value); all current usage is identity comparison (`.is`), `.value` reads, and dict keys — removal would change observable stringification for zero functional gain. Harmless compatibility debt, intentionally retained.
3. **Stale concept metadata:** `data/visual_world/concepts/apple.json` says "No real 3D asset is bundled yet" although `apple.glb` exists and is registered (the registry override is what runs, and is tested). Data-file refresh deferred; harmless because the registry wins.
4. **Schema ahead of execution:** intent modes/actions/camera/animation enums outnumber the 6 wired bridge actions and 6 JS-handled commands.
5. **Lint/format debt (deferred by policy):** 1,844 ruff findings and 160 unformatted files remain (measured after Phase 6A); CI deliberately gates F821 only. Full lint/format cleanup is separate technical debt (`PHASES.md` 6) — "ruff passes" means "the F821 gate passes", not a clean full run.
6. **Branch state:** local branch `abc` is ahead of `origin/main` (`c1206fa`) by the unpushed phase history — 10 commits measured during Phase 6B, plus this documentation commit; 0 behind. Push policy is "never push unless explicitly requested" (`RULES.md` §7 rule 10).
7. **Orphaned modules (retained deliberately):** `core/session.py`, `core/session_reconnect.py`, `core/tool_dispatch.py`, `core/stt.py`, `core/tts.py`, `core/audio_pipeline.py`, `core/llm_client.py`, `core/validator.py` are imported by nothing on the live path (session/tool_dispatch only import each other; validator is test-only). `core/perception/` is PARTIAL (one lazy import). `main.py` owns the live Gemini session and dispatch. Do NOT read the §3 tree entries for these as active — wiring/migration requires a separate architectural decision phase (PHASES.md).
8. **RESOLVED (Phase 7) — Apple GLB rendering: RUNTIME VERIFIED.** The chain (router → intent → world model → registry → bridge → `window.operoVisual` GLB load) was verified live in the canonical desktop app: dispatched SHOW returns `{"ok":true,"entity":"apple_01"}`, the anchor is in-frustum, and the apple + galaxy are visible on screen (screenshots under `%TEMP%\opencode\phase7*`). Root cause of the earlier black-desktop symptom: `HudCanvas.paintEvent` filled itself with the opaque theme colour (`C.BG`, `WA_OpaquePaintEvent`) on top of `WebGLBackground` in the `QStackedLayout(StackAll)` stack, so the live 3D layer never reached the screen (test harnesses used `QWidget.grab()` on the WebGL widget itself, bypassing the occlusion). Fixed by the `webgl_backed` flag (`ui/widgets.py`, `ui/window.py`). Remaining open finding: **voice turns append `User:` at `turn_complete` (`main.py`), after the model's tool call, so the search guard's `last_user_utterance` can be stale and a voice "show me an apple" may fall through to a real search** — typed and AssemblyAI paths append before send and are unaffected. This is a Gemini-Live voice-path ordering defect, recorded as open (a fix touches live voice handling and is deliberately out of the test-only commit scope).
9. **Wired-but-unreachable actions:** `ROTATE / ZOOM / FOCUS / HIDE / RETURN_TO_FACE` are wired end to end (intent → bridge → JS) but have **no conversational producer** — production utterances only ever route `SHOW` (`route_visual_request`), and no prompt surface emits the other commands. They were verified at the intent/bridge/JS layers, not from an utterance.
10. **Gemini Live instability (environmental):** Live sessions drop periodically with `APIError 1008 (GoAway, session duration)` and auto-reconnect (`main.py` reconnect loop); a typed turn sent during a drop is silently lost. Not a visual-pipeline defect, but it bounds what live end-to-end testing can prove in one session.
