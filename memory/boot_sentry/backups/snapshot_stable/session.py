"""Gemini Live session management: connect/reconnect, audio I/O, receive loop.

Session methods are written as standalone async functions that receive the
OperaLive instance as `opero`.  OperaLive delegates to these, keeping its
own class thin.
"""

import asyncio
import time
import traceback
from datetime import datetime

import sounddevice as sd
import numpy as np
from google import genai
from google.genai import types

from core.logger import get_logger
from core.audio_utils import pcm_level, pcm_visemes, _VIS_HOP, _TAIL_MARGIN, _CURSOR_SLACK
from core.config_utils import (
    LIVE_MODEL, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE,
    get_api_key, clean_transcript, is_repeat_chunk,
)
from core.tool_dispatch import ToolDispatcher
from core import audio_devices

log = get_logger(__name__)


def _first_sound(chunk_size: int = CHUNK_SIZE) -> float:
    """Seconds from handing bytes to the output stream to hearing them."""
    return chunk_size / RECEIVE_SAMPLE_RATE


async def receive_loop(opero) -> None:
    """The main receive loop: streams audio, processes transcripts, dispatches tools."""
    out_buf, in_buf = [], []

    try:
        while True:
            async for response in opero.session.receive():

                _sru = getattr(response, "session_resumption_update", None)
                if _sru is not None:
                    if getattr(_sru, "resumable", False) and getattr(_sru, "new_handle", None):
                        if opero._resume_handle is None:
                            log.info("[OPERO] 🔗 Session resumption armed")
                        opero._resume_handle = _sru.new_handle

                if response.data:
                    if opero._interrupted:
                        pass
                    else:
                        if opero._turn_done_event and opero._turn_done_event.is_set():
                            opero._turn_done_event.clear()
                        _audio_data = response.data
                        _SLICE = 2400
                        for _i in range(0, len(_audio_data), _SLICE):
                            try:
                                opero.audio_in_queue.put_nowait(_audio_data[_i : _i + _SLICE])
                            except asyncio.QueueFull as e:
                                log.debug("{}", e)

                if response.server_content:
                    sc = response.server_content

                    if sc.output_transcription and sc.output_transcription.text:
                        txt = clean_transcript(sc.output_transcription.text)
                        if txt and not is_repeat_chunk(txt, out_buf):
                            out_buf.append(txt)
                            opero._visemes.feed_text(txt)

                    if sc.input_transcription and sc.input_transcription.text:
                        txt = clean_transcript(sc.input_transcription.text)
                        if txt:
                            in_buf.append(txt)
                            opero._last_user_speech = time.monotonic()

                    if sc.turn_complete:
                        if opero._turn_done_event:
                            opero._turn_done_event.set()

                        if opero._interrupted:
                            opero._interrupted = False
                            in_buf  = []
                            out_buf = []
                            opero._visemes.reset()
                            continue

                        full_in = " ".join(in_buf).strip()
                        if full_in:
                            opero._last_out_logged = ""
                            opero.ui.write_log(f"You: {full_in}")
                            opero._session_log.append(f"User: {full_in}")
                            if opero._dashboard:
                                asyncio.create_task(opero._dashboard.broadcast({
                                    "type": "log", "speaker": "user",
                                    "text": full_in,
                                    "ts": datetime.now().isoformat(),
                                }))
                        in_buf = []

                        full_out = " ".join(out_buf).strip()
                        from core.config_utils import _REPEAT_MIN
                        if full_out and len(full_out) >= _REPEAT_MIN and opero._last_out_logged:
                            if full_out in opero._last_out_logged:
                                full_out = ""
                        if full_out:
                            opero._last_out_logged = full_out
                            opero.ui.write_log(f"{opero._asst_name}: {full_out}")
                            opero._session_log.append(f"{opero._asst_name}: {full_out}")
                            if opero._dashboard:
                                asyncio.create_task(opero._dashboard.broadcast({
                                    "type": "log", "speaker": "opero",
                                    "text": full_out,
                                    "ts": datetime.now().isoformat(),
                                }))
                        out_buf = []

                        if opero._vision_close_pending:
                            opero._vision_close_pending = False
                            opero._vision_busy = False
                            async def _cam_close():
                                await asyncio.sleep(2.0)
                                opero.ui.stop_camera_stream()
                            asyncio.create_task(_cam_close())

                if response.tool_call:
                    fn_responses = []
                    for fc in response.tool_call.function_calls:
                        log.info(f"[OPERO] 📞 {fc.name}")
                        fr = await opero._tool_dispatcher.execute_tool(fc, opero)
                        fn_responses.append(fr)
                    await opero.session.send_tool_response(
                        function_responses=fn_responses
                    )
                    await opero.flush_pending_vision()
    except Exception as e:
        log.error(f"[OPERO] ❌ Recv: {e}")
        traceback.print_exc()
        raise


