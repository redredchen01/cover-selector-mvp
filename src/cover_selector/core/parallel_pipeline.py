"""P5: Parallel pipeline - Multi-threaded feature extraction with caching for improved performance."""

import gc
import hashlib
import logging
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import cv2

logger = logging.getLogger(__name__)

from cover_selector.config import CoverSelectorConfig
from cover_selector.core.analyzer_cache import get_analyzer, clear_cache
from cover_selector.core.blur_analyzer import BlurAnalyzer
from cover_selector.core.brightness_analyzer import BrightnessAnalyzer
from cover_selector.core.composer_analyzer import ComposerAnalyzer
from cover_selector.core.composition_analyzer import CompositionAnalyzer
from cover_selector.core.composition_report_builder import CompositionReportBuilder
from cover_selector.core.face_analyzer import FaceAnalyzer
from cover_selector.core.frame_cache import FrameCache
from cover_selector.core.frame_sampler import FrameSampler
from cover_selector.core.image_compositor import ImageCompositor
from cover_selector.core.ocr_detector import OCRDetector
from cover_selector.core.ranker import Ranker
from cover_selector.core.scene_detector import SceneDetector
from cover_selector.core.scorer import Scorer
from cover_selector.schemas.frame_features import FrameFeatures
from cover_selector.schemas.ranking_result import RankingResult


