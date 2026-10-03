# OPERO — Product Requirements Document

| | |
|---|---|
| Document | PRD.md (1 of 6 — see `ARCHITECTURE.md`, `RULES.md`, `PHASES.md`, `DESIGN.md`, `MEMORY.md`) |
| Status | Authoritative specification |
| Source of truth | Repository implementation first; see `RULES.md` → Documentation rule |
| Terminology | **CURRENT** = verified in code · **PLANNED** = specified, not implemented · **DEFERRED** = intentionally postponed |

---

## 1. Product identity

### 1.1 Name

**OPERO** — **O**pen **P**ersonal **E**xecution & **R**esponse **O**perator.

### 1.2 Product vision

An AI operating layer for the personal computer: local-first, voice-first, able to understand intent, act on the machine under explicit human control, perceive the desktop, and explain ideas visually when a visual representation carries real explanatory value.

### 1.3 Product mission

Give one person a single, trustworthy operator that:

1. hears and understands them (voice, typed input),
2. decides whether the right response is **an answer**, **an action**, or **a visual explanation**,
3. executes actions only through gated, attributable, reversible-where-possible paths,
4. renders explanations in 3D only when visualization is genuinely useful,
5. remembers what matters without inventing anything.

### 1.4 Core problem

Today's assistants are either chat bubbles (they answer but cannot act) or automation scripts (they act but cannot explain or cannot be trusted). Users context-switch between a conversation window, a browser, and manual desktop work. The explanation medium — showing the thing — is usually a 2D screenshot or nothing at all.

### 1.5 Target users

| Persona | Need |
|---|---|
| Technical operator (primary) | Hands-free control of their own machine; structured answers; safe automation |
| Learner / student | Visual and instructional explanations of physical and procedural concepts |
| Accessibility-driven user | Voice-first interaction with visible, predictable system state |

CURRENT: the product ships as a Windows-first desktop application (PyQt6; PyInstaller `OPERO.spec`; NSIS `installer/opero.nsi` — see `ARCHITECTURE.md` §14).

### 1.6 Primary use cases

1. **Voice-first desktop operation** — "open Outlook", "what's on my screen", "summarize this page" (CURRENT: 37 auto-discovered actions + 8 inline tools + 6 plugins; the live tool dispatch lives in `main.py` - `core/tool_dispatch.py` is orphaned).
2. **Desktop perception** — explicit screen/window capture and browser context on request (PARTIAL: capture runs through `actions/screen_processor.py`; `core/perception/` has one production import plus tests; captures are never auto-forwarded).
3. **Memory-backed conversation** — persistent preferences and notes recalled on demand (CURRENT: `memory/memory_manager.py`).
4. **Visual explanation of objects** — "show me an apple" produces a real 3D object in the existing Three.js scene (CURRENT for the routed, asset-backed path; §6).
5. **Structured visual reasoning** — inspection, process, causal, instructional scenes (PLANNED: schema exists in `core/visual/intent.py`; execution largely unwired; `PHASES.md` 9–12).
6. **ISL teaching with 3D hands** (PLANNED: `PHASES.md` 13; not implemented).

### 1.7 Non-goals

- Not a general web-search assistant that "shows things" by fetching images.
- Not a game engine, social avatar, or decorative character product.
- Not a cloud service; local-first preference is a product requirement (`MEMORY.md` §7).
- Not an autonomous agent that acts without safety gates (`RULES.md` §1 rules 5–6, §2).
- Not a second desktop OS: it layers on top of the existing one.
- Not a React application; the desktop UI is PyQt6 (`RULES.md` §1.1).

---

## 2. Product philosophy

OPERO is **not merely** any one of the following:

| Reduced to… | What would be missing |
|---|---|
| an AI chatbot | execution, perception, visual explanation |
| a voice assistant | persistent memory, desktop perception, 3D reasoning medium |
| a desktop automation tool | conversational understanding, teaching ability |
| an avatar | real actions, real perception, factual grounding |
| a 3D visualization demo | safety-gated execution, voice, memory, real tool integration |

