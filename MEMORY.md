# OPERO — Memory Architecture

| | |
|---|---|
| Document | MEMORY.md (6 of 6) |
| Status | Design authority for everything OPERO remembers |
| Rule | This phase **designs** memory; it does not implement new memory systems (`PHASES.md` 15 owns visual persistence) |

---

## 1. What memory is for

OPERO remembers so that conversations, explanations, and actions build on each other — **without inventing a past**. Every memory answers three questions: *where did this come from*, *who controls it*, *when does it stop being true*.

Implementation today lives in one place: `memory/memory_manager.py` (file `memory/long_term.json`, local, thread-locked) plus the session log in `main.py`. Everything else below is design.

---

## 2. Memory taxonomy — CURRENT vs PLANNED

| # | Memory kind | Status | Home today / planned home |
|---|---|---|---|
| 1 | Short-term conversation memory | **CURRENT** (session-scoped) | `_session_log` in `main.py` |
| 2 | Session visual memory | **PARTIAL** | world model in RAM (`core/visual/world_model.py`); persistence PLANNED (Phase 15) |
| 3 | Long-term user memory | **CURRENT** | `memory/long_term.json` via `memory_manager.py` |
| 4 | Entity memory | **PARTIAL** | deterministic IDs in-session; cross-session PLANNED |
| 5 | Visual memory (scenes/objects seen) | **PLANNED** | `PHASES.md` 15; schema below (§5) |
| 6 | Action history | **PARTIAL** | in-session activity log (`LogWidget`); durable history PLANNED |
| 7 | Preferences | **PARTIAL** | theme/accent/config via `memory/config_manager.py`; declared prefs in long-term `preferences` category; inferred preference learning PLANNED |
| 8 | Relationship memory | **CURRENT** (as data) | `relationships` category of long-term memory |
| 9 | Provenance | **CURRENT for assets** / **PLANNED for memory entries** | Asset Registry (`source`, `license`, verification); memory entries carry no source metadata yet |
| 10 | Safety-sensitive information | **POLICY NOW / enforcement PLANNED** | §9 — never stored today by policy; formal redaction/audit is Phase 19 work |

---

## 3. Short-term conversation memory — CURRENT

- **Session log**: ordered entries (`"User: …"`, assistant/tool lines) held in memory for the running session; used for context, visual routing (`last_user_utterance`), and greeting continuity.
- **Budgets** (`memory_manager.py`): only a *core slice* rides in every system prompt — `PROMPT_CORE_CHARS = 900` plus an index `PROMPT_INDEX_CHARS = 420`; the full store stays on disk and is fetched on demand (`recall_memory`, `search_memory`). Identity always rides in the prompt; categories compete for the remainder and are interleaved so one fat category can't starve the rest.
- **Session summaries**: `save_session_summary()` / `pop_last_session()` persist a wrap-up that the next session can ingest.
- **Boundary**: session log is not user-editable history; it ends with the session. No fabrication: entries are appended, never synthesized retroactively.

---

## 4. Long-term user memory — CURRENT

Storage: `memory/long_term.json` (local-first, path falls back to the frozen exe dir when packaged). Write path: the `save_memory` tool (`main.py` L411+): `{category, key, value}` with **English values regardless of conversation language**, `MAX_VALUE_LENGTH = 380`.

| Category | Contents (per tool schema) |
|---|---|
| `identity` | name, age, birthday, city, job, language, nationality |
| `preferences` | favorite food/color/music/film/game/sport, hobbies |
| `projects` | active projects, goals, things being built |
| `relationships` | friends, family, partner, colleagues |
| `wishes` | future plans, things to buy, travel dreams |
| `notes` | habits, schedule, anything else worth remembering |

Hard limits: `MEMORY_MAX_CHARS = 200_000` is a **runaway guard**, not a feature limit — `_trim_to_limit()` exists for bug protection, and the design comment explicitly records that storage and prompt budget are separate concerns (a past bug: whole-memory dumps silently evicted personal facts).

Controls (CURRENT): `MemoryOverlay` UI lists entries (`all_entries_for_ui`), `remember()`/`forget()`, lexical `search_memory`. Tool guidance excludes weather/reminders/one-shot commands from long-term memory.

**PLANNED:** per-entry provenance + timestamps (§9), export/clear-all parity, explicit consent for sensitive categories.

---

## 5. Session visual memory & visual memory design

### 5.1 Session visual memory — CURRENT (in-RAM) / PLANNED (persisted)

The **world model** is the session's visual memory: every object the user has seen exists as an entity with a deterministic ID, transform, part visibility, and relationships. `to_dict()`/`from_dict()` already round-trip the whole thing — but nothing calls them at shutdown today, so the scene forgets on exit.