class ParallelVideoToTripleCollagePipeline:
    """End-to-end pipeline with parallel feature extraction and caching."""

    def __init__(self, config: CoverSelectorConfig, max_workers: Optional[int] = None, cache_dir: Optional[str] = None):
        """Initialize pipeline with configuration and caching.

        Args:
            config: Pipeline configuration
            max_workers: Number of worker threads (default: min(4, cpu_count))
            cache_dir: Directory for frame cache (default: ~/.cover_selector_cache)
        """
        self.config = config
        self.max_workers = max_workers or min(4, __import__('os').cpu_count() or 4)

        # Initialize all feature analyzers
        self.scene_detector = get_analyzer(SceneDetector, config.scene_detection)
        self.frame_sampler = get_analyzer(FrameSampler, config)
        self.blur_analyzer = get_analyzer(BlurAnalyzer, config.blur_analysis)
        self.brightness_analyzer = get_analyzer(BrightnessAnalyzer, config.brightness_analysis)
        self.face_analyzer = get_analyzer(FaceAnalyzer, config.face_analysis)
        self.ocr_detector = get_analyzer(OCRDetector, config.ocr_detection)
        self.composition_analyzer = get_analyzer(CompositionAnalyzer, config)
        self.scorer = Scorer(config.scorer)
        self.ranker = get_analyzer(Ranker, config)
        self.composer_analyzer = get_analyzer(ComposerAnalyzer, config.composition_analysis)
        self.image_compositor = None
        self.report_builder = CompositionReportBuilder()

        # Initialize frame cache
        self.frame_cache = FrameCache(cache_dir=cache_dir)
        self.config_hash = self._compute_config_hash()

    def _compute_config_hash(self) -> str:
        """Compute hash of configuration for cache invalidation."""
        config_str = str(self.config.dict())
        return hashlib.md5(config_str.encode()).hexdigest()

    def _extract_single_feature(self, video_path: str, candidate_frame) -> Tuple:
        """Extract features for a single candidate frame using all analyzers.

        Uses frame cache to avoid recomputation on re-runs.
        """
        try:
            # Extract frame image
            frame_image = self._extract_frame_image(video_path, candidate_frame.timestamp_sec)
            if frame_image is None:
                raise ValueError(f"Failed to extract frame {candidate_frame.frame_id}")

            # Check cache first
            frame_bytes = cv2.imencode(".jpg", frame_image)[1].tobytes()
            cached_features = self.frame_cache.get(frame_bytes, self.config_hash)
            if cached_features:
                features = FrameFeatures(**cached_features)
                score_result = self.scorer.score(features)
                return (candidate_frame.frame_id, features, score_result)

            # Extract features from all analyzers in parallel (per-frame)
            blur_result = self.blur_analyzer.analyze(frame_image)
            brightness_result = self.brightness_analyzer.analyze(frame_image)
            face_result = self.face_analyzer.analyze(frame_image)
            ocr_result = self.ocr_detector.detect(frame_image)
            composition_result = self.composition_analyzer.analyze(frame_image)

            # Build FrameFeatures
            features = FrameFeatures(
                frame_id=candidate_frame.frame_id,
                timestamp_sec=candidate_frame.timestamp_sec,
                # Blur/Clarity
                blur_score=blur_result.get("blur_score", 0.0),
                laplacian_variance=blur_result.get("laplacian_variance", 0.0),
                edge_density=blur_result.get("edge_density", 0.0),
                # Brightness/Contrast
                brightness_score=brightness_result.get("brightness_score", 0.0),
                contrast_score=brightness_result.get("contrast_score", 0.0),
                overexposure_score=brightness_result.get("overexposure_score", 0.0),
                underexposure_score=brightness_result.get("underexposure_score", 0.0),
                # OCR
                ocr_text_count=ocr_result.get("text_count", 0),
                ocr_text_area_ratio=ocr_result.get("text_area_ratio", 0.0),
                bottom_subtitle_ratio=ocr_result.get("bottom_subtitle_ratio", 0.0),
                corner_text_ratio=ocr_result.get("corner_text_ratio", 0.0),
                center_text_ratio=ocr_result.get("center_text_ratio", 0.0),
                # Face detection
                face_count=face_result.get("face_count", 0),
                largest_face_ratio=face_result.get("largest_face_ratio", 0.0),
                face_edge_cutoff_ratio=face_result.get("face_edge_cutoff_ratio", 0.0),
                primary_face_center_offset=face_result.get("primary_face_center_offset", 0.0),
                face_confidence=face_result.get("face_confidence", 0.0),
                face_center_x=face_result.get("face_center_x", 0.0),
                face_center_y=face_result.get("face_center_y", 0.0),
                face_size_ratio=face_result.get("face_size_ratio", 0.0),
                face_landmarks_json=face_result.get("face_landmarks_json"),
                # Composition
                is_closeup=composition_result.get("is_closeup", False),
                is_subject_too_small=composition_result.get("is_subject_too_small", False),
                is_subject_cutoff=composition_result.get("is_subject_cutoff", False),
                subject_center_offset=composition_result.get("subject_center_offset", 0.0),
                composition_balance_score=composition_result.get("composition_balance_score", 0.0),
            )

            # Cache the features
            self.frame_cache.put(frame_bytes, self.config_hash, features.dict())

            # Score the features
            score_result = self.scorer.score(features)
            return (candidate_frame.frame_id, features, score_result)

        except Exception as e:
            logger.warning(f"  ⚠️ Failed to extract features for frame {candidate_frame.frame_id}: {e}")
            raise

    def _extract_frame_image(self, video_path: str, timestamp_sec: float) -> Optional[np.ndarray]:
        """Extract a single frame image from video at given timestamp."""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_num = int(timestamp_sec * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            cap.release()
            return frame if ret else None
        except Exception as e:
            logger.warning(f"Failed to extract frame at {timestamp_sec}s: {e}")
            return None

    def run(self, video_path: str, output_dir: Path) -> Dict:
        """Complete pipeline with parallel feature extraction."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "video_path": str(video_path),
            "scenes_count": 0,
            "candidates_count": 0,
            "final_cover": None,
            "cover_mode": None,
            "parallel_execution": True,
            "max_workers": self.max_workers,
        }

        logger.info("📍 Stage 1: Scene Detection...")
        scenes = self.scene_detector.detect(video_path)
        results["scenes_count"] = len(scenes)
        logger.info(f"  ✓ Found {len(scenes)} scenes")

        logger.info("📍 Stage 2: Frame Sampling...")
        candidate_frames = self.frame_sampler.sample_frames(video_path, scenes)
        results["candidates_count"] = len(candidate_frames)
        logger.info(f"  ✓ Sampled {len(candidate_frames)} candidates")

        # P5: Parallel feature extraction with caching
        logger.info(f"📍 Stage 3: Parallel Feature Extraction & Scoring ({self.max_workers} workers)...")
        features_list = []
        scores_dict = {}

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all extraction tasks
                futures = {
                    executor.submit(self._extract_single_feature, video_path, cf): cf.frame_id
                    for cf in candidate_frames
                }

                # Collect results as they complete
                completed = 0
                for future in as_completed(futures):
                    try:
                        frame_id, features, score_result = future.result()
                        features_list.append(features)
                        scores_dict[frame_id] = score_result
                        completed += 1
                        if completed % max(1, len(candidate_frames) // 4) == 0:
                            logger.info(f"  ✓ Extracted features for {completed}/{len(candidate_frames)} frames")
                    except Exception as e:
                        logger.warning(f"  ⚠️ Failed to process frame: {e}")

            logger.info(f"  ✓ Completed feature extraction for {completed} frames")

            # Log cache statistics
            cache_stats = self.frame_cache.get_stats()
            logger.info(f"  📊 Cache: {cache_stats['hits']} hits, {cache_stats['misses']} misses ({cache_stats['hit_rate_pct']:.1f}% hit rate)")

        except Exception as e:
            logger.error(f"  ❌ Parallel extraction failed: {e}, falling back to sequential")
            # Fallback to sequential if parallel fails
            for cf in candidate_frames:
                frame_id, features, score_result = self._extract_single_feature(video_path, cf)
                features_list.append(features)
                scores_dict[frame_id] = score_result

        logger.info("📍 Stage 4: Ranking...")
        ranking_results, ranking_metadata = self.ranker.rank(features_list, scores_dict)
        logger.info(f"  ✓ Ranked {len(ranking_results)} frames")

        # Build frame_features_map before releasing large data structures
        frame_features_map = {f.frame_id: f for f in features_list}

        # P4: Memory optimization
        del features_list, scores_dict
        gc.collect()

        video_duration = self._get_video_duration(video_path)
        logger.info(f"  ✓ Video duration: {video_duration:.1f}s")

        logger.info("📍 Stage 5: Triple-Collage Composition...")
        composition_result = self.composer_analyzer.compose(
            ranking_results, frame_features_map, {"duration": video_duration}
        )

        if composition_result.is_degraded:
            logger.info(f"  ⚠️ Degraded mode: {composition_result.degradation_reason}")
            results["cover_mode"] = "degraded"
            selected_frames = [composition_result.bottom_image]
        else:
            logger.info("  ✨ Triple-collage mode")
            results["cover_mode"] = "triple"
            selected_frames = [composition_result.bottom_image] + composition_result.zoom_images

        logger.info("📍 Stage 6: Extracting Frame Images from Video...")
        with tempfile.TemporaryDirectory() as tmpdir:
            frame_paths = self._extract_frames(video_path, selected_frames, tmpdir)
            gc.collect()

            logger.info("📍 Stage 7: Compositing Final Image...")
            if self.image_compositor:
                try:
                    final_image_path = self.image_compositor.compose(
                        frame_paths[0],
                        frame_paths[1] if len(frame_paths) > 1 else frame_paths[0],
                        frame_paths[2] if len(frame_paths) > 2 else frame_paths[0],
                        str(Path(output_dir) / "final_cover.jpg"),
                    )
                    results["final_cover"] = str(final_image_path)
                    logger.info(f"  ✓ Final cover saved: {final_image_path}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Compositing failed: {e}, using base frame instead")
                    results["final_cover"] = frame_paths[0] if frame_paths else None
            else:
                results["final_cover"] = frame_paths[0] if frame_paths else None
                logger.info(f"  ✓ Frame extracted: {results['final_cover']}")

        report = self.report_builder.build_report(composition_result, "composition_report.json")
        report_path = output_dir / "composition_report.json"
        self.report_builder.save_report(report, str(report_path))

        # P4: Final memory cleanup
        del candidate_frames, ranking_results, frame_features_map, composition_result
        gc.collect()

        return results

    def _extract_frames(self, video_path: str, frames_to_extract, tmpdir: str) -> List[str]:
        """Extract specified frames from video using ffmpeg."""
        frame_paths = []

        for i, frame in enumerate(frames_to_extract):
            output_path = Path(tmpdir) / f"frame_{i}_{frame.frame_id}.jpg"

            cmd = [
                "ffmpeg",
                "-ss",
                f"{frame.timestamp_sec}",
                "-i",
                video_path,
                "-vf",
                "scale=-1:-1",
                "-vframes",
                "1",
                "-q:v",
                "2",
                str(output_path),
            ]

            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                frame_paths.append(str(output_path))
                logger.info(f"    ✓ Extracted frame {frame.frame_id} @ {frame.timestamp_sec:.2f}s")
            except subprocess.CalledProcessError as e:
                logger.warning(f"    ⚠️ Failed to extract frame {frame.frame_id}: {e}")
                frame_paths.append(
                    frame_paths[-1] if frame_paths else self._create_fallback_image(tmpdir, i)
                )

        return frame_paths

    def _create_fallback_image(self, tmpdir: str, index: int) -> str:
        """Create a fallback black image when ffmpeg extraction fails."""
        from PIL import Image

        fallback_path = Path(tmpdir) / f"fallback_{index}.jpg"
        img = Image.new("RGB", (1920, 1080), color=(0, 0, 0))
        try:
            img.save(fallback_path, "JPEG", quality=95)
        finally:
            img.close()
        return str(fallback_path)

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception:
            return 0.0


def create_parallel_pipeline(
    config: CoverSelectorConfig,
    max_workers: Optional[int] = None,
    cache_dir: Optional[str] = None
) -> ParallelVideoToTripleCollagePipeline:
    """Factory function for parallel pipeline with caching support."""
    return ParallelVideoToTripleCollagePipeline(config, max_workers=max_workers, cache_dir=cache_dir)
