"""Session and history management for Web UI."""

import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions and upload history."""

    def __init__(self, history_dir: Optional[str] = None):
        """Initialize session manager.

        Args:
            history_dir: Directory to store history. Default: ~/.cover_selector_history
        """
        if history_dir is None:
            history_dir = str(Path.home() / ".cover_selector_history")

        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.sessions = {}  # In-memory session state
        self.sessions_lock = threading.RLock()  # Thread-safe access

    def create_session(self, video_filename: str) -> str:
        """Create a new session for video processing."""
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "video_filename": video_filename,
            "created_at": datetime.now().isoformat(),
            "status": "uploading",
            "progress": 0,
            "current_stage": None,
            "total_frames": 0,
            "processed_frames": 0,
            "result": None,
            "error": None,
        }
        with self.sessions_lock:
            self.sessions[session_id] = session
        return session_id

    def update_progress(
        self,
        session_id: str,
        stage: str,
        progress: int = 0,
        total_frames: int = 0,
        processed_frames: int = 0,
    ) -> bool:
        """Update session progress."""
        with self.sessions_lock:
            if session_id not in self.sessions:
                return False
            session = self.sessions[session_id]
            session["status"] = "processing"
            session["current_stage"] = stage
            session["progress"] = progress
            session["total_frames"] = total_frames
            session["processed_frames"] = processed_frames
        return True

    def complete_session(self, session_id: str, result: Dict, error: Optional[str] = None) -> bool:
        """Mark session as completed."""
        with self.sessions_lock:
            if session_id not in self.sessions:
                return False
            session = self.sessions[session_id]
            session["status"] = "failed" if error else "completed"
            session["result"] = result
            session["error"] = error
            session["completed_at"] = datetime.now().isoformat()
        self._save_to_history(session)
        return True

    def get_progress(self, session_id: str) -> Optional[Dict]:
        """Get current progress for session."""
        with self.sessions_lock:
            return self.sessions.get(session_id)

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get upload history."""
        history = []
        history_files = sorted(
            self.history_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:limit]
        for history_file in history_files:
            try:
                # Security: prevent symlink/TOCTOU attacks
                if history_file.is_symlink():
                    logger.warning(f"Skipping symlink: {history_file}")
                    continue
                if history_file.parent != self.history_dir:
                    logger.warning(f"Skipping file outside history dir: {history_file}")
                    continue
                with open(history_file, "r") as f:
                    entry = json.load(f)
                    history.append(entry)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read history file {history_file}: {e}")
        return history

    def _save_to_history(self, session: Dict) -> bool:
        """Save session to history file."""
        try:
            history_file = self.history_dir / f"{session['session_id']}.json"
            with open(history_file, "w") as f:
                json.dump(session, f, indent=2)
            return True
        except IOError as e:
            logger.warning(f"Failed to save history: {e}")
            return False
