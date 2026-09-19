"""Tests for memory.config_manager — settings persistence."""
import json
import os
import pytest


def test_config_roundtrip(tmp_path):
    """Write and read back a config value via save_api_keys / load_api_keys."""
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_api_keys("test-api-key-12345678")
        keys = cm.load_api_keys()
        assert keys.get("gemini_api_key") == "test-api-key-12345678"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_get_gemini_key(tmp_path):
    """get_gemini_key returns the stored key."""
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_api_keys("abcdef1234567890")
        assert cm.get_gemini_key() == "abcdef1234567890"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_get_gemini_key_missing(tmp_path):
    """get_gemini_key returns None when no config exists."""
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.get_gemini_key() is None
    finally:
        cm.CONFIG_FILE = original_config_file


def test_is_configured(tmp_path):
    """is_configured returns True only when a long enough key is stored."""
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.is_configured() is False
        cm.save_api_keys("short")
        assert cm.is_configured() is False
        cm.save_api_keys("this-key-is-long-enough")
        assert cm.is_configured() is True
    finally:
        cm.CONFIG_FILE = original_config_file


def test_assistant_name_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_assistant_config("ARIA", "Bob")
        assert cm.get_assistant_name() == "ARIA"
        assert cm.get_user_name() == "Bob"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_assistant_name_default(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.get_assistant_name() == "OPERO"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_voice_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_voice("Kore")
        assert cm.get_voice() == "Kore"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_voice_invalid_falls_back_to_default(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_voice("NonExistentVoice")
        assert cm.get_voice() == cm.DEFAULT_VOICE
    finally:
        cm.CONFIG_FILE = original_config_file


def test_voice_engine_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_voice_engine("assemblyai")
        assert cm.get_voice_engine() == "assemblyai"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_voice_engine_invalid_falls_back(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_voice_engine("bogus")
        assert cm.get_voice_engine() == cm.DEFAULT_VOICE_ENGINE
    finally:
        cm.CONFIG_FILE = original_config_file


def test_theme_mode_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_theme_mode("light")
        assert cm.get_theme_mode() == "light"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_theme_mode_invalid_falls_back(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_theme_mode("rainbow")
        assert cm.get_theme_mode() == "dark"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_hud_style_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_hud_style("orb")
        assert cm.get_hud_style() == "orb"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_hud_style_invalid_falls_back(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_hud_style("neon")
        assert cm.get_hud_style() == "face"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_wake_word_enabled_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.get_wake_word_enabled() is False
        cm.save_wake_word_enabled(True)
        assert cm.get_wake_word_enabled() is True
    finally:
        cm.CONFIG_FILE = original_config_file


def test_push_to_talk_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.get_push_to_talk_enabled() is False
        cm.save_push_to_talk_enabled(True)
        assert cm.get_push_to_talk_enabled() is True
    finally:
        cm.CONFIG_FILE = original_config_file


def test_plugin_config_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        cm.save_plugin_config("my_plugin", {"token": "abc123", "debug": True})
        assert cm.get_plugin_setting("my_plugin", "token") == "abc123"
        assert cm.get_plugin_setting("my_plugin", "debug") is True
        assert cm.get_plugin_setting("my_plugin", "missing", "default") == "default"
    finally:
        cm.CONFIG_FILE = original_config_file


def test_plugin_enabled_default_true(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.get_plugin_enabled("some_plugin") is True
    finally:
        cm.CONFIG_FILE = original_config_file


def test_brief_enabled_roundtrip(tmp_path):
    import memory.config_manager as cm

    original_config_file = cm.CONFIG_FILE
    test_cfg = tmp_path / "api_keys.json"
    try:
        cm.CONFIG_FILE = test_cfg
        assert cm.get_brief_enabled() is True
        cm.save_brief_enabled(False)
        assert cm.get_brief_enabled() is False
    finally:
        cm.CONFIG_FILE = original_config_file
