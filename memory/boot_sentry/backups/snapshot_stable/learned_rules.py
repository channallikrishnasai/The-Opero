"""
learned_rules.py — OPERO Behavioral Learning Engine

Persists custom rules, preferences, and workflows learned during interactions.
Injects these rules into the system prompt dynamically.
Adapted from OPERO for OPERO.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("OPEROLearnedRules")

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
RULES_FILE = BASE_DIR / "memory" / "learned_rules.json"

class LearnedRules:
    def __init__(self):
        RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        if not RULES_FILE.exists():
            return {}
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_rules(self):
        try:
            with open(RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            logger.error(f"[LearnedRules] Could not save rules: {e}")

    def add_rule(self, key: str, instruction: str) -> str:
        """Adds or updates a behavioral rule."""
        key = key.strip().lower()
        self.rules[key] = {
            "instruction": instruction.strip(),
            "updated_at": datetime.now().isoformat()
        }
        self._save_rules()
        logger.info(f"[LearnedRules] Rule '{key}' updated.")
        return f"Rule '{key}' saved successfully."

    def remove_rule(self, key: str) -> str:
        """Removes a rule by key."""
        key = key.strip().lower()
        if key in self.rules:
            del self.rules[key]
            self._save_rules()
            logger.info(f"[LearnedRules] Rule '{key}' removed.")
            return f"Rule '{key}' removed."
        return f"Rule '{key}' not found."

    def get_rules_text(self) -> str:
        """Formats the active rules for injection into the system prompt."""
        if not self.rules:
            return ""
            
        lines = ["\n# USER PREFERENCES & LEARNED RULES\n"]
        lines.append("You MUST follow these rules dynamically learned from the user:\n")
        
        for key, data in self.rules.items():
            lines.append(f"- [{key.upper()}]: {data['instruction']}")
            
        return "\n".join(lines)

    def get_all(self) -> dict:
        return self.rules

# Global instance
rules_engine = LearnedRules()
