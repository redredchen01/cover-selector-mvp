"""Face detection analysis using MediaPipe."""

import json
import logging
from typing import Optional

import numpy as np

from cover_selector.config import FaceAnalysisConfig

logger = logging.getLogger(__name__)

# Try to import MediaPipe with graceful fallback
_MEDIAPIPE_AVAILABLE = False
face_detection_module = None

try:
    from mediapipe import solutions as mp_solutions
    face_detection_module = mp_solutions.face_detection
    _MEDIAPIPE_AVAILABLE = True
except (ImportError, AttributeError):
    try:
        import mediapipe as mp
        face_detection_module = mp.solutions.face_detection
        _MEDIAPIPE_AVAILABLE = True
    except (ImportError, AttributeError):
        logger.warning("MediaPipe not available. Face detection will use heuristics only.")
        _MEDIAPIPE_AVAILABLE = False


class FaceAnalyzer:
    """Detects and analyzes faces in images using MediaPipe (with graceful fallback)."""

    def __init__(self, config: FaceAnalysisConfig):
        """
        Initialize face analyzer.

        Args:
            config: Face analysis configuration

        Note:
            If MediaPipe is not available, analyzer will fall back to heuristic-based
            detection using image analysis.
        """
        self.config = config
        self.detector = None
        self.mediapipe_available = _MEDIAPIPE_AVAILABLE

        if self.mediapipe_available and face_detection_module:
            try:
                self.detector = face_detection_module.FaceDetection(
                    model_selection=0,  # 0=short range (0-2m), 1=full range (0-5m)
                    min_detection_confidence=config.face_confidence,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize MediaPipe detector: {e}. Falling back to heuristics.")
                self.mediapipe_available = False
                self.detector = None

    def analyze(self, image: np.ndarray) -> dict:
        """
        Detect faces and analyze face-related features.

        Uses MediaPipe if available, falls back to heuristics otherwise.

        Args:
            image: Input image (BGR format from OpenCV)

        Returns:
            Dictionary with face metrics:
            - face_count: Number of faces detected
            - largest_face_ratio: Largest face area ratio
            - face_edge_cutoff_ratio: Max face cutoff at edges
            - primary_face_center_offset: Offset of primary face from center
            - face_confidence: Confidence of primary face detection
            - face_center_x: X coordinate of primary face center (0-1)
            - face_center_y: Y coordinate of primary face center (0-1)
            - face_size_ratio: Size ratio of primary face
            - face_landmarks_json: JSON string of face landmarks (468 points) if available
        """
        if self.mediapipe_available and self.detector:
            return self._analyze_with_mediapipe(image)
        else:
            return self._analyze_heuristic(image)

    def _analyze_with_mediapipe(self, image: np.ndarray) -> dict:
        """Analyze using MediaPipe face detection."""
        # MediaPipe expects RGB, not BGR
        image_rgb = image[:, :, ::-1] if len(image.shape) == 3 else image
        h, w = image.shape[:2]

        try:
            results = self.detector.process(image_rgb)
        except Exception as e:
            logger.warning(f"MediaPipe processing failed: {e}. Falling back to heuristics.")
            return self._analyze_heuristic(image)

        face_count = 0
        face_ratios = []
        face_centers = []
        face_cutoffs = []
        face_confidences = []
        primary_landmarks = None
        primary_confidence = 0.0

        if results.detections:
            face_count = len(results.detections)

            for idx, detection in enumerate(results.detections):
                # Get bounding box
                bbox = detection.location_data.relative_bounding_box
                left = bbox.xmin
                top = bbox.ymin
                width = bbox.width
                height = bbox.height

                # Calculate face area ratio
                face_area = width * height
                face_ratios.append(face_area)

                # Calculate center position
                face_center_x = left + width / 2.0
                face_center_y = top + height / 2.0
                face_centers.append((face_center_x, face_center_y))

                # Calculate edge cutoff
                cutoff = 0.0
                if left < 0:
                    cutoff = max(cutoff, -left)
                if left + width > 1:
                    cutoff = max(cutoff, (left + width) - 1)
                if top < 0:
                    cutoff = max(cutoff, -top)
                if top + height > 1:
                    cutoff = max(cutoff, (top + height) - 1)
                face_cutoffs.append(cutoff)

                # Extract confidence score
                confidence = detection.score[0] if detection.score else 0.0
                face_confidences.append(confidence)

                # Extract landmarks if available (MediaPipe face_detection has keypoints)
                if idx == 0:  # Store primary face landmarks
                    primary_confidence = confidence
                    if hasattr(detection.location_data, 'keypoints') and detection.location_data.keypoints:
                        landmarks = []
                        for keypoint in detection.location_data.keypoints:
                            landmarks.append({
                                "x": float(keypoint.x),
                                "y": float(keypoint.y),
                                "z": float(getattr(keypoint, 'z', 0.0))
                            })
                        if landmarks:
                            primary_landmarks = landmarks

        # Calculate metrics
        largest_face_ratio = max(face_ratios) if face_ratios else 0.0
        face_edge_cutoff_ratio = max(face_cutoffs) if face_cutoffs else 0.0

        # Calculate primary face offset from center
        primary_face_center_offset = 0.0
        primary_face_center_x = 0.0
        primary_face_center_y = 0.0
        primary_face_size_ratio = 0.0

        if face_centers:
            center_x, center_y = face_centers[0]
            offset_x = abs(center_x - 0.5)
            offset_y = abs(center_y - 0.5)
            primary_face_center_offset = max(offset_x, offset_y)
            primary_face_center_x = center_x
            primary_face_center_y = center_y
            primary_face_size_ratio = face_ratios[0] if face_ratios else 0.0

        # Convert landmarks to JSON if present
        landmarks_json = None
        if primary_landmarks:
            try:
                landmarks_json = json.dumps(primary_landmarks)
            except (TypeError, ValueError) as e:
                logger.warning(f"Failed to serialize landmarks: {e}")

        return {
            "face_count": int(face_count),
            "largest_face_ratio": float(largest_face_ratio),
            "face_edge_cutoff_ratio": float(face_edge_cutoff_ratio),
            "primary_face_center_offset": float(primary_face_center_offset),
            "face_confidence": float(primary_confidence),
            "face_center_x": float(primary_face_center_x),
            "face_center_y": float(primary_face_center_y),
            "face_size_ratio": float(primary_face_size_ratio),
            "face_landmarks_json": landmarks_json,
            "face_detections": results.detections if results.detections else [],
        }

    def _analyze_heuristic(self, image: np.ndarray) -> dict:
        """Fallback heuristic-based face analysis without MediaPipe."""
        h, w = image.shape[:2]

        # Simple heuristic: detect face-like regions based on color/edge density
        # This is a basic fallback - in production, might use different approach
        try:
            import cv2

            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # Use basic edge detection as proxy for face regions
            edges = cv2.Canny(gray, 100, 200)
            contours, _ = cv2.findContours(
                edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            face_count = 0
            face_ratios = []
            face_centers = []
            face_cutoffs = []

            # Consider significant contours as potential faces
            for contour in contours[:10]:  # Limit to top 10 contours
                x, y, width, height = cv2.boundingRect(contour)
                aspect_ratio = width / (height + 1e-5)

                # Simple heuristic: face-like rectangles have aspect ratio close to 1
                if 0.5 < aspect_ratio < 2.0 and width > 20 and height > 20:
                    face_count += 1

                    # Normalize to 0-1
                    norm_x = x / w
                    norm_y = y / h
                    norm_w = width / w
                    norm_h = height / h

                    face_area = norm_w * norm_h
                    face_ratios.append(face_area)

                    # Center
                    center_x = norm_x + norm_w / 2
                    center_y = norm_y + norm_h / 2
                    face_centers.append((center_x, center_y))

                    # Edge cutoff
                    cutoff = max(
                        max(-norm_x, 0),
                        max(norm_x + norm_w - 1, 0),
                        max(-norm_y, 0),
                        max(norm_y + norm_h - 1, 0)
                    )
                    face_cutoffs.append(cutoff)

            largest_face_ratio = max(face_ratios) if face_ratios else 0.0
            face_edge_cutoff_ratio = max(face_cutoffs) if face_cutoffs else 0.0

            primary_face_center_offset = 0.0
            primary_face_center_x = 0.0
            primary_face_center_y = 0.0
            primary_face_size_ratio = 0.0

            if face_centers:
                center_x, center_y = face_centers[0]
                offset_x = abs(center_x - 0.5)
                offset_y = abs(center_y - 0.5)
                primary_face_center_offset = max(offset_x, offset_y)
                primary_face_center_x = center_x
                primary_face_center_y = center_y
                primary_face_size_ratio = face_ratios[0] if face_ratios else 0.0

            return {
                "face_count": min(face_count, 10),  # Cap at 10
                "largest_face_ratio": float(largest_face_ratio),
                "face_edge_cutoff_ratio": float(face_edge_cutoff_ratio),
                "primary_face_center_offset": float(primary_face_center_offset),
                "face_confidence": 0.5 if face_count > 0 else 0.0,  # Heuristic confidence
                "face_center_x": float(primary_face_center_x),
                "face_center_y": float(primary_face_center_y),
                "face_size_ratio": float(primary_face_size_ratio),
                "face_landmarks_json": None,  # Heuristic method doesn't extract landmarks
                "face_detections": [],
            }
        except Exception as e:
            logger.warning(f"Heuristic face analysis failed: {e}. Returning empty result.")
            return {
                "face_count": 0,
                "largest_face_ratio": 0.0,
                "face_edge_cutoff_ratio": 0.0,
                "primary_face_center_offset": 0.0,
                "face_confidence": 0.0,
                "face_center_x": 0.0,
                "face_center_y": 0.0,
                "face_size_ratio": 0.0,
                "face_landmarks_json": None,
                "face_detections": [],
            }
