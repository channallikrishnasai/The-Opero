# OPERO — Design Specification

| | |
|---|---|
| Document | DESIGN.md (5 of 6) |
| Status | Design authority for interaction & visual language |
| Rule | CURRENT = what the code renders today; PLANNED = specified, not built (`RULES.md` §8) |

---

## 1. Design principles

| Principle | Meaning in OPERO |
|---|---|
| **Face-first** | The OPERO face/core is home. Visualization is a visitor that leaves (`PRD.md` §4) |
| **Minimal UI** | Panels exist to inform, not to decorate; nothing on screen without a job |
| **Cinematic** | Motion has staging and intent — transitions read as deliberate, never as spinner replacements |
| **Futuristic** | Holographic, deep-space visual language: dark field, luminous accents, restrained bloom |
| **Intelligent** | The interface reflects internal state honestly (listening vs thinking vs speaking vs executing) |
| **Spatial** | Explanations use depth and position when that carries meaning — not parallax for its own sake |
| **Informative** | Every color, pulse, and label maps to real system state or real data |
| **Non-gimmicky** | If removing an effect loses no information, it is a candidate for removal (perf + taste) |
| **Accessible** | Motion and color are never the only channel (§8) |

---

## 2. Default UI — CURRENT (documented as-is, not redesigned)

Verified layout of `MainWindow` (`ui/window.py`):

```text
┌──────────────────────────────────────────────────────────────────────┐
│ HEADER  ◉ OPERO   title · subtitle · clock · date                   │
├──────────────┬───────────────────────────────────┬───────────────────┤
│ SYS MONITOR  │                                   │ ACTIVITY LOG      │
│ CPU/RAM/GPU  │        HUD CENTREPIECE            │ (LogWidget)       │
│ uptime       │   face │ orb │ core (cycled)      ├───────────────────┤
│ proc count   │   (HudCanvas over WebGL           │ FILE UPLOAD       │
│ OS / status  │    galaxy background)             │ drop-or-click     │
│ feature      │                                   ├───────────────────┤
│ indicators   │                                   │ COMMAND INPUT     │
│              │                                   ├───────────────────┤
│              │                                   │ 🎙 MICROPHONE     │
├──────────────┴───────────────────────────────────┴───────────────────┤
│ COLLAPSIBLE PANEL  search results · news · briefings (L1644)         │
└──────────────────────────────────────────────────────────────────────┘
+ full-window 3D galaxy background (Three.js) behind everything
+ overlays: setup, confirm banner, call banner, pairing, memory, mini-mode
```

| Element | Current behavior |
|---|---|
| System monitor | Live CPU/RAM/storage/uptime/proc labels + metric bars (`_build_left_panel`) |
| OPERO face/core | `HudCanvas` centrepiece: realistic face → gradient orb → reactor core, user-cycled (L2387); mouth reacts to voice |
| Activity log | `LogWidget`: tool calls, results, system lines (visual routes log a `🧭 visual route:` line) |
| Command input | Typed turns join the session log → same pipeline as voice |
| Microphone | Mute toggle → `MUTED` state (`_apply_state`) |
| File upload | Drop/click zone with hint label |
| Status | Header status + status card (ONLINE, CPU/RAM/storage sparkline, active model) |
| News/system panel | Collapsible bottom panel; news pre-fetched in the greeting flow (`main.py`) |
| Galaxy visualization | Full-window Three.js background; state palette; feature nodes; automation chains; audio reactivity |

**Do not redesign this layout in the specification phase.** Changes belong to future phases with explicit scope.

---

## 3. Face states

### 3.1 Implemented states — CURRENT

| State | Set by | Face/HUD behavior |
|---|---|---|
| `LISTENING` | `main.py` session loop | Eyes on user, brows raised, attentive |
| `THINKING` | tool dispatch / reasoning | Eyes glance away slowly, brows lower, slower blinks |
| `PROCESSING` | widgets treat as THINKING-class | accelerated motion, same palette as THINKING (`ui/widgets.py`) |
| `SPEAKING` | TTS boundaries | Mouth driven by amplitude/visemes, glow up |
| `SLEEPING` (avatar also: `STANDBY`, `OFFLINE`) | wake-word idle | Lids down, no blinks, dim palette |
| `MUTED` | mic toggle | Glow forced off, red-mute accent |

The same string fans out to the galaxy palette (`STATES` in `site/web_background/index.html`), which additionally defines `IDLE`, `ONLINE`, `EXECUTING`, `WORKING`, `SCANNING`, `CINEMATIC`, `ERROR` for background rendering.

### 3.2 Requested-but-not-implemented states — PLANNED