OPERO **combines six capabilities in one loop**:

```text
reasoning  — Gemini intent extraction and orchestration   (core/gemini.py, core/session.py)
execution  — gated action dispatch                        (core/tool_dispatch.py, actions/, core/confirm.py)
perception — explicit screen/window/browser observation   (core/perception/)
memory     — persistent, bounded, user-controlled recall  (memory/)
voice      — full-duplex speech with echo-safe gating     (core/voice_state.py, core/session.py, core/tts.py)
visual     — structured visual intent → 3D scene          (core/visual/, site/web_background/)
```

The product is defined by the **seams** between these systems: the visual system never executes actions, the action system never fabricates visuals, and neither may bypass the other's controls (`RULES.md` §1.4–1.5).

---

## 3. Core user experience

The intended conversation loop:

```text
User speaks / types
      ↓
OPERO understands (Gemini Live turn; typed turns join the same session log)
      ↓
OPERO classifies the response kind:
      ├── answer     → speak / show text
      ├── action     → dispatcher → safety/confirmation → execution → report
      └── visualize  → Visual Router → Visual Intent → World Model → Asset Registry
                       → Visual Bridge → Three.js scene
      ↓
OPERO responds (voice + HUD state + log)
      ↓
OPERO executes ONLY when authorized (confirm banner / policy)
      ↓
OPERO visualizes ONLY when it adds explanatory value (§5)
      ↓
Return to face/default state when the visualization ends
```

**CURRENT evidence for each step:**

| Step | Verified in |
|---|---|
| Voice/typed turn enters one session log | `main.py` (typed turns append `User:` entries; `last_user_utterance` reads them) |
| Tool dispatch + safety | `core/tool_dispatch.py`, `core/confirm.py` |
| Visual routing terminates explicit visual requests | `core/visual/routing.py`, `main.py` (~L1347–1380) |
| Bridge → Three.js | `core/visual/bridge.py`, `ui/widgets.py` `execute_visual`, `site/web_background/index.html` `window.operoVisual` |
| HUD state feedback | `ui/window.py` `_apply_state` → HUD + 3D background states |
| Return to face | `IntentAction.RETURN_TO_FACE` (bridge + renderer camera reset) |

**PLANNED:** the cinematic face→object→face transition sequence itself (`DESIGN.md` §5) is not implemented; today `return_to_face` restores the background camera while the Qt HUD face remains independently visible.

---

## 4. Face-first principle

**Design rule (authoritative):**

1. **Default state = the holographic OPERO face/core.** The HUD centre always shows one of three user-cyclable centrepieces: realistic face → gradient orb → reactor core (CURRENT: `ui/window.py` centrepiece cycling; `core/avatar.py`; `core/gradient_orb.py`).
2. **Normal conversation keeps the face present.** Visualization is never the default response mode.
3. **Visualization only when it has explanatory value.** The face/HUD transitions into a visualization for the duration of the explanation.
4. **After the explanation, control returns.** The scene returns to the default/background state (`RETURN_TO_FACE` exists in bridge and renderer; the full animated reconstruction is PLANNED — `DESIGN.md` §5).

The Three.js galaxy background and the Qt face HUD are **both CURRENT and coexist**: the galaxy is the window background; the face/orb/core is the HUD centrepiece. Unifying them into one cinematic stage is PLANNED (`PHASES.md` 7).

---

## 5. Visualization intelligence

**OPERO must not visualize every noun.**

A visualization is authorized only when at least one criterion holds:

| # | Criterion | Meaning | Example |
|---|---|---|---|
| 1 | Spatial value | shape/position matters to understanding | an apple's form |
| 2 | Structural value | internal parts carry the point | engine pistons |
| 3 | Causal value | one thing makes another happen | ignition → power |
| 4 | Temporal value | change over time is the subject | a heartbeat cycle |
| 5 | Relational value | connections between things matter | organ → body system |
| 6 | Explanatory value | the scene explains better than words alone | causal chains |
| 7 | Explicit user request | "show me X", "visualize X", "X in 3D" | "show me an apple" |
| 8 | Interruption cost | the visual costs less than the confusion it prevents | a quick object vs. paragraphs |
| 9 | Cognitive load | text/voice would overload working memory | anatomy, machinery |

