"""Frame-level feature caching for performance optimization."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FrameCache:
    """Caches extracted frame features to avoid re-computation on re-runs."""

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize frame cache."""
        if cache_dir is None:
            cache_dir = str(Path.home() / ".cover_selector_cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.stats = {"hits": 0, "misses": 0, "writes": 0, "errors": 0}

    def _frame_hash(self, frame_bytes: bytes) -> str:
        """Compute MD5 hash of frame."""
        return hashlib.md5(frame_bytes).hexdigest()

    def _get_cache_path(self, frame_hash: str, config_hash: str) -> Path:
        """Get cache file path."""
        filename = f"{frame_hash}_{config_hash}.json"
        return self.cache_dir / filename

    def get(self, frame_bytes: bytes, config_hash: str) -> Optional[Dict]:
        """Retrieve cached frame features if available."""
        frame_hash = self._frame_hash(frame_bytes)
        cache_path = self._get_cache_path(frame_hash, config_hash)
        if not cache_path.exists():
            self.stats["misses"] += 1
            return None
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            self.stats["hits"] += 1
            return cached
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Cache corruption: {e}")
            self.stats["errors"] += 1
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None

    def put(self, frame_bytes: bytes, config_hash: str, features: Dict) -> bool:
        """Cache extracted frame features."""
        frame_hash = self._frame_hash(frame_bytes)
        cache_path = self._get_cache_path(frame_hash, config_hash)
        try:
            with open(cache_path, "w") as f:
                json.dump(features, f)
            self.stats["writes"] += 1
            return True
        except (TypeError, IOError) as e:
            logger.warning(f"Failed to cache: {e}")
            self.stats["errors"] += 1
            return False

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate_pct": hit_rate,
            "writes": self.stats["writes"],
            "errors": self.stats["errors"],
        }