async def play_audio(opero) -> None:
    """Speaker output loop: pulls chunks from audio_in_queue, writes to stream."""
    log.info("[OPERO] 🔊 Play started")

    _spk_name = audio_devices.resolve(None, "output")
    _spk_dev  = audio_devices.resolve(_spk_name, "output")
    if _spk_dev is not None:
        log.info(f"[OPERO] 🔊 Output device: {_spk_name}")

    def _open_spk(dev):
        st = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            device=dev,
        )
        st.start()
        return st

    try:
        stream = _open_spk(_spk_dev)
    except Exception as _e:
        if _spk_dev is None:
            raise
        log.warning(f"[OPERO] ⚠️  Output device '{_spk_name}' failed: {_e} -- using default")
        opero.ui.write_log(f"SYS: Speaker '{_spk_name}' unavailable -- using system default.")
        stream = _open_spk(None)

    try:
        lat = float(getattr(stream, "latency", 0.0) or 0.0)
        if 0.0 < lat < 1.0:
            opero._out_latency = lat
        log.info(f"[OPERO] 🔊 Output latency {opero._out_latency*1000:.0f} ms "
              f"→ echo tail {(opero._out_latency + _TAIL_MARGIN)*1000:.0f} ms")
    except Exception as e:
        log.debug("{}", e)

    try:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    opero.audio_in_queue.get(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                if (
                    opero._turn_done_event
                    and opero._turn_done_event.is_set()
                    and opero.audio_in_queue.empty()
                ):
                    opero.set_speaking(False)
                    opero._turn_done_event.clear()
                continue

            opero.set_speaking(True)

            batch = bytearray(chunk)
            while len(batch) < 9600:
                try:
                    batch.extend(opero.audio_in_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            try:
                pcm = np.frombuffer(bytes(batch), dtype=np.int16)
                hop = _VIS_HOP / RECEIVE_SAMPLE_RATE
                frames = pcm_visemes(pcm, sr=RECEIVE_SAMPLE_RATE)
                now = time.time()
                horizon = opero._out_latency + _CURSOR_SLACK
                if not (now <= opero._play_cursor <= now + horizon):
                    opero._play_cursor = now + _first_sound()
                at = opero._play_cursor
                opero._play_cursor += pcm.size / RECEIVE_SAMPLE_RATE
                if frames:
                    frames = opero._visemes.frames(frames, hop)
                    opero.ui.push_visemes(frames, hop, at)
                    opero._out_level = max(f[0] for f in frames)
                    opero._echo.note_output(pcm, RECEIVE_SAMPLE_RATE,
                                           opero._out_level)
                else:
                    lvl = pcm_level(pcm)
                    opero.ui.set_audio_level(lvl)
                    opero._out_level = lvl
                    opero._echo.note_output(pcm, RECEIVE_SAMPLE_RATE, lvl)
            except Exception as e:
                log.debug("{}", e)

            try:
                await asyncio.to_thread(stream.write, bytes(batch))
            except (RuntimeError, asyncio.CancelledError):
                break
    except Exception as e:
        log.error(f"[OPERO] ❌ Play: {e}")
        raise
    finally:
        opero.set_speaking(False)
        stream.stop()
        stream.close()


async def listen_audio(opero) -> None:
    """Microphone input loop: opens sounddevice stream, feeds audio to out_queue."""
    log.info("[OPERO] 🎤 Mic started")
    loop = asyncio.get_event_loop()

    def callback(indata, frames, time_info, status):
        if opero._wake_enabled and not opero._awake:
            det = opero._wake_detector
            if det is not None:
                det.feed(indata)
            return
        with opero._speaking_lock:
            opero_speaking = opero._is_speaking

        if opero_speaking:
            return

        if opero._tail_active():
            try:
                if not opero._echo.is_user_speech(
                        indata, SEND_SAMPLE_RATE, pcm_level(indata)):
                    return
                opero._tail_until = 0.0
            except Exception:
                return
        elif opero._echo._hist:
            opero._echo.reset()

        if opero._ptt_enabled and not opero._ptt_held:
            return

        if not opero.ui.muted and not opero._phone_active:
            data = indata.tobytes()
            def _safe_put():
                try:
                    opero.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                except asyncio.QueueFull as e:
                    log.debug("{}", e)
            loop.call_soon_threadsafe(_safe_put)
            try:
                opero.ui.set_audio_level(pcm_level(indata))
            except Exception as e:
                log.debug("{}", e)

    try:
        def _open_mic(dev):
            return sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                device=dev,
                callback=callback,
            )

        from memory.config_manager import get_input_device
        _mic_name = get_input_device()
        _mic_dev  = audio_devices.resolve(_mic_name, "input")
        if _mic_dev is not None:
            log.info(f"[OPERO] 🎤 Input device: {_mic_name}")
        try:
            _mic_stream = _open_mic(_mic_dev)
        except Exception as _e:
            if _mic_dev is None:
                raise
            log.warning(f"[OPERO] ⚠️  Mic '{_mic_name}' failed: {_e} -- using default")
            opero.ui.write_log(
                f"SYS: Microphone '{_mic_name}' unavailable -- using system default."
            )
            _mic_stream = _open_mic(None)

        with _mic_stream:
            log.info("[OPERO] 🎤 Mic stream open")
            while not opero._stop:
                await asyncio.sleep(0.1)
    except Exception as e:
        log.error(f"[OPERO] ❌ Mic: {e}")
        raise


async def send_realtime(opero) -> None:
    """Drain the out_queue and stream mic/phone PCM to Gemini."""
    while True:
        msg = await opero.out_queue.get()
        await opero.session.send_realtime_input(
            audio=types.Blob(
                data=msg["data"],
                mime_type=msg.get("mime_type", "audio/pcm"),
            )
        )


async def reconnect_loop(opero, voice_engine: str = "opero") -> None:
    """Inner reconnect loop: connect, run TaskGroup, handle errors, back off."""
    from core.config_utils import API_CONFIG_PATH
    import json

    while True:
        try:
            log.info("[OPERO] Connecting...")
            opero.ui.set_state("THINKING")
            _resumed_with = opero._resume_handle is not None
            config = opero._build_config()

            client = genai.Client(
                api_key=get_api_key(),
                http_options={"api_version": "v1alpha" if opero._enhanced_live else "v1beta"}
            )

            async with (
                client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                asyncio.TaskGroup() as tg,
            ):
                opero.session          = session
                opero.audio_in_queue   = asyncio.Queue()
                opero.out_queue        = asyncio.Queue(maxsize=200)
                opero._turn_done_event = asyncio.Event()

                opero._pending_vision       = None
                opero._vision_cam_active    = False
                opero._vision_close_pending = False
                opero._vision_busy          = False
                opero._vision_last_time     = 0.0
                opero._interrupted          = False

                log.info("[OPERO] Connected.")
                if _resumed_with:
                    opero.ui.write_log("SYS: Reconnected -- conversation restored.")

                if opero._wake_enabled:
                    opero._ensure_wake_detector()
                    opero._awake = False
                    opero.ui.set_state("SLEEPING")
                    opero.ui.write_log("SYS: OPERO online -- sleeping. Say 'Hey opero' to wake me.")
                else:
                    opero._awake = True
                    opero.ui.set_state("LISTENING")
                    opero.ui.write_log("SYS: OPERO online.")

                if opero._dashboard:
                    await opero._dashboard.broadcast({"type": "status", "state": "active"})

                opero._reconnect_event.clear()
                tg.create_task(opero._watch_reconnect())
                tg.create_task(send_realtime(opero))
                if voice_engine == "assemblyai":
                    from core.assemblyai_voice import AssemblyAIVoice
                    opero._voice_generation += 1
                    opero._assemblyai_engine = AssemblyAIVoice(
                        opero, opero._voice_generation, opero._submit_assemblyai_transcript,
                    )
                    tg.create_task(opero._run_assemblyai_input(
                        opero._assemblyai_engine, opero._voice_generation,
                    ))
                else:
                    tg.create_task(listen_audio(opero))
                tg.create_task(receive_loop(opero))
                tg.create_task(play_audio(opero))
                tg.create_task(opero._run_system_monitor())
                tg.create_task(opero._run_background_monitor())
                tg.create_task(opero._run_proactive_mode())
                tg.create_task(opero._run_sleep_watch())
                if opero._dashboard:
                    tg.create_task(opero._relay_phone_audio())

                from memory.config_manager import get_brief_enabled
                if not opero._briefing_sent and get_brief_enabled() and opero._awake:
                    opero._briefing_sent = True
                    tg.create_task(opero._send_startup_briefing())

        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except BaseException as e:
            from core.session_reconnect import (
                _is_reconnect_signal, _keep_context_of,
            )
            if _is_reconnect_signal(e):
                log.info("[OPERO] Voluntary reconnect requested.")
                if not _keep_context_of(e):
                    opero._resume_handle = None
                if getattr(opero, '_voice_engine_reconnect', False):
                    opero._voice_engine_reconnect = False
                    return
                opero._conn_backoff = 0
                continue

            if _resumed_with and (
                "resum" in str(e).lower()
                or "handle" in str(e).lower()
                or "INVALID_ARGUMENT" in str(e)
                or "NOT_FOUND" in str(e)
            ):
                log.info("[OPERO] 🔗 Resumption handle rejected -- starting a fresh session")
                opero.ui.write_log("SYS: Could not restore the conversation -- starting fresh.")
                opero._resume_handle = None
                opero._conn_backoff = 0
                continue

            err_str = str(e)
            log.info(f"[OPERO] Error ({type(e).__name__}): {e}")
            traceback.print_exc()

            if opero._tuned_live and (
                "INVALID_ARGUMENT" in err_str
                or "Unknown name" in err_str
                or "unexpected keyword" in err_str
                or "realtime_input" in err_str.lower()
                or "media_resolution" in err_str.lower()
                or "thinking" in err_str.lower()
            ):
                opero._tuned_live = False
                log.info("[OPERO] Live tuning rejected -- reconnecting without it.")
                continue

            if opero._enhanced_live and (
                "INVALID_ARGUMENT" in err_str
                or "proactiv" in err_str.lower()
                or "Unknown name" in err_str
                or "unexpected keyword" in err_str
            ):
                opero._enhanced_live = False
                opero.ui.write_log(
                    "SYS: Proactive audio unavailable -- reconnecting without it."
                )
                continue

            if "API key not valid" in err_str or "1007" in err_str:
                opero.ui.write_log("ERR: API key invalid -- please re-enter your key.")
                opero.ui.set_state("SLEEPING")
                opero.ui.prompt_reconfig()
                while not opero.ui._win._ready:
                    await asyncio.sleep(1)
                log.info("[OPERO] New API key saved -- reconnecting...")
                _conn_backoff = 3
                continue

            is_net_err = any(k in err_str for k in (
                "TimeoutError", "timed out", "getaddrinfo", "CancelledError",
                "ConnectionRefusedError", "OSError", "Cannot connect",
            ))
            if is_net_err:
                _conn_backoff = min(getattr(opero, "_conn_backoff", 3) * 2, 60)
                opero._conn_backoff = _conn_backoff
                opero.ui.write_log(
                    f"NET: Connection failed -- retrying in {_conn_backoff}s. "
                    "(a VPN may be required)"
                )
            else:
                opero._conn_backoff = 3
        finally:
            if opero._assemblyai_engine is not None:
                opero._assemblyai_engine.stop()
                opero._assemblyai_engine = None
            opero.session = None
            if len(opero._session_log) >= 3:
                asyncio.create_task(opero._save_session_summary())

        opero.set_speaking(False)
        opero.ui.set_state("SLEEPING")

        if opero._dashboard:
            await opero._dashboard.broadcast({"type": "status", "state": "sleeping"})

        delay = getattr(opero, "_conn_backoff", 3)
        log.info(f"[OPERO] Reconnecting in {delay}s...")
        await asyncio.sleep(delay)