If none hold, OPERO answers in voice/text and stays in face state.

**CURRENT mechanism:** the deterministic lexical router (`core/visual/routing.py`) implements criterion 7 exactly — explicit visual phrasings ("show/display/visualize/render …", any "3D" marker) are routed to the visual layer and **never fall through to web/image search** (`SEARCH_GUARD_TOOLS` guard in `main.py`). Criteria 1–6 and 8–9 require model judgment and are **PLANNED** (they belong to the future Visual Director; `ARCHITECTURE.md` §7.9).

---

## 6. Real-object principle

Physical concepts must be represented by **recognisably real-world objects**, never arbitrary stand-ins.

> "show me an apple" must yield a recognisable apple — correct proportions, meaningful material, usable camera framing — **not** a cube or a generic sphere.

Consequences:

- Assets are GLB/GLTF models with recorded **provenance and license** (`core/visual/assets.py`).
- The bridge **fails closed**: if no real asset is AVAILABLE, the user receives a structured "could not show it" outcome instead of a substituted primitive (`missing_asset` path in `core/visual/bridge.py`; tested in `tests/test_visual_bridge.py`).
- CURRENT state: exactly one bundled asset exists — `data/visual_world/assets/apple.glb`, registered as `apple_default` (source: "procedurally authored for OPERO"; license CC0-1.0). Other concepts do not exist yet; unknown concepts are rejected cleanly (`UnknownConceptError`).

**PLANNED:** the concept/asset library beyond the apple (`PHASES.md` 9–11) and the image→concept→3D acquisition path (`PRD.md` §9).

---

## 7. Visual intelligence examples

Status of each example against the repository:

| Example | What "done" looks like | Status |
|---|---|---|
| **apple** | Recognisable GLB apple; show/hide/rotate/zoom/focus; orbit camera | **CURRENT** (`apple.glb`; router; bridge; `window.operoVisual`) |
| **engine** | Real engine model; cutaway; moving piston; part isolation | PLANNED (`PHASES.md` 9; CUTAWAY/ISOLATE validated in the intent schema, not wired in bridge/renderer) |
| **human heart** | Anatomy-correct model; chambers; beat cycle | PLANNED (`PHASES.md` 11) |
| **lungs** | Breathing cycle; diaphragm motion | PLANNED (`PHASES.md` 11) |
| **machine** | Assembly / exploded view | PLANNED (ASSEMBLE/DISASSEMBLE styles exist in the schema only) |
| **process** | Ordered stages with flow | PLANNED (`IntentMode.PROCESS` exists; no director executes it) |
| **causal chain** | Nodes + directed propagation | PLANNED (`IntentMode.CAUSAL_CHAIN` in schema only) |
| **timeline** | Time-ordered sequence visualization | PLANNED |
| **data** | Charts / spatial data scenes | DEFERRED (no spec; would extend, not replace, the renderer) |
| **ISL teaching** | 3D hands, labels, synchronized narration, replay/slow/camera/isolate/practice | PLANNED (`PHASES.md` 13; §8) |
| **cinematic explanation** | Directed camera, staged reveal, story pacing | PLANNED (`PHASES.md` 16; a `CINEMATIC` palette state exists in the renderer but nothing drives it) |

---

## 8. ISL vision

Intended teaching experience (**all PLANNED**):

```text
"Teach me sign language"
      ↓
OPERO introduces the lesson (voice + text)
      ↓
3D hands demonstrate the sign
      ↓
LEFT HAND / RIGHT HAND labels visible
      ↓
narration synchronized with animation
      ↓
replay · slow motion · change camera · isolate fingers
      ↓
practice mode
```