**PLANNED persistence** (`PHASES.md` 15): snapshot at session end, restore at start, with *re-validation* — a restored entity whose asset vanished must come back as an honest structured state, never as a ghost object.

### 5.2 Visual memory record — PLANNED schema

Example: the apple the user asked to see keeps its identity across the session:

```json
{
  "entity_id": "apple_01",
  "concept_id": "apple",
  "session_id": "…",
  "properties": {},
  "transform": { "position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1] },
  "relationships": [],
  "visual_state": { "visible": true, "last_action": "show", "parts": { "body": true, "stem": true, "leaf": true } },
  "provenance": {
    "created_at": "…",
    "route": "user_request",
    "utterance": "show me an apple",
    "asset_id": "apple_default",
    "asset_source": "procedurally authored for OPERO (data/visual_world/generate_apple_glb.py)",
    "asset_license": "CC0-1.0",
    "verification": "unverified"
  }
}
```

Rules for this record:

1. `entity_id` is stable for the session and unique across restore — `apple_01` never silently becomes `apple_02` while the old one is still remembered.
2. `provenance` is mandatory: which utterance created it, which asset served it, under what license/verification.
3. `visual_state` records *what OPERO showed*, not what was said about it — narration text lives with lessons, not with entities.
4. Restored records are **memory, not truth**: before showing a restored entity, the registry must re-confirm the asset (§9, `RULES.md` §4).

### 5.3 What visual memory must never store

- screenshot pixels or camera frames (perception bytes stay out of memory — `ARCHITECTURE.md` §8);
- model chain-of-thought;
- any claim that an object exists when its asset is gone.

---

## 6. Entity memory — PARTIAL (CURRENT identity, PLANNED durability)

| Aspect | Status | Detail |
|---|---|---|
| Deterministic IDs | **CURRENT** | `{concept}_{NN:02d}` counters in `VisualWorldModel`; restored counters in `from_dict` prevent collisions |
| Identity within session | **CURRENT** | router and bridge reuse live entities; tests assert no duplication |
| Identity across sessions | **PLANNED** | Phase 15 decides: either restore the same world or start fresh *and say so* — never a silent renumber that pretends continuity |
| Concept vocabulary | **CURRENT** | JSON files under `data/visual_world/concepts/` (data-driven memory of *what kinds of things exist*) |
| Deduplication semantics | **PLANNED** | "the apple from yesterday" must resolve to the remembered entity or honestly report no continuity |

Entity memory is subordinate to the asset registry: an entity ID without a servable asset is a memory of an idea, not of a demonstrable object.

---

## 7. Action history — PARTIAL

| Layer | Status | Detail |
|---|---|---|
| Activity log (session) | **CURRENT** | Every dispatch, tool result, visual route, confirm banner, and error appears in `LogWidget` with timestamps (`main.py` logging + `MainWindow` log) |
| Tool-level records | **CURRENT** (in-session) | `actions` arrays appended alongside live-session state |
| Persistent action history | **PLANNED** | Durable, queryable history ("did I already approve this last week?") with the same provenance discipline as §9; Phase 19 folds it into diagnostics |
| Undo records | **CURRENT** | `core/undo.py` stack for reversible operations (session lifetime) |
| Confirmation decisions | **CURRENT** (banner + log) / PLANNED durable audit | who approved what, when — required by safety reviews, implemented as log lines today |

History entries must record **outcome truthfully**: attempted ≠ succeeded; a failed tool call is remembered as failed.

---

## 8. Preferences & relationship memory

### 8.1 Preferences — PARTIAL

- **CURRENT**: `memory/config_manager.py` + config files persist UI/theme/accent/language/model settings; declared preferences also live under the long-term `preferences` category; prompt formatting gives identity + preferences priority for the core prompt slice.
- **PLANNED**: preference *learning* beyond explicit `save_memory` writes; conflict handling when config and memory disagree (config wins for machine settings, memory wins for personal taste — record the rule, test it); a single "what OPERO knows about me" view with edit/delete everywhere (overlay exists; parity pass pending).

### 8.2 Relationship memory — CURRENT (as data, PLANNED as reasoning)

- **CURRENT**: `relationships` category stores user-declared facts ("sister: older sister") exactly as written.
- **PLANNED**: OPERO may *reference* relationships in conversation ("your sister's birthday came up last month") — but must never infer relationships the user didn't state, and never graph them into the visual world model without an explicit request (relationship memory ≠ scene graph).

---

## 9. Provenance

**The binding rule: every durable record either carries provenance or is explicitly marked as unverified user input.**

