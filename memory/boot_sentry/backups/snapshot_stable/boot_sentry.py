"""
boot_sentry.py — OPERO Anti-Brick & Recovery System

Monitors core stability and intercepts fatal crashes.
If OPERO fails to boot or encounters repeated fatal errors,
Boot Sentry rolls back to the last known stable state.
Adapted from OPERO for OPERO.
"""

import json
import logging
import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("OPEROBootSentry")

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
STATE_DIR = BASE_DIR / "memory" / "boot_sentry"
BACKUP_DIR = STATE_DIR / "backups"
STATE_FILE = STATE_DIR / "boot_state.json"

# Max consecutive crashes before triggering rollback
MAX_CRASHES = 3

class BootSentry:
    def __init__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self):
        if not STATE_FILE.exists():
            return {"crashes": 0, "last_boot": None, "last_crash": None, "stable": True}
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"crashes": 0, "last_boot": None, "last_crash": None, "stable": True}

    def _save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"[BootSentry] Could not save state: {e}")

    def mark_boot_start(self):
        """Called at the beginning of the application lifecycle."""
        self.state["last_boot"] = datetime.now().isoformat()
        self.state["stable"] = False
        self._save_state()
        logger.info("[BootSentry] Boot sequence started.")
        
        if self.state.get("crashes", 0) >= MAX_CRASHES:
            logger.warning("[BootSentry] Consecutive crashes exceeded threshold. Initiating rollback...")
            self.rollback()

    def mark_boot_success(self):
        """Called when the application successfully starts and stabilizes."""
        self.state["crashes"] = 0
        self.state["stable"] = True
        self._save_state()
        self.create_snapshot()
        logger.info("[BootSentry] Boot successful. State marked as stable.")

    def record_crash(self, exc_info=None):
        """Records a fatal crash."""
        self.state["crashes"] = self.state.get("crashes", 0) + 1
        self.state["last_crash"] = datetime.now().isoformat()
        self.state["stable"] = False
        self._save_state()
        
        err_msg = ""
        if exc_info:
            err_msg = "".join(traceback.format_exception(*exc_info))
            
        logger.error(f"[BootSentry] FATAL CRASH recorded ({self.state['crashes']}/{MAX_CRASHES}).\n{err_msg}")
        
    def create_snapshot(self):
        """Creates a snapshot of critical core files for rollback."""
        try:
            core_dir = BASE_DIR / "core"
            if not core_dir.exists():
                return
                
            snapshot_name = f"snapshot_stable"
            snapshot_path = BACKUP_DIR / snapshot_name
            
            # Simple sync
            if snapshot_path.exists():
                shutil.rmtree(snapshot_path, ignore_errors=True)
                
            shutil.copytree(core_dir, snapshot_path, dirs_exist_ok=True)
            logger.debug("[BootSentry] Snapshot updated.")
        except Exception as e:
            logger.warning(f"[BootSentry] Snapshot failed: {e}")

    def rollback(self):
        """Rolls back core files to the last known stable snapshot."""
        snapshot_path = BACKUP_DIR / "snapshot_stable"
        if not snapshot_path.exists():
            logger.error("[BootSentry] Rollback failed: No stable snapshot found.")
            return False
            
        try:
            core_dir = BASE_DIR / "core"
            if core_dir.exists():
                # Backup current broken state just in case
                broken_backup = BACKUP_DIR / f"broken_{int(datetime.now().timestamp())}"
                shutil.move(str(core_dir), str(broken_backup))
                
            shutil.copytree(snapshot_path, core_dir)
            logger.info("[BootSentry] ROLLBACK SUCCESSFUL. Core restored to stable state.")
            
            # Reset crash counter after rollback
            self.state["crashes"] = 0
            self.state["stable"] = True
            self._save_state()
            return True
        except Exception as e:
            logger.error(f"[BootSentry] ROLLBACK FAILED: {e}")
            return False

# Global instance
sentry = BootSentry()