**Truthfulness requirements (authoritative — `RULES.md` §4, §5):**

1. ISL factual content must come from **authoritative sources such as the Indian Sign Language Research and Training Centre (ISLRTC)** — or other cited, verifiable references.
2. **Gemini must NOT invent ISL gestures.** Model output may structure, sequence, and narrate; it may never be the source of a sign's form.
3. Every demonstrated sign must carry provenance (source, citation, verification status) — the same discipline the Asset Registry already applies (`VerificationStatus` in `core/visual/assets.py`).
4. If no verified sign data is available for a request, OPERO says so and does not demonstrate.

No ISL data, hand rigs, or sign assets exist in the repository today.

---

## 9. Long-term vision

### 9.1 Current vs future

| Capability | Status |
|---|---|
| Session-scoped world model with deterministic entity IDs | **CURRENT** (`core/visual/world_model.py`) |
| Structured, validated, renderer-independent visual intent | **CURRENT** (`core/visual/intent.py`) |
| Asset registry with provenance, verification, licensing | **CURRENT** (`core/visual/assets.py`) |
| Deterministic lexical visual routing + search guard | **CURRENT** (`core/visual/routing.py`) |
| Bridge to the existing Three.js renderer (6 actions) | **CURRENT** (`core/visual/bridge.py`, `site/web_background/index.html`) |
| GLB loading in the live scene | **CURRENT** (base64 → GLTF loader in the background page) |
| Desktop/window/browser perception (explicit, observation-only) | **CURRENT** (`core/perception/`) |
| Computer world model: TTL windows/monitors/cursor with known/stale/unknown/unavailable statuses | **CURRENT** (`core/world_model.py`, unit-tested) |
| Spatial targeting (anchors, window picking, verified title-targeted window ops) | **CURRENT** (`actions/computer_control.py`; window ops + landing VERIFIED live, click-target accuracy manual) |
| Continuous, interruptible cursor motion (patterns, modify, stop) | **CURRENT** (`core/continuous.py`; live circle/modify/stop VERIFIED; UI-interrupt click session-level) |
| Semantic screen targeting (`screen_find`/`screen_click`) | **UNAVAILABLE in this build** (no vision backend; returns honest `UNAVAILABLE`, never a fake NOT_FOUND) |
| Memory with bounded categories and search | **CURRENT** (`memory/memory_manager.py`) |
| Semantic object understanding beyond a JSON concept vocabulary | PLANNED |
| image → concept → 3D asset pipeline | PLANNED (`PHASES.md` 14) |
| text → concept → 3D asset generation | PLANNED (blocked on registry provenance plumbing for generated assets) |
| Semantic relationship graph beyond `{source, target, kind}` links | PLANNED |
| Object behavior simulation (physics, materials) | DEFERRED |
| Body systems / physiology scenes | PLANNED (`PHASES.md` 11) |
| Process simulation (PROCESS / CAUSAL_CHAIN executed) | PLANNED (`PHASES.md` 10) |
| Cinematic, directed explanations | PLANNED (`PHASES.md` 16) |
| Visual memory across sessions | PLANNED (`MEMORY.md` §4, §5) |
| Personalized teaching history | PLANNED (`PHASES.md` 12, `MEMORY.md` §3) |
| Multimodal understanding (image understanding → visual response loop) | PLANNED |

### 9.2 Representation long-term

OPERO may eventually maintain multiple coordinated representations of the same knowledge — semantic vector, visual representation, 3D geometry, behavior, relationship graph — and must keep their distinction explicit (`ARCHITECTURE.md` §7.8). **Semantic embedding space ≠ physical 3D geometry** is a standing architectural constraint, not a future option.

---

## 10. Related documents

| Question | Document |
|---|---|
| How is it built? | `ARCHITECTURE.md` |
| What may never be done? | `RULES.md` |
| What gets built in what order? | `PHASES.md` |
| What does it look and feel like? | `DESIGN.md` |
| What does it remember? | `MEMORY.md` |
