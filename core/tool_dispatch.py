"""Tool dispatch: discovers, validates, and executes tool calls from the LLM.

Contains TOOL_DECLARATIONS (inline tools tied to live-session state) and
the ToolDispatcher class which manages both inline and file-backed tools.
"""

import asyncio
import traceback
from pathlib import Path

from core.logger import get_logger
log = get_logger(__name__)

from core import undo as undo_stack
from core.action_loader import discover_actions
from core.plugin_loader import discover_plugins

# Inline tools stay here because their handling is woven into live-session
# state -- vision capture/injection, camera stream, memory writes, the monitor
# engine, and shutdown.  All other tools live in their own action file and are
# auto-discovered by core.action_loader (see ToolDispatcher.__init__).
TOOL_DECLARATIONS = [
    {
        "name": "system_status",
        "description": (
            "Returns real-time system metrics: CPU usage, RAM, GPU load, CPU temperature, "
            "uptime, and process count. Use when the user asks about computer performance, "
            "temperature, memory, or resource usage."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures the screen or webcam image and lets you analyze it. "
            "MUST be called when user asks what is on screen, what you see, "
            "look at camera, analyze my screen, etc. "
            "You have NO visual ability without this tool. "
            "After the image is captured it is sent directly to you -- describe what you see and answer the user's question. "
            "When using camera: the live view stays open until user says close it or calls close_camera."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "close_camera",
        "description": (
            "Closes the live camera view shown on screen. "
            "Call when the user says (in ANY language): close camera, stop camera, "
            "turn off camera, that's creepy, etc."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "manage_monitor",
        "description": (
            "Add, remove, or list background monitoring topics. "
            "OPERO checks these topics once a day and alerts the user when there is a new development. "
            "Use 'add' when the user says 'monitor X', 'track X', 'follow X'. "
            "Use 'remove' when the user says 'stop monitoring X'. "
            "Use 'list' when the user asks what is being monitored. "
            "Do NOT add crypto, financial, or trading topics."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type":        "STRING",
                    "description": "add | remove | list",
                },
                "topic": {
                    "type":        "STRING",
                    "description": "Topic to monitor or stop monitoring (e.g. 'space exploration', 'AI news')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "shutdown_opero",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop opero. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving -- just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity -- name, age, birthday, city, job, language, nationality | "
                        "preferences -- favorite food/color/music/film/game/sport, hobbies | "
                        "projects -- active projects, goals, things being built | "
                        "relationships -- friends, family, partner, colleagues | "
                        "wishes -- future plans, things to buy, travel dreams | "
                        "notes -- habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": (
            "Look up a fact you have stored about the user but which is NOT in "
            "the memory block of your system prompt. "
            "The prompt lists the keys it did not have room for under "
            "'[ALSO REMEMBERED]' -- if the user asks about anything named there, "
            "call this FIRST. "
            "Also call it before saying you do not know something personal, and "
            "when the user asks what you remember about them (leave query empty "
            "for everything). "
            "This is a local file search: it is instant and costs nothing."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Keyword to search for -- a name, a topic, a category "
                        "(e.g. 'ayse', 'coffee', 'projects'). "
                        "Leave empty to list everything stored."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "undo",
        "description": (
            "Reverse the last change YOU made to this computer -- a file you "
            "moved, renamed, created or wrote, or a setting you changed such as "
            "volume, brightness, dark mode or WiFi. "
            "Call this whenever the user says undo, revert, take it back, put it "
            "back, cancel that, or tells you that you did the wrong thing, in ANY "
            "language. "
            "Use action='list' when they ask what can be undone. "
            "This only covers your own actions -- it is not the Ctrl+Z of whatever "
            "application is on screen (that is computer_settings with action 'undo')."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "undo (default) -- reverse the last change | list -- show what can be undone",
                },
            },
            "required": [],
        },
    },
]


class ToolDispatcher:
    """Discovers, validates, and executes tool calls from the LLM.

    Owns the action and plugin registries and the inline TOOL_DECLARATIONS.
    """

    def __init__(self, ui, memory=None, log_fn=None):
        self.ui = ui
        self._log = log_fn or (lambda msg: log.info(msg))

        _base_dir = Path(__file__).resolve().parent.parent
        _inline_names = {t["name"] for t in TOOL_DECLARATIONS}

        self._action_registry = discover_actions(
            actions_dir=_base_dir / "actions",
            reserved_names=_inline_names,
            logger=lambda msg: log.info(f"[Actions] {msg}"),
        )

        _core_names = _inline_names | self._action_registry.names()
        self._plugin_registry = discover_plugins(
            plugins_dir=_base_dir / "plugins",
            core_tool_names=_core_names,
            logger=lambda msg: log.info(f"[Plugins] {msg}"),
            notify=lambda msg: self.ui.write_log(f"SYS: {msg}"),
        )
        self.ui.get_plugins = self._plugin_registry.list_for_ui
        self.ui.get_plugin_settings = self._plugin_registry.settings_schemas
        self.ui.request_say = None  # set by OperaLive after init

    def get_all_declarations(self) -> list:
        """Return inline + file-backed + plugin tool declarations."""
        return (TOOL_DECLARATIONS
                + self._action_registry.get_tool_declarations()
                + self._plugin_registry.get_tool_declarations())

    def has(self, name: str) -> bool:
        return self._action_registry.has(name) or self._plugin_registry.has(name)

    async def execute_tool(self, fc, opero) -> object:
        """Execute a tool call and return a FunctionResponse.

        `opero` is the OperaLive instance, passed so that tool execution can
        access session state (pending_vision, speak, etc.) without circular
        imports.
        """
        from google.genai import types
        name = fc.name
        args = dict(fc.args or {})

        log.info("🔧 %s  %s", name, args)
        opero.ui.set_state("THINKING")

        if name == "save_memory":
            from memory.memory_manager import update_memory
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                log.info(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not opero.ui.muted:
                opero.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "recall_memory":
                from memory.memory_manager import search_memory
                result = search_memory(args.get("query", ""), limit=8)

            elif name == "undo":
                if str(args.get("action", "")).lower().strip() == "list":
                    items = undo_stack.history()
                    result = ("Things I can undo, most recent first:\n"
                              + "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))
                              ) if items else "I have not changed anything I can undo yet."
                else:
                    result = await loop.run_in_executor(None, undo_stack.undo_last)

            elif name == "screen_process":
                import time as _t_mod
                from actions.screen_processor import _capture_camera, _capture_screen
                _now = _t_mod.monotonic()
                _cooldown = 4.0
                if opero._vision_busy or (_now - opero._vision_last_time) < _cooldown:
                    _wait = max(0, _cooldown - (_now - opero._vision_last_time))
                    log.debug(f"[Vision] ⏳ Cooldown active ({_wait:.1f}s remaining) -- ignoring duplicate call")
                    result = "Vision is still processing the previous request. I will not call this again."
                else:
                    opero._vision_busy      = True
                    opero._vision_last_time = _now
                    angle     = args.get("angle", "screen").lower()
                    user_text = args.get("text", "What do you see?")
                    if angle == "camera":
                        img_b, mime_t = await loop.run_in_executor(None, _capture_camera)
                        opero.ui.start_camera_stream()
                        opero._vision_cam_active = True
                        log.info(f"[Vision] 📷 Camera: {len(img_b):,} bytes")
                        _stall = "camera"
                    else:
                        img_b, mime_t = await loop.run_in_executor(None, _capture_screen)
                        log.info(f"[Vision] 🖥️  Screen: {len(img_b):,} bytes")
                        _stall = "screen"
                    opero._pending_vision = (img_b, mime_t, user_text, angle)
                    result = (
                        f"[VISION_ACTIVE] {_stall.capitalize()} captured and attached to this "
                        f"same exchange. Do not acknowledge and do not answer yet -- the image "
                        f"is arriving with this result. Reply once, from what you actually see "
                        f"in it."
                    )

            elif name == "close_camera":
                opero.ui.stop_camera_stream()
                result = "Camera closed."

            elif name == "system_status":
                from actions.system_monitor import get_system_status
                r = await loop.run_in_executor(None, get_system_status)
                result = str(r)

            elif name == "manage_monitor":
                from actions.background_monitor import (
                    add_monitor, remove_monitor, list_monitors,
                )
                action = args.get("action", "").lower().strip()
                topic  = args.get("topic", "").strip()
                if action == "add" and topic:
                    result = await asyncio.to_thread(add_monitor, topic)
                elif action == "remove" and topic:
                    result = await asyncio.to_thread(remove_monitor, topic)
                elif action == "list":
                    topics = await asyncio.to_thread(list_monitors)
                    result = ("Monitoring: " + ", ".join(topics)) if topics else "No topics are being monitored."
                else:
                    result = "Specify action (add/remove/list) and a topic."

            elif name == "shutdown_opero":
                opero.ui.write_log("SYS: Shutdown requested.")
                async def _do_shutdown():
                    await opero._save_session_summary()
                    if opero.session:
                        try:
                            await opero.session.send_client_content(
                                turns={"role": "user", "parts": [{"text": "Say a brief natural goodbye to the user."}]},
                                turn_complete=True,
                            )
                        except Exception as e:
                            log.debug("{}", e)
                    await asyncio.sleep(1.5)
                    import os as _os
                    _os._exit(0)
                asyncio.create_task(_do_shutdown())

            elif self._action_registry.has(name):
                if name == "file_processor" and not args.get("file_path") and opero.ui.current_file:
                    args["file_path"] = opero.ui.current_file
                _ctx = {"player": opero.ui, "speak": opero.speak,
                        "response": None, "session_memory": None}
                r = await loop.run_in_executor(None, lambda: self._action_registry.run(name, args, _ctx))
                result = r or "Done."
                if (name == "web_search" and r
                        and not r.startswith("No results")
                        and not r.startswith("Search failed")):
                    _mode  = args.get("mode", "search")
                    _query = args.get("query") or ", ".join(args.get("items", []))
                    _label = f"{_mode.upper()} -- {_query[:38]}" if _query else _mode.upper()
                    opero.ui.show_content(_label, r)

            else:
                if self._plugin_registry.has(name):
                    r = await loop.run_in_executor(
                        None,
                        lambda: self._plugin_registry.run(name, args, player=opero.ui, session_memory=None)
                    )
                    result = r or "Done."
                else:
                    result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            opero.speak_error(name, e)

        if not opero.ui.muted:
            opero.ui.set_state("LISTENING")

        log.info(f"[OPERO] 📤 {name} → {str(result)[:80]}")

        _sched = (self._action_registry.scheduling(name)
                  or self._plugin_registry.scheduling(name))
        _extra = {"scheduling": _sched} if _sched else {}
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result},
            **_extra
        )

    def undo_last(self) -> str:
        return undo_stack.undo_last()