| State | Intended meaning | Gap |
|---|---|---|
| `VISUALIZING` | face yielded to a 3D scene | no transition system yet (`PHASES.md` 7) |
| `SUCCESS` | verified positive completion signal | success is reported via text/log today, not a face state |
| face-level `ERROR` | renderer has `ERROR`; the Qt face has no distinct error expression | face-side error expression PLANNED |

---

## 4. Visual states

### 4.1 Implemented modes — CURRENT (schema)

Defined and validated in `core/visual/intent.py`; execution status varies:

| Mode | Meaning | Executable today? |
|---|---|---|
| `FACE_ONLY` | object actions forbidden; return/home semantics | partially (`RETURN_TO_FACE` wired) |
| `OBJECT` | show/manipulate one object | **yes** (SHOW/HIDE/ROTATE/ZOOM/FOCUS) |
| `OBJECT_INSPECTION` | look inside an object | no — schema only (`PHASES.md` 9) |
| `PROCESS` | ordered process scene | no — schema only (`PHASES.md` 10) |
| `CAUSAL_CHAIN` | cause → effect scene | no — schema only (`PHASES.md` 10) |
| `INSTRUCTION` | lesson/teaching scene | no — schema only (`PHASES.md` 12) |

### 4.2 Future modes — PLANNED (kept separate on purpose)

| Mode (proposed) | Purpose | Phase |
|---|---|---|
| `TIMELINE` | time-ordered narrative | 16 |
| `DATA_SCENE` | charts/spatial data | DEFERRED (no spec) |
| cinematic sequence | directed multi-stage explanation | 16 |

New modes are proposed through `PHASES.md`, never announced in code docs first (`RULES.md` §8).

---

## 5. Transition design — PLANNED (spec; only `RETURN_TO_FACE` exists today)

### 5.1 Face → visualization

```text
face (present, speaking the setup)
  → holographic energy gather (particles/light converge on centrepiece)
  → mesh/particle transformation (face dissolves; energy becomes the scene seed)
  → camera movement (dolly/orbit from face position to object framing)
  → object assembly (asset materializes — ASSEMBLE animation style)
  → explanation begins (director takes over)
```

### 5.2 Visualization → face

```text
explanation ends (or user says "go back to my face")
  → object dissolve/disassemble (DISASSEMBLE style)
  → particles retract toward the centrepiece
  → camera returns (blend to default framing; `return_to_face` already resets the blend)
  → face reconstructed (energy → features; state returns to LISTENING/IDLE)
  → verification: face usable immediately — transition failure falls back to face, never a blank stage
```

Constraints (binding on implementation):

1. **Interruptible at every stage** — user voice/hotkey abort lands on the face, not between states.
2. **No double presence** — during `VISUALIZING`, the Qt centrepiece hides or is subsumed; never two OPEROs.
3. **Time-boxed** — transitions have fixed budgets (no 10-second drama before an answer).
4. **Reduced-motion path** — instant cut to scene/face when reduced motion is on (§7).

Current reality: `RETURN_TO_FACE` only resets the background camera blend (`site/web_background/index.html`); the Qt face stays visible independently. Everything else in §5 is **PLANNED** (`PHASES.md` 7).

---

## 6. Semantic colors

### 6.1 Canonical mapping (design authority)

| Color | Meaning | Never used for |
|---|---|---|
| **Cyan / blue** `#00e5ff`-family | neutral · info · technology · data · listening | danger |
| **Green** `#37ff9f`-family | positive · healthy · success · safe | warnings |
| **Gold / yellow** `#ffc46b`-family | selected · important · user attention | background wash |
| **Orange** `#ffa63d`-family | heat · energy · combustion · thinking/processing | success |
| **Red** `#ff3b30`-family | danger · failure · critical · muted-attention | decoration |
| **Purple** `#a06cff`-family | abstract · AI · creative · executing | warnings |
| **White / silver** `#eafcff`-family | neutral physical · inspection · speaking | error |

### 6.2 Implemented palette — CURRENT (`STATES`, `site/web_background/index.html`)

| State | Accent family | Alignment with §6.1 |
|---|---|---|
| `IDLE` / `ONLINE` | pale blue | ✓ neutral |
| `LISTENING` | cyan `0x00e5ff` | ✓ info/listening |
| `THINKING` | amber `0xffa63d` | ✓ energy/processing |
| `SPEAKING` | white-blue `0x7fe6ff` | ✓ neutral-physical |
| `EXECUTING` / `WORKING` | purple `0xa06cff` | ✓ AI/action |
| `SCANNING` | green `0x37ff9f` | ✓ active-safe (perception in progress) |
| `MUTED` | red-pink `0xff4d6d` | intentional "attention" use of red family |
| `SLEEPING` | deep blue | ✓ low-energy neutral |
| `CINEMATIC` | pink/gold | ✓ staged/selected |
| `ERROR` | red `0xff3b30` | ✓ critical |

