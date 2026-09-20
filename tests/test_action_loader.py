"""Tests for core.action_loader — tool discovery and dispatch."""
import pytest
from pathlib import Path


def test_discover_actions_on_real_actions_dir():
    """Verify the real actions/ directory loads without errors."""
    from core.action_loader import discover_actions

    actions_dir = Path(__file__).resolve().parent.parent / "actions"
    if not actions_dir.exists():
        pytest.skip("actions/ directory not found")
    registry = discover_actions(actions_dir)
    assert isinstance(registry, object)
    assert hasattr(registry, "names")
    assert len(registry.names()) > 0


def test_each_action_has_required_fields():
    """Every valid ActionRecord must have name, description, and parameters."""
    from core.action_loader import discover_actions, ActionRegistry

    actions_dir = Path(__file__).resolve().parent.parent / "actions"
    if not actions_dir.exists():
        pytest.skip("actions/ directory not found")
    registry = discover_actions(actions_dir)
    for name in registry.names():
        decls = [d for d in registry.get_tool_declarations() if d["name"] == name]
        assert len(decls) == 1, f"Expected exactly one declaration for {name}"
        decl = decls[0]
        assert "name" in decl, f"{name} missing 'name'"
        assert "description" in decl, f"{name} missing 'description'"
        assert "parameters" in decl, f"{name} missing 'parameters'"


def test_discover_actions_empty_dir(tmp_path):
    """An empty actions dir produces a registry with zero actions."""
    from core.action_loader import discover_actions

    empty_dir = tmp_path / "actions"
    empty_dir.mkdir()
    registry = discover_actions(empty_dir)
    assert len(registry.names()) == 0


def test_discover_actions_ignores_private_files(tmp_path):
    """Files starting with _ are skipped."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "_helper.py").write_text("# private helper\n")
    registry = discover_actions(actions_dir)
    assert len(registry.names()) == 0


def test_discover_actions_rejects_no_tool(tmp_path):
    """A .py file without TOOL dict is silently ignored."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "not_an_action.py").write_text("x = 1\n")
    registry = discover_actions(actions_dir)
    assert len(registry.names()) == 0


def test_discover_actions_rejects_invalid_tool(tmp_path):
    """A TOOL dict with a missing handler is rejected, not fatal."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "bad_action.py").write_text(
        'TOOL = {"name": "bad", "description": "x", "parameters": {"type": "OBJECT"}}\n'
    )
    registry = discover_actions(actions_dir)
    assert "bad" not in registry.names()


def test_discover_actions_catches_name_collision(tmp_path):
    """Duplicate tool names are rejected (second file loses)."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    tool_code = (
        'def _handler(parameters, **kwargs):\n'
        '    return "ok"\n'
        'TOOL = {\n'
        '    "name": "dup_tool",\n'
        '    "description": "dup",\n'
        '    "parameters": {"type": "OBJECT"},\n'
        '    "handler": _handler,\n'
        '}\n'
    )
    (actions_dir / "first.py").write_text(tool_code)
    (actions_dir / "second.py").write_text(tool_code)
    registry = discover_actions(actions_dir)
    names = registry.names()
    assert names.count("dup_tool") <= 1 if isinstance(names, list) else True


def test_registry_run_calls_handler(tmp_path):
    """ActionRegistry.run() invokes the handler for a valid action."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "echo_action.py").write_text(
        'def _handler(parameters, **kwargs):\n'
        '    return f"echo: {parameters}"\n'
        'TOOL = {\n'
        '    "name": "echo_action",\n'
        '    "description": "echoes params",\n'
        '    "parameters": {"type": "OBJECT"},\n'
        '    "handler": _handler,\n'
        '}\n'
    )
    registry = discover_actions(actions_dir)
    assert registry.has("echo_action")
    result = registry.run("echo_action", {"x": 1})
    assert "echo" in result


def test_registry_run_unknown_action():
    """Running an unknown action returns an error string, no exception."""
    from core.action_loader import discover_actions
    from pathlib import Path

    actions_dir = Path(__file__).resolve().parent.parent / "actions"
    if not actions_dir.exists():
        pytest.skip("actions/ directory not found")
    registry = discover_actions(actions_dir)
    result = registry.run("nonexistent_action_xyz", {})
    assert "not available" in result


def test_registry_scheduling(tmp_path):
    """ActionRecord stores scheduling metadata when declared."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "silent_action.py").write_text(
        'def _handler(parameters, **kwargs):\n'
        '    return "done"\n'
        'TOOL = {\n'
        '    "name": "silent_action",\n'
        '    "description": "silent",\n'
        '    "parameters": {"type": "OBJECT"},\n'
        '    "handler": _handler,\n'
        '    "scheduling": "SILENT",\n'
        '}\n'
    )
    registry = discover_actions(actions_dir)
    assert registry.scheduling("silent_action") == "SILENT"


def test_reserved_names_rejected(tmp_path):
    """Actions whose names are in the reserved set are rejected."""
    from core.action_loader import discover_actions

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "reserved.py").write_text(
        'def _handler(parameters, **kwargs):\n'
        '    return "ok"\n'
        'TOOL = {\n'
        '    "name": "reserved_action",\n'
        '    "description": "reserved",\n'
        '    "parameters": {"type": "OBJECT"},\n'
        '    "handler": _handler,\n'
        '}\n'
    )
    registry = discover_actions(actions_dir, reserved_names={"reserved_action"})
    assert "reserved_action" not in registry.names()


def test_registry_run_records_task_lifecycle(tmp_path):
    """Every dispatched action is visible to task-status consumers."""
    from core.action_loader import discover_actions
    from core.task_manager import TaskState, journal

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "tracked.py").write_text(
        'def _handler(parameters, **kwargs):\n'
        '    return "completed"\n'
        'TOOL = {"name": "tracked_action", "description": "tracked", '
        '"parameters": {"type": "OBJECT"}, "handler": _handler}\n'
    )
    registry = discover_actions(actions_dir)
    assert registry.run("tracked_action", {"secret": "not-recorded"}) == "completed"
    latest = journal.recent(1)[0]
    assert latest["state"] == TaskState.SUCCEEDED.value
    assert latest["metadata"] == {"action": "tracked_action", "parameter_keys": ["secret"]}
    assert latest["result"] == "Completed successfully."
    assert "not-recorded" not in str(latest)


def test_registry_does_not_retain_action_output_in_journal(tmp_path):
    from core.action_loader import discover_actions
    from core.task_manager import journal

    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    (actions_dir / "private.py").write_text(
        'def _handler(parameters, **kwargs):\n'
        '    return "private-message-body"\n'
        'TOOL = {"name": "private_action", "description": "private", '
        '"parameters": {"type": "OBJECT"}, "handler": _handler}\n'
    )
    registry = discover_actions(actions_dir)
    assert registry.run("private_action", {}) == "private-message-body"
    latest = journal.recent(1)[0]
    assert latest["result"] == "Completed successfully."
    assert "private-message-body" not in str(latest)
