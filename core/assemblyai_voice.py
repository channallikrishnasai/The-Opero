"""
AssemblyAI voice engine for OPERO.

Architecture:
  AssemblyAI Real-time Streaming STT  →  Gemini (one-shot text)  →  EdgeTTS playback

This replaces the native Gemini Live bidirectional audio pipeline with a
three-stage text-centric flow.  The conversation context, tools and system
prompt are the same as the Live path — only the audio I/O layer changes.

Requires:
  pip install assemblyai
  AssemblyAI API key in config/api_keys.json  ("assemblyai_api_key")
"""
from __future__ import annotations

import asyncio
import io
import json
import queue
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import sounddevice as sd

try:
    import assemblyai as aai
    from assemblyai import RealtimeTranscriber
    _HAS_AAI = True
except ImportError:
    _HAS_AAI = False

from core.tts import EdgeTTSEngine, TTSPlayer
from core import gemini as _gemini_mod
from memory.config_manager import get_assemblyai_key

# ── Constants ─────────────────────────────────────────────────────────────────
SEND_SAMPLE_RATE = 16000   # AssemblyAI expects 16 kHz mono
RECEIVE_SAMPLE_RATE = 24000  # Speaker output rate
CHANNELS = 1
CHUNK_SIZE = 1024          # mic callback blocksize
_TTS_VOICE = "en-US-GuyNeural"  # EdgeTTS voice (matches OPERO default)


