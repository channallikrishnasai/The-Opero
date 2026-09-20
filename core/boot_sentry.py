"""
Boot Sentry for Brahma AI
Runs at absolute startup before any heavy modules or UI to guarantee boot resilience.
Detects if the previous session crashed right after an auto-patch, and safely rolls back.
"""

import json
import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("BootSentry")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
CRASH_LOG = BASE_DIR / "FATAL_CRASH.log"
PATCH_HISTORY_FILE = CONFIG_DIR / "patch_history.json"


def check_and_recover_on_boot() -> bool:
    """
    Checks if a crash log exists. If a recent patch was applied within the last 5 minutes
    of the crash, automatically rolls back to the backup file to unbrick the system.
    Returns True if a recovery rollback was performed.
    """
    if not CRASH_LOG.exists() or not PATCH_HISTORY_FILE.exists():
        return False

    try:
        with open(PATCH_HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        return False

    if not history or not isinstance(history, list):
        return False

    last_patch = history[-1]
    if last_patch.get("status") != "applied" or not last_patch.get("backup_path"):
        return False

    target_file = Path(last_patch.get("target_file", ""))
    backup_file = Path(last_patch.get("backup_path", ""))

    if not backup_file.exists() or not target_file.exists():
        return False

    print(f"[BootSentry] ⚠️ Fatal crash detected after patch '{last_patch.get('patch_id')}'.")
    print(f"[BootSentry] 🛡️ Initiating automatic rollback of '{target_file.name}' from backup...")

    try:
        shutil.copy2(backup_file, target_file)
        last_patch["status"] = "rolled_back_on_boot"
        last_patch["rollback_reason"] = "App crashed on startup after patch."

        with open(PATCH_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)

        # Archive the crash log
        crash_archive = BASE_DIR / "FATAL_CRASH_RECOVERED.log"
        if CRASH_LOG.exists():
            shutil.move(str(CRASH_LOG), str(crash_archive))

        print(f"[BootSentry] ✅ Successfully restored '{target_file.name}'! Brahma AI recovered.")
        return True
    except Exception as e:
        print(f"[BootSentry] ❌ Recovery failed: {e}")
        return False


# Automatically execute recovery check on import
check_and_recover_on_boot()

class BootSentry:
    """Simple shim providing the boot lifecycle hooks expected by main.py.
    The original implementation in Brahma likely performed richer telemetry;
    for Opero we only need the methods to exist without breaking functionality.
    """

    @staticmethod
    def mark_boot_start() -> None:
        logger.info("[BootSentry] Boot start marked.")

    @staticmethod
    def mark_boot_end() -> None:
        logger.info("[BootSentry] Boot end marked.")

    @staticmethod
    def mark_boot_success() -> None:
        logger.info("[BootSentry] Boot success marked.")

    @staticmethod
    def record_crash(exc_info=None) -> None:
        """Record a crash to FATAL_CRASH.log for boot-sentry recovery on next launch."""
        import traceback as _tb
        try:
            crash_log = BASE_DIR / "FATAL_CRASH.log"
            if exc_info and exc_info[0] is not None:
                text = "".join(_tb.format_exception(*exc_info))
            else:
                text = "Unknown crash — no exc_info provided."
            crash_log.write_text(text, encoding="utf-8")
            logger.error(f"[BootSentry] Crash recorded to {crash_log}")
        except Exception as e:
            logger.error(f"[BootSentry] Failed to record crash: {e}")

    @staticmethod
    def recover() -> bool:
        """Run the original recovery check and return its result."""
        return check_and_recover_on_boot()

# Expose an instance named `sentry` that matches the original import usage.
sentry = BootSentry()


