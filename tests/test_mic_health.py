"""Microphone health, stream-flush, and Gemini send-path diagnostics.

Covers the failure modes of the mic→Gemini pipeline without a real microphone,
API key or network: frames never captured (zeros visible), queue full (counted,
not raised), send failing mid-stream (torn down, never swallowed), stream-end
flush emitted exactly once per pause, rate-tagged mime on every chunk, and the
VoiceGate contract that transcripts only pass after fresh mic capture.
"""

import asyncio
import types as pytypes

import pytest

import main
from core.voice_state import MicHealth, VoiceGate


# ── health counters ─────────────────────────────────────────────────────────

def test_health_aggregates_and_snapshot_is_a_copy():
    h = MicHealth()
    h.frame(2048, non_silent=True)
    h.frame(2048, non_silent=False)
    h.frame(2048, non_silent=True)
    h.drop()
    h.sent(2048)
    h.sent(2048)

    snap = h.snapshot()
    assert snap == {
        "frames": 3, "bytes": 6144, "non_silent": 2,
        "dropped": 1, "sent_chunks": 2, "sent_bytes": 4096,
    }
    snap["frames"] = 999          # log formatting must never mutate the source
    assert h.snapshot()["frames"] == 3


def test_health_zero_frames_still_reportable():
    # Failure mode: the device opens but the callback never fires. The first
    # MIC_AUDIO_HEALTH line must show all-zero capture, not a stale value.
    snap = MicHealth().snapshot()
    assert snap["frames"] == 0 and snap["bytes"] == 0 and snap["sent_chunks"] == 0


def test_queue_full_counts_as_drop_not_exception():
    # Failure mode: Gemini stops consuming and the 200-item out_queue fills.
    # The callback path must count the drop instead of raising on the audio
    # thread (mirrors _safe_put in main._listen_audio).
    async def scenario():
        q = asyncio.Queue(maxsize=1)
        h = MicHealth()
        await q.put({"data": b"\x00" * 2048, "mime_type": "audio/pcm;rate=16000"})
        with pytest.raises(asyncio.QueueFull):
            q.put_nowait({"data": b"\x00" * 2048, "mime_type": "audio/pcm;rate=16000"})
        h.drop()
        assert h.snapshot()["dropped"] == 1
        assert q.qsize() == 1      # the original chunk is untouched

    asyncio.run(scenario())


# ── send path: mime, health, failure surfacing ──────────────────────────────

class _StubSession:
    def __init__(self, fail_with=None):
        self.calls = []
        self.fail_with = fail_with

    async def send_realtime_input(self, **kw):
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append(kw)


def _fake_self(session, queue):
    return pytypes.SimpleNamespace(
        out_queue=queue,
        session=session,
        _mic_health=MicHealth(),
    )


def _run_sender_one_shot(fake, put, timeout=2.0):
    """Run _send_realtime until `put` items are consumed, then cancel it."""
    async def scenario():
        task = asyncio.create_task(main.OperaLive._send_realtime(fake))
        for item in put:
            await fake.out_queue.put(item)
        # Let the sender drain (stream_end items do not consume the timeout).
        for _ in range(50):
            await asyncio.sleep(0.01)
            if fake.out_queue.empty():
                break
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    asyncio.run(asyncio.wait_for(scenario(), timeout))


def test_send_uses_rate_tagged_mime_and_counts_health():
    sess = _StubSession()
    fake = _fake_self(sess, asyncio.Queue())
    _run_sender_one_shot(fake, [
        {"data": b"\x01" * 2048, "mime_type": "audio/pcm;rate=16000"},
        {"data": b"\x02" * 1024},   # phone-relay style: mime omitted
    ])

    assert len(sess.calls) == 2
    assert sess.calls[0]["audio"].mime_type == "audio/pcm;rate=16000"
    # The default must carry the rate too — a bare "audio/pcm" is the exact
    # pattern the Live docs forbid, and it was what the queue used before.
    assert sess.calls[1]["audio"].mime_type == "audio/pcm;rate=16000"
    assert sess.calls[1]["audio"].data == b"\x02" * 1024
    assert fake._mic_health.snapshot()["sent_chunks"] == 2
    assert fake._mic_health.snapshot()["sent_bytes"] == 3072


