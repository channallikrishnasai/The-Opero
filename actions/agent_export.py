"""Export OPERO's agent passport as a Claude Code project instruction file."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parent.parent
PASSPORT_FILES = ("SOUL.md", "DUTIES.md", "EXPLAINABILITY.md")


class ExportAdapter(Protocol):
    name: str

    def export(self, source_root: Path, destination: Path) -> Path:
        """Write this adapter's checkpoint and return its artifact path."""


class ClaudeCodeAdapter:
    """Create Claude Code project instructions from the repository passport."""

    name = "claude-code"

    def export(self, source_root: Path, destination: Path) -> Path:
        metadata = (source_root / "agent.yaml").read_text(encoding="utf-8")
        match = re.search(r"(?m)^name:\s*([a-z][a-z0-9-]*)\s*$", metadata)
        if match is None:
            raise ValueError("agent.yaml must define a lowercase hyphenated agent name")

        sections = []
        for filename in PASSPORT_FILES:
            path = source_root / filename
            if not path.is_file():
                raise FileNotFoundError(f"Required passport file is missing: {path}")
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                raise ValueError(f"Required passport file is empty: {path}")
            sections.append(content)

        output = destination / self.name / "CLAUDE.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            f"# {match.group(1)}\n\n" + "\n\n".join(sections) + "\n",
            encoding="utf-8",
        )
        return output


def export_checkpoint(
    destination: str | Path,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    adapters: tuple[ExportAdapter, ...] | None = None,
) -> list[Path]:
    """Run export adapters independently; succeed when any adapter exports."""
    target = Path(destination)
    source = Path(source_root)
    configured_adapters = adapters if adapters is not None else (ClaudeCodeAdapter(),)
    successes = []
    failures = []

    for adapter in configured_adapters:
        try:
            successes.append(adapter.export(source, target))
        except Exception as exc:
            failures.append(f"{adapter.name}: {exc}")
            logger.warning("Agent export adapter %s failed: %s", adapter.name, exc)

    if not successes:
        details = "; ".join(failures) if failures else "no adapters were configured"
        raise RuntimeError(f"No agent export adapter succeeded: {details}")
    return successes
