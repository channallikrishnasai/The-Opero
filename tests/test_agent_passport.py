import re
from pathlib import Path

import pytest

from actions.agent_export import ClaudeCodeAdapter, export_checkpoint


ROOT = Path(__file__).resolve().parent.parent


def test_agent_passport_metadata_and_responsibilities():
    metadata = (ROOT / "agent.yaml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^spec_version:\s*0\.1\.0\s*$", metadata)
    assert re.search(r"(?m)^name:\s*[a-z][a-z0-9-]*\s*$", metadata)
    assert "skills: []" in metadata
    for tool in ("Bash", "FileRead", "FileWrite", "FileEdit", "Glob", "Grep"):
        assert f"name: {tool}" in metadata
    assert "## " in (ROOT / "SOUL.md").read_text(encoding="utf-8")

    for filename in ("DUTIES.md", "AGENTS.md"):
        for line in (ROOT / filename).read_text(encoding="utf-8").splitlines():
            assert not ("Maker" in line and "Checker" in line)


def test_explainability_has_two_sentences_per_required_heading():
    text = (ROOT / "EXPLAINABILITY.md").read_text(encoding="utf-8")
    required = (
        "Decision, reasoning, and how it decides",
        "Data source, input, and data used",
        "Limitation, constraint, and known issue",
    )
    for heading in required:
        start = text.index(f"## {heading}") + len(f"## {heading}")
        end = text.find("\n## ", start)
        section = text[start:] if end == -1 else text[start:end]
        assert len(re.findall(r"[.!?](?:\s|$)", section.strip())) >= 2


def test_claude_code_export_creates_passport_checkpoint(tmp_path):
    outputs = export_checkpoint(tmp_path, source_root=ROOT)

    assert len(outputs) == 1
    assert outputs[0] == tmp_path / "claude-code" / "CLAUDE.md"
    checkpoint = outputs[0].read_text(encoding="utf-8")
    assert checkpoint.startswith("# opero-desktop-operator")
    assert "## Decision, reasoning, and how it decides" in checkpoint
    assert "## Data source, input, and data used" in checkpoint
    assert "## Limitation, constraint, and known issue" in checkpoint


def test_export_checkpoint_succeeds_when_one_independent_adapter_fails(tmp_path, caplog):
    class FailingAdapter:
        name = "unavailable"

        def export(self, source_root, destination):
            raise OSError("adapter unavailable")

    outputs = export_checkpoint(
        tmp_path,
        source_root=ROOT,
        adapters=(FailingAdapter(), ClaudeCodeAdapter()),
    )

    assert outputs == [tmp_path / "claude-code" / "CLAUDE.md"]
    assert "adapter unavailable" in caplog.text


def test_export_checkpoint_reports_failure_when_no_adapter_succeeds(tmp_path):
    class FailingAdapter:
        name = "unavailable"

        def export(self, source_root, destination):
            raise OSError("adapter unavailable")

    with pytest.raises(RuntimeError, match="unavailable: adapter unavailable"):
        export_checkpoint(tmp_path, source_root=ROOT, adapters=(FailingAdapter(),))
