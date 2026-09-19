"""Tests for memory.memory_manager — long-term memory."""
import json
import pytest


def test_remember_and_search(tmp_path):
    """remember() stores a fact; search_memory() finds it."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    test_file.write_text(json.dumps(mm._empty_memory()), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        mm.remember("favorite_color", "blue", category="preferences")
        # search_memory splits by non-word chars; underscores are word chars
        # so "favorite_color" is one token. Search for a substring that appears
        # in the pretty-printed key ("favorite color").
        results = mm.search_memory("color")
        assert "blue" in results
    finally:
        mm.MEMORY_PATH = original_path


def test_forget(tmp_path):
    """forget() removes a stored key."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    test_file.write_text(json.dumps(mm._empty_memory()), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        mm.remember("temp_key", "temp_val", category="notes")
        msg = mm.forget("temp_key", category="notes")
        assert "Forgotten" in msg
        results = mm.search_memory("temp_key")
        assert "Nothing stored" in results or "temp_val" not in results
    finally:
        mm.MEMORY_PATH = original_path


def test_forget_nonexistent(tmp_path):
    """forget() on a missing key returns 'Not found'."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    test_file.write_text(json.dumps(mm._empty_memory()), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        msg = mm.forget("no_such_key", category="notes")
        assert "Not found" in msg
    finally:
        mm.MEMORY_PATH = original_path


def test_empty_memory_loads(tmp_path):
    """load_memory() returns a valid structure when no file exists."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "nonexistent.json"
    try:
        mm.MEMORY_PATH = test_file
        mem = mm.load_memory()
        assert isinstance(mem, dict)
        assert "identity" in mem
        assert "preferences" in mem
        assert "notes" in mem
    finally:
        mm.MEMORY_PATH = original_path


def test_load_memory_corrupt_file(tmp_path):
    """load_memory() returns empty structure on corrupt JSON."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "corrupt.json"
    test_file.write_text("{broken json!!!", encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        mem = mm.load_memory()
        assert isinstance(mem, dict)
        assert "identity" in mem
    finally:
        mm.MEMORY_PATH = original_path


def test_format_memory_for_prompt_empty():
    """format_memory_for_prompt returns empty string for None input."""
    import memory.memory_manager as mm

    assert mm.format_memory_for_prompt(None) == ""


def test_format_memory_for_prompt_identity(tmp_path):
    """Identity fields appear in prompt output."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    mem = mm._empty_memory()
    mem["identity"]["name"] = {"value": "Alice", "updated": "2025-01-01"}
    test_file.write_text(json.dumps(mem), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        loaded = mm.load_memory()
        prompt = mm.format_memory_for_prompt(loaded)
        assert "Alice" in prompt
    finally:
        mm.MEMORY_PATH = original_path


def test_search_empty_query(tmp_path):
    """search_memory('') returns a general overview."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    mem = mm._empty_memory()
    mem["notes"]["fact"] = {"value": "something", "updated": "2025-01-01"}
    test_file.write_text(json.dumps(mem), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        result = mm.search_memory("")
        assert "something" in result
    finally:
        mm.MEMORY_PATH = original_path


def test_search_no_match(tmp_path):
    """search_memory with unmatched query returns a 'nothing' message."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    mem = mm._empty_memory()
    test_file.write_text(json.dumps(mem), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        result = mm.search_memory("xyz_no_match")
        assert "Nothing stored" in result or "nothing" in result.lower()
    finally:
        mm.MEMORY_PATH = original_path


def test_all_entries_for_ui(tmp_path):
    """all_entries_for_ui returns a sorted list of dicts."""
    import memory.memory_manager as mm

    original_path = mm.MEMORY_PATH
    test_file = tmp_path / "long_term.json"
    mem = mm._empty_memory()
    mem["notes"]["a"] = {"value": "alpha", "updated": "2025-01-01"}
    mem["notes"]["b"] = {"value": "beta", "updated": "2025-06-01"}
    test_file.write_text(json.dumps(mem), encoding="utf-8")
    try:
        mm.MEMORY_PATH = test_file
        entries = mm.all_entries_for_ui()
        assert len(entries) >= 2
        assert entries[0]["updated"] >= entries[1]["updated"]
    finally:
        mm.MEMORY_PATH = original_path
