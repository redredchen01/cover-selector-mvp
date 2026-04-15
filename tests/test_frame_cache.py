"""Tests for frame-level caching system."""

import tempfile
from pathlib import Path

import pytest

from cover_selector.core.frame_cache import FrameCache


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def cache(temp_cache_dir):
    """Frame cache instance with temporary directory."""
    return FrameCache(cache_dir=temp_cache_dir)


def test_frame_cache_init(temp_cache_dir):
    """Test FrameCache initialization."""
    cache = FrameCache(cache_dir=temp_cache_dir)
    assert cache.cache_dir.exists()
    assert cache.stats["hits"] == 0


def test_frame_cache_default_dir():
    """Test default cache directory creation."""
    cache = FrameCache()
    assert cache.cache_dir.exists()


def test_cache_miss_on_empty(cache):
    """Test cache miss when no entry exists."""
    frame_bytes = b"test_frame_data"
    config_hash = "config_123"

    result = cache.get(frame_bytes, config_hash)

    assert result is None
    assert cache.stats["misses"] == 1


def test_cache_put_and_get(cache):
    """Test happy path: put and retrieve cached features."""
    frame_bytes = b"test_frame_data"
    config_hash = "config_123"
    features = {
        "blur_score": 75.0,
        "brightness_score": 50.0,
        "face_count": 1,
    }

    # Put features
    success = cache.put(frame_bytes, config_hash, features)
    assert success is True
    assert cache.stats["writes"] == 1

    # Retrieve features
    cached = cache.get(frame_bytes, config_hash)
    assert cached == features
    assert cache.stats["hits"] == 1


def test_cache_invalidation_on_config_change(cache):
    """Test cache invalidation when config hash changes."""
    frame_bytes = b"test_frame_data"
    features = {"blur_score": 75.0}

    # Cache with config v1
    cache.put(frame_bytes, "config_v1", features)
    assert cache.get(frame_bytes, "config_v1") == features

    # Different config v2 should not hit cache
    result = cache.get(frame_bytes, "config_v2")
    assert result is None
    assert cache.stats["hits"] == 1  # Only v1 hit
    assert cache.stats["misses"] == 1  # v2 miss


def test_cache_different_frames_different_cache(cache):
    """Test that different frames have separate cache entries."""
    features1 = {"blur_score": 75.0}
    features2 = {"blur_score": 50.0}

    # Cache two different frames
    cache.put(b"frame_1", "config", features1)
    cache.put(b"frame_2", "config", features2)

    # Retrieve separately
    assert cache.get(b"frame_1", "config") == features1
    assert cache.get(b"frame_2", "config") == features2

    assert cache.stats["hits"] == 2


def test_cache_clear(cache):
    """Test clearing all cache entries."""
    cache.put(b"frame_1", "config", {"blur_score": 75.0})
    cache.put(b"frame_2", "config", {"blur_score": 50.0})

    assert cache.stats["writes"] == 2

    # Clear
    cleared = cache.clear()
    assert cleared == 2

    # Verify cleared
    assert cache.get(b"frame_1", "config") is None
    assert cache.stats["misses"] == 1


def test_cache_stats(cache):
    """Test cache statistics."""
    cache.put(b"frame_1", "config", {"blur_score": 75.0})
    cache.get(b"frame_1", "config")  # Hit
    cache.get(b"frame_2", "config")  # Miss

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["writes"] == 1
    assert stats["hit_rate_pct"] == 50.0


def test_cache_reset_stats(cache):
    """Test resetting cache statistics."""
    cache.put(b"frame_1", "config", {"blur_score": 75.0})

    assert cache.stats["writes"] == 1

    cache.reset_stats()

    assert cache.stats["writes"] == 0
    assert cache.stats["hits"] == 0


def test_cache_corruption_recovery(cache):
    """Test graceful handling of corrupted cache files."""
    cache.put(b"frame_1", "config", {"blur_score": 75.0})

    # Corrupt the cache file
    frame_hash = "5b6e7f8a8e7e6f7f7e7e7e7e"  # Dummy hash
    cache_path = cache.cache_dir / f"{frame_hash}_config.json"

    # Find actual cache file
    actual_file = list(cache.cache_dir.glob("*.json"))[0]

    # Write invalid JSON
    with open(actual_file, "w") as f:
        f.write("invalid json {")

    # Try to retrieve - should handle gracefully
    result = cache.get(b"frame_1", "config")
    assert result is None
    assert cache.stats["errors"] == 1

    # File should be deleted
    assert not actual_file.exists()


def test_cache_with_complex_features(cache):
    """Test caching complex feature structures."""
    features = {
        "blur_score": 75.0,
        "face_landmarks_json": '{"x": 0.5, "y": 0.5}',
        "final_score_breakdown": {
            "blur": 0.8,
            "brightness": 0.6,
            "face": 0.7,
        },
    }

    cache.put(b"frame_1", "config", features)
    cached = cache.get(b"frame_1", "config")

    assert cached == features
    assert cached["face_landmarks_json"] == '{"x": 0.5, "y": 0.5}'


def test_cache_empty_features(cache):
    """Test caching empty features dict."""
    cache.put(b"frame_1", "config", {})
    cached = cache.get(b"frame_1", "config")

    assert cached == {}


def test_cache_large_features(cache):
    """Test caching large feature structures."""
    # Create large features dict
    landmarks = [{"x": i * 0.01, "y": i * 0.01, "z": 0.0} for i in range(468)]
    features = {
        "face_landmarks_json": str(landmarks),
        "blur_score": 75.0,
    }

    cache.put(b"frame_1", "config", features)
    cached = cache.get(b"frame_1", "config")

    assert len(cached["face_landmarks_json"]) > 1000