| Store | Provenance status |
|---|---|
| Asset Registry | **CURRENT**: `source`, `license`, verification axis, selection order prefers verified (`core/visual/assets.py`) |
| Concept files | **CURRENT**: JSON files with descriptions; discoverable origin (repo) |
| Long-term memory entries | **PLANNED**: today entries are `{value}` (+ optional metadata) written by the `save_memory` tool; add `created_at`, `source_tool`, `session_id`, and a user-facing "why this is here" |
| Visual memory records | **PLANNED (mandatory)**: §5.2 schema |
| Lesson/ISL sign data | **PLANNED (mandatory)**: authoritative citation per item (`PRD.md` §8) |
| Conversation facts shown to user | Policy: distinguish fetched / remembered / inferred / unknown (`RULES.md` §5) |

No provenance ⇒ the record may not be presented as authoritative.

---

## 10. Safety-sensitive information

**Policy (binding now):** these are never stored in any memory store — enforced by tool description today, by tests in Phase 19:

- passwords, API keys, tokens, session cookies, authorization headers;
- payment card / government ID numbers;
- secrets embedded in file contents or screenshots;
- raw perception bytes (screenshots/camera frames) in any persistent store.

| Rule | Detail |
|---|---|
| Redaction at write | `save_memory` values that look like credentials are rejected (PLANNED enforcement; today only length truncation exists at 380 chars) |
| Redaction at read | Diagnostics, exports, and logs pass a secret-scrub (Phase 19) |
| Config files ≠ memory | `config/` credential stores are outside the memory system and outside prompts; never copied into memory |
| User control | Everything in §2 that is durable is viewable, editable, and deletable by the user (overlay exists for long-term memory; visual/action stores inherit the same rights when implemented) |

---

## 11. Memory principles (binding on all current and future stores)

1. **Explicit provenance** — records say where they came from (§9).
2. **No fabricated memory** — store what happened or what the user said; never synthesize history (`RULES.md` §5).
3. **Deterministic identity where appropriate** — `apple_01` stays `apple_01`; counters restore with the world.
4. **User control** — view, edit, export, delete; deletion actually deletes (tested in Phase 15).
5. **Privacy** — memory stays on this machine by default; nothing leaves without an explicit action that needed it.
6. **Local-first preference** — `memory/long_term.json` on disk; no cloud store required to remember.
7. **Bounded context** — prompt budgets (`PROMPT_CORE_CHARS`/`PROMPT_INDEX_CHARS`) and per-entry limits; storage guard ≠ prompt budget (the lesson recorded in `memory_manager.py`).
8. **Expiration / cleanup** — trim guards against runaway writes; session state ends with the session; stale visual records re-validate or expire (Phase 15).
9. **Conflict handling** — config vs memory precedence defined in §8.1; duplicate keys update in place with an auditable merge (`update_memory` recursive update).
10. **Versioning** — stores serialize with explicit `version` fields where they exist today (world model v1, asset registry v1); migrations belong to Phase 15/19.

---

## 12. How memory connects to the rest of OPERO

```text
                    ┌──────────────────────────┐
                    │   Gemini (model calls)   │
                    │  reads: prompt core+idx  │
                    │  writes: save_memory     │
                    └───────┬────────────────┘
                            │ never fabricates entries
                            ▼
┌──────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│  Perception  │───►│  short/long memory   │◄───│   Action system     │
│ (explicit    │    │  (session log,       │    │ (results, confirm   │
│  captures,   │    │   long_term.json)    │    │  decisions, undo →  │
│  metadata    │    └──────────┬───────────┘    │  action history)    │
│  only)       │               │                └─────────────────────┘
└──────────────┘               │
                               ▼
                    ┌──────────────────────┐
                    │  Visual stack        │
                    │  VisualIntent  ◄─ lesson/progress memory (Phase 12/15)
                    │  World Model   ◄─ session visual memory (§5)
                    │  Asset Registry ─► provenance source of truth (§9)
                    └──────────────────────┘
```

| System | Memory reads | Memory writes |
|---|---|---|
| Gemini | prompt core slice + index; `recall_memory` search results | `save_memory` (silent, per tool contract) |
| World Model | restores entities from visual memory (Phase 15) | emits entity snapshots at session end |
| Visual Intent | resolves targets against remembered entities | none — intents are events, not memories |
| Asset Registry | is itself a memory (of assets); re-validates restored claims | registration events with provenance |
| Action system | consults history for idempotence ("already done") | results, approvals, undo records |
| Perception | provides *fresh* observations — never a substitute memory | metadata only; bytes never persisted (§5.3) |

---

## 13. Scope statement

This document **designs** memory architecture only. No new memory system, store, index, or migration is implemented in the documentation phase (`PRD.md` non-goals; `PHASES.md` 15/19 own implementation). When implementation begins, update this file in the same phase — CURRENT labels move only when code and tests say so (`RULES.md` §8).