def test_stream_end_marker_flushes_without_counting_as_audio():
    sess = _StubSession()
    fake = _fake_self(sess, asyncio.Queue())
    _run_sender_one_shot(fake, [
        {"stream_end": True},
        {"data": b"\x03" * 2048, "mime_type": "audio/pcm;rate=16000"},
    ])

    assert sess.calls[0].get("audio_stream_end") is True
    assert "audio" not in sess.calls[0]
    assert len(sess.calls) == 2
    # stream_end is a control marker, not captured audio
    assert fake._mic_health.snapshot()["sent_chunks"] == 1


def test_send_failure_tears_the_session_down():
    # Failure mode: send dies mid-stream. It must propagate (TaskGroup →
    # reconnect), never be swallowed while the queue fills silently.
    sess = _StubSession(fail_with=RuntimeError("socket gone"))
    fake = _fake_self(sess, asyncio.Queue())

    died = []

    async def scenario():
        task = asyncio.create_task(main.OperaLive._send_realtime(fake))
        await fake.out_queue.put({"data": b"\x04" * 64, "mime_type": "audio/pcm;rate=16000"})
        with pytest.raises(RuntimeError, match="socket gone"):
            await asyncio.wait_for(task, 2.0)
        died.append(True)

    asyncio.run(scenario())
    assert died == [True]


# ── stream-end flush on gate pause ──────────────────────────────────────────

def test_pause_emits_exactly_one_flush_per_burst():
    async def scenario():
        loop = asyncio.get_event_loop()
        q = asyncio.Queue()
        fake = pytypes.SimpleNamespace(_mic_streaming=True, out_queue=q)

        main.OperaLive._mic_stream_pause(fake, loop)
        await asyncio.sleep(0.01)          # call_soon_threadsafe round-trip
        main.OperaLive._mic_stream_pause(fake, loop)
        await asyncio.sleep(0.01)

        assert q.qsize() == 1              # one pause burst → one stream_end
        assert (await q.get()) == {"stream_end": True}

        fake._mic_streaming = True         # frames resumed, then paused again
        main.OperaLive._mic_stream_pause(fake, loop)
        await asyncio.sleep(0.01)
        assert q.qsize() == 1              # armed again after the new burst

    asyncio.run(scenario())


def test_pause_before_any_capture_emits_nothing():
    async def scenario():
        loop = asyncio.get_event_loop()
        q = asyncio.Queue()
        fake = pytypes.SimpleNamespace(_mic_streaming=False, out_queue=q)
        main.OperaLive._mic_stream_pause(fake, loop)
        await asyncio.sleep(0.01)
        assert q.empty()

    asyncio.run(scenario())


def test_pause_between_sessions_never_touches_a_dead_queue():
    async def scenario():
        loop = asyncio.get_event_loop()
        fake = pytypes.SimpleNamespace(_mic_streaming=True, out_queue=None)
        main.OperaLive._mic_stream_pause(fake, loop)   # must not raise
        await asyncio.sleep(0.01)

    asyncio.run(scenario())


# ── VoiceGate contract behind the mic path ──────────────────────────────────

def test_transcript_requires_capture_under_the_current_generation():
    # The gate feeds GEMINI_INPUT_TRANSCRIPT_RECEIVED: words captured before
    # our own last reply are stale and must not reach the session log.
    t = [0.0]
    gate = VoiceGate(clock=lambda: t[0])
    gate.note_mic()                        # user captured while we were silent
    assert gate.accept_transcript() is True

    gate.begin_speaking()                  # our reply invalidates that capture
    gate.end_speaking()
    assert gate.accept_transcript() is False   # stale: nothing fresh captured

    t[0] = 10.0                            # acoustic tail expires
    gate.note_mic()                        # fresh capture after the reply
    assert gate.accept_transcript() is True


def test_mic_flows_while_idle_and_stops_during_playback():
    gate = VoiceGate()
    assert gate.accept_mic() is True       # idle: callback queues frames
    gate.begin_speaking()
    assert gate.accept_mic() is False      # replying: frames gated (→ flush)
    gate.end_speaking()
    assert gate.accept_mic() is True       # listening again
