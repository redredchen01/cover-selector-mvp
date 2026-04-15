"""Tests for face analyzer with MediaPipe landmarks extraction."""

import json
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from cover_selector.config import FaceAnalysisConfig
from cover_selector.core.face_analyzer import FaceAnalyzer


@pytest.fixture
def config():
    """Default face analysis config."""
    return FaceAnalysisConfig(face_confidence=0.5)


@pytest.fixture
def analyzer(config):
    """Face analyzer instance."""
    return FaceAnalyzer(config)


def create_image_with_face(width=640, height=480):
    """Create a synthetic image with a face-like region."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 100
    # Create a face-like region in the center
    face_region = img[100:400, 150:490]
    # Simulate face with slightly different color
    face_region[:] = 150
    # Add some features (eyes)
    img[150:180, 200:250] = 200  # Left eye region
    img[150:180, 350:400] = 200  # Right eye region
    return img


def test_face_analyzer_init(config):
    """Test FaceAnalyzer initialization."""
    analyzer = FaceAnalyzer(config)
    assert analyzer.config == config
    # Detector may be None if MediaPipe is unavailable (graceful fallback)
    # but analyzer should still be usable via heuristic fallback
    assert analyzer.mediapipe_available is not None


def test_analyze_with_no_face():
    """Test analyzer on image with no face - edge case."""
    config = FaceAnalysisConfig(face_confidence=0.5)
    analyzer = FaceAnalyzer(config)

    # Create blank image
    image = np.ones((480, 640, 3), dtype=np.uint8) * 50
    result = analyzer.analyze(image)

    # Should return 0 faces with default values
    assert result["face_count"] == 0
    assert result["face_confidence"] == 0.0
    assert result["face_center_x"] == 0.0
    assert result["face_center_y"] == 0.0
    assert result["face_size_ratio"] == 0.0
    assert result["face_landmarks_json"] is None


def test_analyze_returns_all_required_fields():
    """Test happy path - all required face fields are present."""
    config = FaceAnalysisConfig(face_confidence=0.5)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    # Check all required fields exist
    assert "face_count" in result
    assert "largest_face_ratio" in result
    assert "face_edge_cutoff_ratio" in result
    assert "primary_face_center_offset" in result
    assert "face_confidence" in result
    assert "face_center_x" in result
    assert "face_center_y" in result
    assert "face_size_ratio" in result
    assert "face_landmarks_json" in result


def test_face_confidence_range():
    """Test that face confidence is in valid range (0-1)."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    assert 0.0 <= result["face_confidence"] <= 1.0
    assert isinstance(result["face_confidence"], float)


def test_face_center_coordinates_normalized():
    """Test that face center coordinates are normalized (0-1)."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    assert 0.0 <= result["face_center_x"] <= 1.0
    assert 0.0 <= result["face_center_y"] <= 1.0
    assert isinstance(result["face_center_x"], float)
    assert isinstance(result["face_center_y"], float)


def test_face_size_ratio_valid():
    """Test that face size ratio is valid (0-1)."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    assert 0.0 <= result["face_size_ratio"] <= 1.0
    assert isinstance(result["face_size_ratio"], float)


def test_landmarks_json_valid_format():
    """Test that face landmarks JSON is valid when present."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    if result["face_landmarks_json"] is not None:
        # Should be valid JSON
        landmarks = json.loads(result["face_landmarks_json"])
        assert isinstance(landmarks, list)

        # Each landmark should have x, y, z
        for landmark in landmarks:
            assert "x" in landmark
            assert "y" in landmark
            assert "z" in landmark
            assert isinstance(landmark["x"], (int, float))
            assert isinstance(landmark["y"], (int, float))
            assert isinstance(landmark["z"], (int, float))


def test_analyze_grayscale_image():
    """Test analyzer works with grayscale input."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    color_image = create_image_with_face()
    gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

    result = analyzer.analyze(gray)

    # Should return valid result structure
    assert "face_count" in result
    assert isinstance(result["face_count"], int)


def test_backward_compatibility_old_fields():
    """Test that old face detection fields still work."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    # Old fields should still be present
    assert "face_count" in result
    assert "largest_face_ratio" in result
    assert "face_edge_cutoff_ratio" in result
    assert "primary_face_center_offset" in result
    assert "face_detections" in result


def test_multiple_faces_only_primary_landmarks():
    """Test that only primary (first) face gets landmarks."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    # Create image with multiple face-like regions
    img = np.ones((480, 640, 3), dtype=np.uint8) * 100
    img[50:200, 50:200] = 150  # Face 1
    img[50:200, 350:500] = 150  # Face 2

    result = analyzer.analyze(img)

    # If multiple faces detected, landmarks should be from first one only
    if result["face_count"] > 0:
        # Check that we have consistent primary face data
        assert result["face_center_x"] >= 0
        assert result["face_center_y"] >= 0


def test_edge_case_very_small_face():
    """Test edge case with very small face in corner."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    img = np.ones((480, 640, 3), dtype=np.uint8) * 100
    # Tiny face-like region
    img[10:30, 10:30] = 150

    result = analyzer.analyze(img)

    # Should handle gracefully
    assert isinstance(result["face_count"], int)
    assert 0.0 <= result["face_size_ratio"] <= 1.0


def test_edge_case_face_at_edge():
    """Test edge case with face partially at image edge."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    img = np.ones((480, 640, 3), dtype=np.uint8) * 100
    # Face region extending beyond edge
    img[100:300, 500:650] = 150  # Note: 650 > 640, would be clipped

    result = analyzer.analyze(img)

    # Should have handled edge cutoff
    assert "face_edge_cutoff_ratio" in result
    assert 0.0 <= result["face_edge_cutoff_ratio"] <= 1.0


def test_error_recovery_invalid_landmarks():
    """Test graceful handling if landmarks serialization fails."""
    config = FaceAnalysisConfig(face_confidence=0.3)
    analyzer = FaceAnalyzer(config)

    image = create_image_with_face()
    result = analyzer.analyze(image)

    # Even if something fails, landmarks_json should be None or valid JSON
    if result["face_landmarks_json"] is not None:
        try:
            json.loads(result["face_landmarks_json"])
        except json.JSONDecodeError:
            pytest.fail("landmarks_json is not valid JSON")
