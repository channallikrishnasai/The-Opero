"""Tests for the AssemblyAI API-key configuration hotfix.

Root-cause chain covered here: a Gemini transport error (WebSocket 1007,
caused by a malformed ARRAY tool schema) was classified as "invalid API key",
which raised the first-boot/reconfigure overlay; that overlay rewrote
api_keys.json from scratch, wiping the stored AssemblyAI key; the next
voice-engine switch then reported the key as missing.
"""
import json
import logging

import pytest

from memory import config_manager as cm
from core.assemblyai_voice import AssemblyAIVoice

DUMMY = "TEST_ASSEMBLYAI_KEY"
GEMINI_DUMMY = "TEST_GEMINI_KEY_1234567890"


@pytest.fixture
def cfg_path(tmp_path, monkeypatch):
    """Point config_manager at an isolated file for one test."""
    p = tmp_path / "api_keys.json"
    monkeypatch.setattr(cm, "CONFIG_FILE", p)
    return p


# ── validation states ─────────────────────────────────────────────────────

def test_missing_key_reports_missing(cfg_path):
    err = AssemblyAIVoice.validate_configuration()
    assert err is not None
    assert "AssemblyAI API key is missing" in err


def test_saved_key_validates_as_configured(cfg_path):
    cm.save_assemblyai_key(DUMMY)
    assert AssemblyAIVoice.validate_configuration() is None


def test_key_persists_across_reload(cfg_path):
    cm.save_assemblyai_key(DUMMY)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["assemblyai_api_key"] == DUMMY
    assert cm.get_assemblyai_key() == DUMMY


# ── provider separation ───────────────────────────────────────────────────

def test_gemini_and_assemblyai_keys_stay_separate(cfg_path):
    cm.save_api_keys(GEMINI_DUMMY)
    cm.save_assemblyai_key(DUMMY)
    assert cm.get_gemini_key() == GEMINI_DUMMY
    assert cm.get_assemblyai_key() == DUMMY
    cm.save_assemblyai_key("TEST_ASSEMBLYAI_KEY_2")
    assert cm.get_gemini_key() == GEMINI_DUMMY
    cm.save_api_keys(GEMINI_DUMMY + "x")
    assert cm.get_assemblyai_key() == "TEST_ASSEMBLYAI_KEY_2"


# ── normalisation and empty handling ──────────────────────────────────────

def test_whitespace_and_quotes_normalised(cfg_path):
    cm.save_assemblyai_key(f'  "{DUMMY}"  ')
    assert cm.get_assemblyai_key() == DUMMY
    cfg_path.write_text(
        json.dumps({"assemblyai_api_key": f"'{DUMMY}'"}), encoding="utf-8")
    assert cm.get_assemblyai_key() == DUMMY


def test_empty_key_never_overwrites_stored_key(cfg_path):
    cm.save_assemblyai_key(DUMMY)
    cm.save_assemblyai_key("")
    cm.save_assemblyai_key("   ")
    assert cm.get_assemblyai_key() == DUMMY
    cm.save_assemblyai_key(f"  '{DUMMY}' ")
    assert cm.get_assemblyai_key() == DUMMY


# ── logging hygiene ───────────────────────────────────────────────────────

def test_key_never_appears_in_log_output(cfg_path, caplog):
    with caplog.at_level(logging.DEBUG):
        cm.save_assemblyai_key(DUMMY)
        cm.get_assemblyai_key()
        AssemblyAIVoice.validate_configuration()
    assert DUMMY not in caplog.text


# ── voice engine reads the persisted key ──────────────────────────────────

def test_voice_engine_configuration_reads_persisted_key(cfg_path):
    cm.save_assemblyai_key(DUMMY)
    cm.save_voice_engine("assemblyai")
    assert cm.get_voice_engine() == "assemblyai"
    assert cm.get_assemblyai_key() == DUMMY
    assert AssemblyAIVoice.validate_configuration() is None


def test_opero_unchanged_when_assemblyai_not_configured(cfg_path):
    assert cm.get_voice_engine() == "opero"
    err = AssemblyAIVoice.validate_configuration()
    assert err is not None and "missing" in err


# ── the wipe: reconfigure must merge, not overwrite ───────────────────────

def test_setup_reconfigure_preserves_assemblyai_key(cfg_path):
    cm.save_api_keys(GEMINI_DUMMY)
    cm.save_assemblyai_key(DUMMY)
    cm.save_voice_engine("assemblyai")
    cm.save_setup_config("GEMINI_NEW_KEY_1234567890", "windows")
    assert cm.get_assemblyai_key() == DUMMY
    assert cm.get_voice_engine() == "assemblyai"
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert raw["gemini_api_key"] == "GEMINI_NEW_KEY_1234567890"
    assert raw["os_system"] == "windows"


def test_setup_reconfigure_rejects_empty_gemini_key(cfg_path):
    cm.save_api_keys(GEMINI_DUMMY)
    cm.save_setup_config("   ", "windows")
    assert cm.get_gemini_key() == GEMINI_DUMMY


# ── the misclassification: 1007 transport close is not a key error ───────

def test_transport_1007_is_not_an_api_key_error():
    import main
    assert main._is_api_key_error(
        "API key not valid. Please pass a valid API key.")
    assert main._is_api_key_error("No API key was provided")
    # Exact failure captured from logs/opero.log (2026-10-03): a WebSocket
    # 1007 close caused by the malformed context_note ARRAY schema.
    err_1007 = ("APIError: 1007 None. * BidiGenerateContentRequest.setup."
                "tools[0].function_declarations[3].parameters."
                "properties[items].items: missing field.")
    assert not main._is_api_key_error(err_1007)
    assert not main._is_api_key_error("1007")
    assert not main._is_api_key_error("TimeoutError while connecting")


# ── schema regression: every ARRAY schema declares its element type ───────

def _walk_decl(node):
    if isinstance(node, dict):
        if node.get("type") == "ARRAY":
            assert "items" in node, f"ARRAY schema missing items: {node}"
        for v in node.values():
            _walk_decl(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _walk_decl(v)


def test_all_inline_tool_array_schemas_declare_items():
    import main
    from actions.computer_control import TOOL
    _walk_decl(main.TOOL_DECLARATIONS)
    _walk_decl(TOOL)