### 6.3 Binding color rules

1. **Color never carries meaning alone** — always pair with text, icon, shape, or motion (e.g. ERROR also changes arcs/labels; the confirm banner has words).
2. Palette changes flow through the shared `STATES` table — no ad-hoc hex values scattered in features.
3. Face/HUD and galaxy palette must not contradict each other: one state string, one meaning (`MainWindow._apply_state`).
4. Accessibility contrast targets are part of §7, not an afterthought.

---

## 7. Interaction vocabulary

### 7.1 CURRENT (reachable today)

| User says / types | What happens | Evidence |
|---|---|---|
| "show me an apple" | routes → intent → entity → asset → scene (SHOW) | `routing.py`, `tests/test_visual_routing.py` |
| "display/show …", "visualize X", "render X", "… in 3D" | same routing; unknown noun → honest rejection, never a search | `_HEAD_RE`, must-route logic |
| anything visual to `web_search` / `youtube_video` / `browser_control` | intercepted pre-dispatch by the search guard | `main.py` L1347+ |
| typed commands generally | join the session log → normal pipeline | `main.py` (typed turns) |

### 7.2 PLANNED (bridge/schema exists or is reserved; no voice/model path yet)

| Command | Intended behavior | Blocked by |
|---|---|---|
| "rotate it" / "zoom in" / "focus on the stem" | ROTATE/ZOOM/FOCUS on the live entity | routing only emits SHOW; needs director/tool wiring (`PHASES.md` 8) |
| "show me inside" / "hide everything except …" | CUTAWAY/ISOLATE | `PHASES.md` 9 |
| "slow it down" / "replay" / "pause" | SLOW/REPLAY/PAUSE | `PHASES.md` 8, 10 |
| "show me why" / "what happens if this stops?" | CAUSAL_CHAIN scene | `PHASES.md` 10 |
| "go back to my face" | RETURN_TO_FACE from voice | command exists in bridge+renderer; voice/model path PLANNED (`PHASES.md` 7–8) |
| "teach me sign language" | ISL lesson flow | `PHASES.md` 13 |

Rule: a vocabulary entry may appear here only when either CURRENT evidence exists or a phase owns it — no aspirational commands without a phase (`RULES.md` §8).

---

## 8. Accessibility — PLANNED checklist (not yet implemented)

| Requirement | Specification |
|---|---|
| Reduced motion | Settings flag suppresses particle/transition/assembly animation; scenes appear via instant cut; information preserved |
| Keyboard support | Full path: navigate panels, trigger commands, orbit/zoom scene objects, confirm/cancel banners without a mouse |
| Contrast | Text/background pairs meet WCAG AA in HUD, panels, labels; state labels readable over galaxy |
| Readable labels | Scene labels (LEFT HAND, part names) sized for distance reading; never texture-only text |
| Non-animation alternatives | Every animated explanation has a static, labeled equivalent (diagram view or final-frame + captions) |
| Color-independent meaning | Every color signal doubled by text/shape (§6.3 rule 1) |
| Audio independence | All voice interactions have typed equivalents; captions for narration |

Exit proof lives in `PHASES.md` 18.

---

## 9. Performance

### 9.1 CURRENT (implemented in the renderer)

| Mechanism | Behavior |
|---|---|
| Adaptive quality | FPS sampled each second; two consecutive seconds < 26 fps drops a quality rung (`applyQuality`) |
| Visibility pause | `document.hidden` → frame loop returns immediately (minimized window doesn't burn GPU) |
| Delta clamp | `dt = min(0.05, …)` prevents spiral-of-death after stalls |
| Smoothing lerps | Palette/bloom/audio values lerp instead of stepping (perceived smoothness at low fps) |
| Inline asset size | base64 GLB on SHOW only; one object at a time (~72 KB today) |

### 9.2 PLANNED ceilings (owned by `PHASES.md` 17)

| Budget | Target |
|---|---|
| LOD | >N units or >M triangles → simplified meshes / instancing |
| Pooling | feature nodes, labels, particle sprites reused, not recreated |
| Frustum culling | rely on Three.js frustum + explicit audit for labels/sprites |
| Lazy loading | assets fetched on first SHOW; cache with eviction ceiling (file-URL switch past ~500 KB, pre-flagged in bridge) |
| Animation throttling | background/idle animations drop frame share before foreground visuals do |
| Resolution scaling | devicePixelRatio rung below the quality floor |
| Cleanup | show/hide cycles must not grow GPU object counts (leak test in Phase 17) |

Rule: performance work never removes information — it removes waste (non-gimmicky principle, §1).
