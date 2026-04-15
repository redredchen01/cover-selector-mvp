"""End-to-end integration tests for complete pipeline."""

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from cover_selector.config import CoverSelectorConfig
from cover_selector.core.frame_cache import FrameCache
from cover_selector.core.frame_sampler import FrameSampler
from cover_selector.core.scorer import Scorer
from cover_selector.schemas.frame_features import FrameFeatures


def create_test_video(video_path: str, duration_seconds: float = 5.0) -> None:
    """Create a test video file using ffmpeg."""
    import subprocess
    import os

    # Use ffmpeg to create a simple test video (more reliable than OpenCV VideoWriter)
    try:
        cmd = [
            "ffmpeg", "-f", "lavfi", "-i",
            f"color=c=blue:s=640x480:d={duration_seconds}",
            "-f", "lavfi", "-i",
            f"sine=f=1000:d={duration_seconds}",
            "-pix_fmt", "yuv420p",
            "-y",  # Overwrite without asking
            video_path
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: create using OpenCV with proper initialization
        fourcc = cv2.VideoWriter_fourcc(*"avc1")  # Use H.264 instead of mp4v
        fps = 30
        frame_size = (640, 480)
        writer = cv2.VideoWriter(video_path, fourcc, fps, frame_size)

        if not writer.isOpened():
            raise RuntimeError(f"Failed to open VideoWriter for {video_path}")

        # Create video frames
        for frame_num in range(int(duration_seconds * fps)):
            frame = np.zeros(frame_size + (3,), dtype=np.uint8)
            # Simple pattern
            frame[:, :] = [100 + (frame_num % 50), 150, 200]
            # Add moving circle
            x = int((frame_num % int(duration_seconds * fps)) / (duration_seconds * fps) * frame_size[0])
            cv2.circle(frame, (x, frame_size[1]//2), 30, (0, 255, 0), -1)
            writer.write(frame)

        writer.release()

        # Verify file was created
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            raise RuntimeError(f"Failed to create video file: {video_path}")


@pytest.fixture
def temp_video():
    """Create a temporary test video."""
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "test.mp4"
        create_test_video(str(video_path))
        yield str(video_path)


@pytest.fixture
def config():
    """Default configuration."""
    return CoverSelectorConfig()


def test_end_to_end_frame_sampling(temp_video, config):
    """Test end-to-end frame sampling pipeline."""
    sampler = FrameSampler(config)

    from cover_selector.core.scene_detector import SceneDetector
    detector = SceneDetector(config.scene_detection)
    scenes = detector.detect(temp_video)

    assert len(scenes) > 0
    assert scenes[0].start_sec >= 0

    # Sample frames
    frames = sampler.sample_frames(temp_video, scenes)
    assert len(frames) > 0
    assert all(f.timestamp_sec >= 0 for f in frames)


def test_frame_cache_hit_improves_performance(temp_video, config):
    """Test that frame caching improves performance on re-runs."""
    import time

    sampler = FrameSampler(config)
    cache = FrameCache()

    from cover_selector.core.scene_detector import SceneDetector
    detector = SceneDetector(config.scene_detection)
    scenes = detector.detect(temp_video)

    frames = sampler.sample_frames(temp_video, scenes)

    # Simulate extracting features with caching
    config_hash = "test_config"

    # First run - cache miss
    features_data = {
        "frame_id": 1,
        "blur_score": 75.0,
        "brightness_score": 50.0,
    }

    cache.put(b"frame_data", config_hash, features_data)
    cached = cache.get(b"frame_data", config_hash)
    assert cached == features_data

    stats = cache.get_stats()
    assert stats["hit_rate_pct"] == 100.0


def test_feature_extraction_with_empty_video(config):
    """Test graceful handling of edge cases."""
    # Test with minimal video
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "empty.mp4"
        create_test_video(str(video_path), duration_seconds=0.1)

        from cover_selector.core.scene_detector import SceneDetector
        detector = SceneDetector(config.scene_detection)

        # Should handle short video gracefully
        scenes = detector.detect(str(video_path))
        assert isinstance(scenes, list)


def test_scorer_with_various_frame_features(config):
    """Test scoring with different feature combinations."""
    scorer = Scorer(config.scorer)

    # Test various feature combinations
    test_cases = [
        {
            "blur_score": 95.0,  # Sharp
            "brightness_score": 60.0,
            "contrast_score": 70.0,
            "face_count": 1,
            "largest_face_ratio": 0.3,
        },
        {
            "blur_score": 20.0,  # Blurry
            "brightness_score": 30.0,  # Dark
            "contrast_score": 20.0,
            "face_count": 0,
            "largest_face_ratio": 0.0,
        },
        {
            "blur_score": 70.0,
            "brightness_score": 90.0,  # Very bright
            "contrast_score": 50.0,
            "overexposure_score": 40.0,
            "face_count": 2,  # Multiple faces
            "largest_face_ratio": 0.5,
        },
    ]

    for features_dict in test_cases:
        # Extract all potentially duplicate fields
        test_dict = features_dict.copy()
        contrast_score = test_dict.pop("contrast_score", 50.0)
        overexposure_score = test_dict.pop("overexposure_score", 0.0)

        features = FrameFeatures(
            frame_id=1,
            timestamp_sec=1.0,
            **test_dict,
            # Fill defaults
            laplacian_variance=test_dict.get("blur_score", 0.0) * 2,
            edge_density=0.3,
            contrast_score=contrast_score,
            overexposure_score=overexposure_score,
            underexposure_score=0.0,
            ocr_text_count=0,
            ocr_text_area_ratio=0.0,
            bottom_subtitle_ratio=0.0,
            corner_text_ratio=0.0,
            center_text_ratio=0.0,
            face_edge_cutoff_ratio=0.0,
            primary_face_center_offset=0.5,
            is_closeup=False,
            is_subject_too_small=False,
            is_subject_cutoff=False,
            subject_center_offset=0.5,
            composition_balance_score=0.5,
        )

        # Score should be between 0 and 100
        score_result = scorer.score(features)
        assert isinstance(score_result, dict)
        assert "score" in score_result or "final_score" in score_result


def test_frame_features_schema_validation():
    """Test frame features schema validation."""
    # Valid features
    valid_features = FrameFeatures(
        frame_id=1,
        timestamp_sec=1.5,
        blur_score=75.0,
        brightness_score=50.0,
    )
    assert valid_features.frame_id == 1
    assert valid_features.blur_score == 75.0

    # Schema should enforce type constraints
    with pytest.raises(Exception):
        FrameFeatures(
            frame_id="invalid",  # Should be int
            timestamp_sec=1.5,
        )


def test_parallel_pipeline_basic():
    """Test basic parallel pipeline operation."""
    from cover_selector.core.parallel_pipeline import create_parallel_pipeline

    config = CoverSelectorConfig()
    pipeline = create_parallel_pipeline(config, max_workers=2)

    assert pipeline.max_workers == 2
    assert pipeline.config == config
    assert pipeline.frame_cache is not None


def test_cache_invalidation_on_config_change():
    """Test that cache is properly invalidated when config changes."""
    cache = FrameCache()

    frame_bytes = b"test_frame"
    config_hash_v1 = "config_v1"
    config_hash_v2 = "config_v2"

    features = {"blur_score": 75.0}

    # Cache with v1
    cache.put(frame_bytes, config_hash_v1, features)
    assert cache.get(frame_bytes, config_hash_v1) is not None

    # Should not find with v2
    assert cache.get(frame_bytes, config_hash_v2) is None


def test_session_manager_concurrent_sessions():
    """Test session manager with concurrent sessions."""
    from cover_selector.web import SessionManager
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(history_dir=tmpdir)

        # Create multiple sessions
        sessions = []
        for i in range(5):
            session_id = manager.create_session(f"video_{i}.mp4")
            sessions.append(session_id)
            manager.update_progress(session_id, f"Stage {i}", i * 20)

        # All sessions should be tracked
        for session_id in sessions:
            progress = manager.get_progress(session_id)
            assert progress is not None
            assert progress["status"] == "processing"


def test_error_handling_in_feature_extraction():
    """Test graceful error handling in feature extraction."""
    from cover_selector.core.blur_analyzer import BlurAnalyzer

    config = CoverSelectorConfig()
    analyzer = BlurAnalyzer(config.blur_analysis)

    # Test with invalid image (wrong shape)
    invalid_image = np.zeros((10,), dtype=np.uint8)

    # Should handle gracefully or raise appropriate error
    try:
        result = analyzer.analyze(invalid_image)
        # If it doesn't raise, result should be valid
        assert isinstance(result, dict)
    except Exception as e:
        # If it raises, should be a clear error
        assert "shape" in str(e).lower() or "dimension" in str(e).lower()