class AssemblyAIVoice:
    """Full-duplex voice engine backed by AssemblyAI streaming STT + Gemini
    text completion + EdgeTTS playback.

    Designed to be driven from OperaLive.run() as a drop-in alternative to the
    Gemini Live WebSocket loop.  The caller provides callbacks so the UI layer
    stays decoupled.

    Usage from OperaLive.run()::

        engine = AssemblyAIVoice(opero_ref)
        await engine.run()   # blocks until disconnect / shutdown
    """

    def __init__(self, opero):
        """
        Parameters
        ----------
        opero : OperaLive
            The parent live session — gives access to ui, action_registry,
            plugin_registry, tool declarations, memory, and all the callbacks
            the Gemini Live path uses.
        """
        self.opero = opero
        self.ui = opero.ui

        # ── State ────────────────────────────────────────────────────────
        self._running = False
        self._transcriber: Optional[RealtimeTranscriber] = None
        self._mic_stream: Optional[sd.InputStream] = None
        self._spk_stream: Optional[sd.RawOutputStream] = None

        # Queues
        self._mic_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._tts_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

        # Transcript buffers (mirroring Gemini Live path)
        self._in_buf: list[str] = []    # user words this turn
        self._out_buf: list[str] = []   # assistant words this turn

        # TTS
        self._tts_player: Optional[TTSPlayer] = None
        self._is_speaking = False
        self._speaking_lock = threading.Lock()

        # Echo / barge-in (reuse opero's existing guards)
        self._echo = opero._echo
        self._out_level = 0.0
        self._tail_until = 0.0
        self._play_cursor = 0.0

        # Interrupt
        self._interrupted = False

        # Viseme (lip-sync)
        self._visemes = opero._visemes

        # Session log
        self._session_log = opero._session_log

        # Dashboard
        self._dashboard = opero._dashboard

        # Tool execution — reuse opero's existing method
        self._execute_tool = opero._execute_tool

    # ── Public API ──────────────────────────────────────────────────────────

    async def run(self):
        """Main entry point — blocking.  Mirrors OperaLive.run() structure."""
        if not _HAS_AAI:
            print("[AssemblyAI] ❌ 'assemblyai' package not installed. "
                  "Run: pip install assemblyai", file=sys.stderr)
            self.ui.write_log("SYS: AssemblyAI voice engine unavailable — "
                              "package not installed.")
            raise RuntimeError("assemblyai package not installed")

        api_key = get_assemblyai_key()
        if not api_key:
            print("[AssemblyAI] ❌ No API key configured. "
                  "Set 'assemblyai_api_key' in config/api_keys.json.",
                  file=sys.stderr)
            self.ui.write_log("SYS: AssemblyAI voice engine unavailable — "
                              "no API key. Add 'assemblyai_api_key' to config.")
            raise RuntimeError("no AssemblyAI API key configured")

        self._running = True
        print("[AssemblyAI] Starting voice engine…")

        # Initialize TTS
        self._tts_player = TTSPlayer(EdgeTTSEngine(voice=_TTS_VOICE))

        # Gemini module imported at top level; no instance needed

        # Build system prompt + tool declarations (reuse opero's builder)
        try:
            self._sys_prompt, self._tool_decls = self._build_context()
        except Exception as e:
            print(f"[AssemblyAI] Context build failed: {e}", file=sys.stderr)
            self._sys_prompt = "You are OPERO, a helpful voice assistant."
            self._tool_decls = []

        # Open speaker
        self._open_speaker()

        # Start tasks
        loop = asyncio.get_event_loop()
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._run_stt(api_key))
                tg.create_task(self._process_transcripts())
                tg.create_task(self._play_tts_audio())
        except* Exception as eg:
            for exc in eg.exceptions:
                print(f"[AssemblyAI] Task error: {exc}")
                traceback.print_exc()
        finally:
            self._running = False
            self._close_speaker()
            print("[AssemblyAI] Engine stopped.")

    def stop(self):
        """Graceful shutdown."""
        self._running = False
        if self._transcriber:
            try:
                self._transcriber.close()
            except Exception:
                pass

    def interrupt(self):
        """Cut current TTS playback (barge-in)."""
        self._interrupted = True
        if self._tts_player:
            self._tts_player.stop()
        with self._speaking_lock:
            self._is_speaking = False

    # ── STT (AssemblyAI Real-time) ──────────────────────────────────────────

    async def _run_stt(self, api_key: str):
        """Open AssemblyAI streaming STT and pipe mic audio to it."""
        loop = asyncio.get_event_loop()

        def on_open(self_ref=weakref.ref(self)):
            print("[AssemblyAI] STT connected.")

        def on_data(transcript_obj, self_ref=weakref.ref(self)):
            """Called from AssemblyAI's thread for each partial/final."""
            if not transcript_obj.text:
                return
            ref = self_ref()
            if ref is None:
                return
            # Put the transcript text into the async queue
            loop.call_soon_threadsafe(
                ref._transcript_queue.put_nowait,
                {
                    "text": transcript_obj.text,
                    "final": transcript_obj.audio_end is not None,
                    "confidence": getattr(transcript_obj, "confidence", 0.0),
                }
            )

        def on_error(error, self_ref=weakref.ref(self)):
            print(f"[AssemblyAI] STT error: {error}", file=sys.stderr)

        def on_close(self_ref=weakref.ref(self)):
            print("[AssemblyAI] STT disconnected.")

        import weakref
        self._transcript_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        self._transcriber = RealtimeTranscriber(
            api_key=api_key,
            sample_rate=SEND_SAMPLE_RATE,
            on_open=on_open,
            on_data=on_data,
            on_error=on_error,
            on_close=on_close,
        )
        self._transcriber.connect()

        # Mic capture → AssemblyAI
        mic_name = ""
        try:
            from memory.config_manager import get_input_device
            mic_name = get_input_device()
        except Exception:
            pass

        resolved = None
        try:
            from core.audio_devices import resolve
            resolved = resolve(mic_name, "input") if mic_name else None
        except Exception:
            pass

        def mic_callback(indata, frames, time_info, status):
            if not self._running:
                return
            # Barge-in: detect speech while we're talking
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                level = _pcm_level(indata)
                if level > 200 and (time.monotonic() > self._tail_until):
                    self.interrupt()
            # Stream raw PCM to AssemblyAI
            try:
                self._transcriber.send_audio(indata.tobytes())
            except Exception:
                pass

        dev_info = None
        if resolved is not None:
            dev_info = resolved

        try:
            self._mic_stream = sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                device=dev_info,
                callback=mic_callback,
            )
            self._mic_stream.start()
            print("[AssemblyAI] 🎤 Mic started")

            # Keep running until shutdown
            while self._running:
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[AssemblyAI] Mic error: {e}", file=sys.stderr)
            traceback.print_exc()
        finally:
            if self._mic_stream:
                try:
                    self._mic_stream.stop()
                    self._mic_stream.close()
                except Exception:
                    pass
            self._close_stt()

    def _close_stt(self):
        if self._transcriber:
            try:
                self._transcriber.close()
            except Exception:
                pass
            self._transcriber = None

    # ── Transcript processor (STT → Gemini → TTS) ──────────────────────────

    async def _process_transcripts(self):
        """Drain STT partials/finals, batch into turns, send to Gemini."""
        turn_text = ""

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self._transcript_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            text = msg.get("text", "")
            is_final = msg.get("final", False)

            if is_final:
                turn_text += " " + text
                turn_text = turn_text.strip()
                if turn_text:
                    # Log user speech
                    self.ui.write_log(f"You: {turn_text}")
                    self._session_log.append(f"User: {turn_text}")
                    if self._dashboard:
                        asyncio.create_task(self._dashboard.broadcast({
                            "type": "log", "speaker": "user",
                            "text": turn_text,
                            "ts": datetime.now().isoformat(),
                        }))

                    # Send to Gemini
                    self.ui.set_state("THINKING")
                    response_text = await self._query_gemini(turn_text)
                    turn_text = ""

                    if response_text:
                        # Log assistant response
                        self.ui.write_log(f"{self.opero._asst_name}: {response_text}")
                        self._session_log.append(f"{self.opero._asst_name}: {response_text}")
                        if self._dashboard:
                            asyncio.create_task(self._dashboard.broadcast({
                                "type": "log", "speaker": "opero",
                                "text": response_text,
                                "ts": datetime.now().isoformat(),
                            }))

                        # Feed visemes for lip-sync
                        self._visemes.feed_text(response_text)

                        # Queue TTS
                        await self._tts_queue.put(response_text)

                    self.ui.set_state("LISTENING")
            else:
                # Partial transcript — just update the UI
                pass

    async def _query_gemini(self, user_text: str) -> str:
        """Send text to Gemini (one-shot REST) and return the response text."""
        try:
            from core.gemini import call as gemini_call, FAST

            # Build a config with system instruction
            from google.genai import types as gtypes
            config = gtypes.GenerateContentConfig(
                system_instruction=self._sys_prompt,
            )

            # Convert tool declarations to Gemini format
            gemini_tools = []
            if self._tool_decls:
                fn_decls = []
                for d in self._tool_decls:
                    if isinstance(d, dict):
                        fn_decls.append(d)
                    else:
                        fn_decls.append(d)
                if fn_decls:
                    config.tools = [{"function_declarations": fn_decls}]

            # Use the existing gemini.call() ladder for one-shot
            response = await asyncio.to_thread(
                gemini_call, user_text, FAST, config
            )
            if response is None:
                return "I couldn't generate a response right now."

            # Extract text (response is an SDK response object)
            text = getattr(response, "text", None)
            if text:
                return text.strip()

            # Try candidates if text is empty
            candidates = getattr(response, "candidates", None)
            if candidates and candidates[0].content:
                parts = candidates[0].content.parts
                text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
                func_parts = [p for p in parts if hasattr(p, "function_call") and p.function_call]

                if func_parts:
                    # Execute tools and re-query
                    tool_results = []
                    for fp in func_parts:
                        fc = fp.function_call
                        mock_fc = type('FunctionCall', (), {
                            'name': fc.name,
                            'args': dict(fc.args) if fc.args else {},
                            'id': f"aai_{fc.name}",
                        })()
                        result = await self._execute_tool(mock_fc)
                        tool_results.append(str(getattr(result, 'response', result)))

                    followup = (
                        f"Tool results:\n" +
                        "\n".join(f"- {r}" for r in tool_results) +
                        "\n\nPlease respond to the user based on these results."
                    )
                    response2 = await asyncio.to_thread(
                        gemini_call, followup, FAST
                    )
                    if response2 and getattr(response2, "text", None):
                        return response2.text.strip()
                    return "Done."

                return "".join(text_parts).strip()

            return ""

        except Exception as e:
            print(f"[AssemblyAI] Gemini error: {e}", file=sys.stderr)
            traceback.print_exc()
            return f"Sorry, I encountered an error: {e}"

    # ── TTS playback ────────────────────────────────────────────────────────

    async def _play_tts_audio(self):
        """Drain the TTS queue and play each response via EdgeTTS."""
        while self._running:
            try:
                text = await asyncio.wait_for(
                    self._tts_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if not text:
                continue

            with self._speaking_lock:
                self._is_speaking = True

            self._interrupted = False
            try:
                await asyncio.to_thread(self._tts_player.speak, text)
            except Exception as e:
                print(f"[AssemblyAI] TTS error: {e}", file=sys.stderr)
            finally:
                with self._speaking_lock:
                    self._is_speaking = False

    # ── Speaker output ──────────────────────────────────────────────────────

    def _open_speaker(self):
        try:
            self._spk_stream = sd.RawOutputStream(
                samplerate=RECEIVE_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
            )
            self._spk_stream.start()
        except Exception as e:
            print(f"[AssemblyAI] Speaker open failed: {e}", file=sys.stderr)
            self._spk_stream = None

    def _close_speaker(self):
        if self._spk_stream:
            try:
                self._spk_stream.stop()
                self._spk_stream.close()
            except Exception:
                pass
            self._spk_stream = None

    # ── Context builder ─────────────────────────────────────────────────────

    def _build_context(self):
        """Build the system prompt and tool declarations for Gemini one-shot."""
        from memory.config_manager import get_assistant_name, get_user_name
        from memory.memory_manager import load_memory, format_memory_for_prompt

        asst = get_assistant_name()
        user = get_user_name()
        memory = load_memory()
        mem_str = format_memory_for_prompt(memory)

        # Load system prompt
        _prompt_path = Path(__file__).resolve().parent.parent / "core" / "prompt.txt"
        try:
            sys_prompt = _prompt_path.read_text(encoding="utf-8")
        except Exception:
            sys_prompt = (
                "You are OPERO, a personal AI assistant. "
                "Be concise, direct, and always use the provided tools to complete tasks. "
                "Never simulate or guess results — always call the appropriate tool."
            )

        # Tool declarations
        all_decls = []
        try:
            all_decls = (
                self.opero._action_registry.get_tool_declarations() +
                self.opero._plugin_registry.get_tool_declarations()
            )
        except Exception:
            pass

        # Identity
        addr = (f"Always call the user '{user}'."
                if user else
                "Address the user respectfully.")
        identity = (
            f"Your name is {asst}. Always refer to yourself as {asst}. "
            f"{addr}\n\n"
        )

        # Time
        from datetime import datetime
        now = datetime.now()
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {now.strftime('%A, %B %d, %Y — %I:%M %p')}\n\n"
        )

        parts = [time_ctx, identity]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        # Platform info
        import platform as _platform
        parts.append(
            f"\n[PLATFORM]\n{_platform.system()} {_platform.release()}\n"
        )

        # Voice engine note
        parts.append(
            "\n[VOICE ENGINE]\n"
            "You are being accessed via AssemblyAI voice mode. "
            "Respond concisely — you are speaking, not displaying text.\n"
        )

        return "".join(parts), all_decls


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pcm_level(samples) -> float:
    """RMS level of a PCM int16 buffer."""
    arr = np.frombuffer(samples, dtype=np.int16).astype(np.float64)
    if len(arr) == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr ** 2)))
