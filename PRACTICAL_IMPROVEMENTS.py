"""
Practical improvements for video_processing.py

This file contains concrete implementations of the recommended improvements.
"""

from typing import List, Dict, Any, Optional, Tuple, Iterator, TypeGuard
from math import isfinite
import logging
import os
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

# ============================================================================
# 1. CONFIGURATION CLASS
# ============================================================================

class VideoProcessingConfig:
    """Centralized configuration for video processing parameters."""
    
    # Segment processing limits
    MAX_SEGMENTS_TO_RENDER = int(os.getenv("MAX_SEGMENTS_TO_RENDER", "10"))
    HARD_MAX_SEGMENTS = int(os.getenv("HARD_MAX_SEGMENTS", "240"))
    
    # Timing parameters
    MAX_MERGED_SEGMENT_SECONDS = float(os.getenv("MAX_MERGED_SEGMENT_SECONDS", "20"))
    MERGE_GAP_SECONDS = float(os.getenv("SEGMENT_MERGE_GAP_SECONDS", "0.6"))
    MIN_SEGMENT_SECONDS = float(os.getenv("MIN_SEGMENT_SECONDS", "2.0"))
    IDEAL_SEGMENT_SECONDS = float(os.getenv("IDEAL_SEGMENT_SECONDS", "8.0"))
    FILLER_CHUNK_SECONDS = float(os.getenv("FILLER_CHUNK_SECONDS", "30.0"))
    
    # Selection parameters
    TRAILER_SELECTOR_MAX_INPUT_SEGMENTS = int(os.getenv("TRAILER_SELECTOR_MAX_INPUT_SEGMENTS", "500"))
    TRAILER_SELECTOR_VIDEO_DURATION_LIMIT_SECONDS = float(
        os.getenv("TRAILER_SELECTOR_VIDEO_DURATION_LIMIT_SECONDS", "1800")
    )
    
    # API tolerance
    API_DURATION_TOLERANCE_SECONDS = float(os.getenv("API_DURATION_TOLERANCE_SECONDS", "1.5"))
    
    # Overlap detection
    DEFAULT_OVERLAP_THRESHOLD = 0.1
    DEFAULT_GAP_THRESHOLD = 0.05


# ============================================================================
# 2. TYPE GUARDS AND VALIDATION
# ============================================================================

def _is_valid_segment(segment: tuple) -> TypeGuard[tuple[float, float]]:
    """Type guard for valid segment tuples."""
    return (isinstance(segment, tuple) and 
            len(segment) == 2 and 
            all(isinstance(x, (int, float)) for x in segment) and
            segment[1] > segment[0] and
            all(isfinite(float(x)) for x in segment))

def _validate_segment_range(start: float, end: float, max_duration: Optional[float] = None) -> bool:
    """Validate that a segment range is valid."""
    if not (isinstance(start, (int, float)) and isinstance(end, (int, float))):
        return False
    if not (isfinite(float(start)) and isfinite(float(end))):
        return False
    if end <= start:
        return False
    if max_duration is not None and (start < 0 or end > max_duration):
        return False
    return True


# ============================================================================
# 3. IMPROVED OVERLAP DETECTION
# ============================================================================

def _segments_overlap(seg1: tuple, seg2: tuple, threshold: float = VideoProcessingConfig.DEFAULT_OVERLAP_THRESHOLD) -> bool:
    """Check if two segments overlap by more than threshold."""
    start1, end1 = float(seg1[0]), float(seg1[1])
    start2, end2 = float(seg2[0]), float(seg2[1])
    
    # No overlap if one ends before the other starts
    if start1 >= end2 or start2 >= end1:
        return False
        
    # Calculate overlap duration
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap_duration = overlap_end - overlap_start
    
    return overlap_duration > threshold


def _has_any_overlap(segment: tuple, existing_segments: List[tuple], threshold: float = VideoProcessingConfig.DEFAULT_OVERLAP_THRESHOLD) -> bool:
    """Check if a segment overlaps with any segment in a list."""
    seg_start, seg_end = float(segment[0]), float(segment[1])
    
    for existing_start, existing_end in existing_segments:
        if _segments_overlap((seg_start, seg_end), (existing_start, existing_end), threshold):
            return True
    return False


# ============================================================================
# 4. PERFORMANCE OPTIMIZATIONS
# ============================================================================

@contextmanager
def timing_context(operation_name: str):
    """Context manager for timing operations."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        logger.debug(f"{operation_name} took {duration:.3f}s")

def _sort_segments_cached(segments: List[tuple]) -> List[tuple]:
    """Sort segments by start time with caching optimization."""
    if not segments:
        return []
    
    # Use a single sort operation with a cached key function
    return sorted(segments, key=lambda x: (float(x[0]), float(x[1])))

def _merge_segments_optimized(segments: List[tuple], gap_threshold: float = VideoProcessingConfig.MERGE_GAP_SECONDS) -> List[tuple]:
    """Optimized segment merging with early validation."""
    if not segments:
        return []
    
    # Sort once and validate
    sorted_segments = _sort_segments_cached(segments)
    
    merged: List[tuple] = []
    current_start, current_end = float(sorted_segments[0][0]), float(sorted_segments[0][1])
    
    for start, end in sorted_segments[1:]:
        start, end = float(start), float(end)
        
        # Check if we can merge
        if start - current_end <= gap_threshold and (end - current_start) <= VideoProcessingConfig.MAX_MERGED_SEGMENT_SECONDS:
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    
    # Don't forget the last segment
    merged.append((current_start, current_end))
    return merged


# ============================================================================
# 5. IMPROVED SEGMENT SELECTION
# ============================================================================

def _select_best_phase_segments(
    scored_segments: List[Dict[str, Any]],
    selected: List[tuple],
    target_duration: float,
    consumed: float,
    max_segments: int,
    score_key: str,
    min_phase_seconds: float,
    min_score: float,
    pos_range: Optional[Tuple[float, float]] = None
) -> Tuple[List[tuple], float]:
    """
    Select the best segments for a specific phase based on scoring.
    
    Args:
        scored_segments: List of segments with scoring data
        selected: Already selected segments to avoid overlap
        target_duration: Target duration for the final video
        consumed: Already consumed duration
        max_segments: Maximum number of segments to select
        score_key: Key to use for phase-specific scoring
        min_phase_seconds: Minimum duration to allocate to this phase
        min_score: Minimum score threshold for selection
        pos_range: Optional position range (start_ratio, end_ratio) for segment selection
        
    Returns:
        Tuple of (updated_selected_segments, updated_consumed_duration)
        
    Raises:
        ValueError: If invalid parameters are provided
    """
    if not scored_segments:
        return selected, consumed
    
    if target_duration <= 0 or consumed < 0 or max_segments <= 0:
        raise ValueError("Invalid parameters: target_duration, consumed, or max_segments")
    
    if min_phase_seconds < 0 or min_score < 0:
        raise ValueError("Invalid parameters: min_phase_seconds or min_score")
    
    # Filter candidates
    candidates = []
    for seg in scored_segments:
        phase_score = float(seg.get(score_key, 0.0))
        if phase_score < min_score:
            continue
            
        if pos_range is not None:
            pos = float(seg.get("position_ratio", 0.0))
            if pos < pos_range[0] or pos > pos_range[1]:
                continue
                
        candidates.append(seg)
    
    if not candidates:
        return selected, consumed
    
    # Sort by phase score and overall score
    candidates.sort(key=lambda s: (float(s.get(score_key, 0.0)), float(s.get("score", 0.0))), reverse=True)
    
    phase_used = 0.0
    updated_selected = list(selected)
    updated_consumed = consumed
    
    for seg in candidates:
        if phase_used >= min_phase_seconds:
            break
        if len(updated_selected) >= max_segments:
            break

        start, end = float(seg["start"]), float(seg["end"])
        seg_len = max(0.0, end - start)
        
        if seg_len < VideoProcessingConfig.MIN_SEGMENT_SECONDS:
            continue

        remaining = target_duration - updated_consumed
        if remaining <= 0:
            break

        # Check for overlap
        if _has_any_overlap((start, end), updated_selected, VideoProcessingConfig.DEFAULT_OVERLAP_THRESHOLD):
            continue

        use_len = min(seg_len, remaining)
        if use_len < VideoProcessingConfig.MIN_SEGMENT_SECONDS:
            continue

        updated_selected.append((start, start + use_len))
        updated_consumed += use_len
        phase_used += use_len

    return updated_selected, updated_consumed


# ============================================================================
# 6. STREAMING PROCESSING
# ============================================================================

def _to_valid_float(value: Any) -> Optional[float]:
    """Convert value to finite float, otherwise return None."""
    try:
        num = float(value)
        if not isfinite(num):
            return None
        return num
    except (TypeError, ValueError):
        return None


def _process_segments_stream(segments: List[Any], video_duration: Optional[float]) -> Iterator[Dict[str, Any]]:
    """Process segments as a stream to reduce memory usage."""
    max_end = float(video_duration) if video_duration and video_duration > 0 else None
    
    for raw in segments:
        start_raw, end_raw = _get_segment_time_range_safe(raw)
        start = _to_valid_float(start_raw)
        end = _to_valid_float(end_raw)
        
        if start is None or end is None:
            continue
            
        if max_end is not None:
            start = max(0.0, min(start, max_end))
            end = max(0.0, min(end, max_end))
        else:
            start = max(0.0, start)
            end = max(0.0, end)

        dur = end - start
        if dur <= 0.05:
            continue

        text = _get_segment_text(raw)
        if not text.strip():
            continue

        score = _calculate_segment_score(text, dur, start, max_end)
        if score <= 0:
            continue

        yield {
            "start": start,
            "end": end,
            "duration": dur,
            "text": text,
            "score": score
        }


def _get_segment_time_range_safe(segment: Any) -> Tuple[float, float]:
    """Safely extract (start, end) time range from a segment."""
    if isinstance(segment, dict):
        start_val = segment.get("start", 0)
        end_val = segment.get("end", 0)
        # Ensure we have valid numeric values
        start_num = start_val if isinstance(start_val, (int, float)) else 0
        end_num = end_val if isinstance(end_val, (int, float)) else 0
        return (float(start_num), float(end_num))
    elif hasattr(segment, "start") and hasattr(segment, "end"):
        start_attr = getattr(segment, "start", 0)
        end_attr = getattr(segment, "end", 0)
        start_num = start_attr if isinstance(start_attr, (int, float)) else 0
        end_num = end_attr if isinstance(end_attr, (int, float)) else 0
        return (float(start_num), float(end_num))
    elif isinstance(segment, tuple) and len(segment) == 2:
        return (float(segment[0]), float(segment[1]))
    else:
        return (0.0, 0.0)


def _get_segment_text(segment: Any) -> str:
    """Extract text from a segment."""
    if isinstance(segment, dict):
        text = segment.get("text")
        return str(text) if text is not None else ""
    elif hasattr(segment, "text"):
        text = getattr(segment, "text", None)
        return str(text) if text is not None else ""
    return ""


def _calculate_segment_score(text: str, duration: float, start: float, max_end: Optional[float]) -> float:
    """Calculate a score for a segment."""
    if not text or duration <= 0:
        return 0.0
    
    # Simple scoring logic - can be expanded
    word_count = len(text.split())
    wps = word_count / duration if duration > 0 else 0.0
    position_ratio = (start / max_end) if max_end is not None and max_end > 0 else 0.0
    
    # Basic scoring formula
    score = (
        min(duration / VideoProcessingConfig.IDEAL_SEGMENT_SECONDS, 1.0) +
        min(wps / 3.0, 1.0) +
        min(word_count / 20.0, 1.0) +
        (1.0 if position_ratio <= 0.3 else 0.5)
    )
    
    return score


# ============================================================================
# 7. ERROR HANDLING
# ============================================================================

class VideoProcessingError(Exception):
    """Base exception for video processing errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "error": self.message,
            "code": self.code,
            "details": self.details
        }


def _safe_process_video_segment(segment_func):
    """Decorator for safe segment processing with error handling."""
    def wrapper(*args, **kwargs):
        try:
            return segment_func(*args, **kwargs)
        except VideoProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {segment_func.__name__}: {str(e)}")
            raise VideoProcessingError(
                f"Processing failed: {str(e)}",
                code="PROCESSING_ERROR",
                details={"function": segment_func.__name__}
            )
    return wrapper


# ============================================================================
# 8. EXAMPLE USAGE
# ============================================================================

@_safe_process_video_segment
def example_improved_processing(raw_segments: List[Any], video_duration: float, target_duration: float) -> List[tuple]:
    """
    Example of improved segment processing with all optimizations.
    """
    with timing_context("Total segment processing"):
        # Use streaming processing to reduce memory usage
        scored_segments = list(_process_segments_stream(raw_segments, video_duration))
        
        if not scored_segments:
            return [(0.0, min(float(target_duration), float(video_duration)))]
        
        # Sort segments by start time (convert to tuples for sorting)
        scored_segments_tuples = [(float(seg["start"]), float(seg["end"])) for seg in scored_segments]
        sorted_segments = _sort_segments_cached(scored_segments_tuples)
        
        # Select segments with improved overlap detection
        selected_segments = []
        consumed = 0.0
        
        for start, end in sorted_segments:
            if consumed >= target_duration:
                break
                
            seg_len = end - start
            
            if seg_len < VideoProcessingConfig.MIN_SEGMENT_SECONDS:
                continue
                
            if _has_any_overlap((start, end), selected_segments):
                continue
                
            use_len = min(seg_len, target_duration - consumed)
            if use_len < VideoProcessingConfig.MIN_SEGMENT_SECONDS:
                continue
                
            selected_segments.append((start, start + use_len))
            consumed += use_len
        
        # Merge nearby segments
        final_segments = _merge_segments_optimized(selected_segments)
        
        return final_segments


# ============================================================================
# 9. TESTING UTILITIES
# ============================================================================

def create_test_segment(start: float, end: float, text: str = "test", score: float = 1.0) -> Dict[str, Any]:
    """Create a test segment for testing purposes."""
    return {
        "start": start,
        "end": end,
        "text": text,
        "score": score,
        "duration": end - start,
        "position_ratio": start / 100.0  # Assume 100s video for testing
    }


def validate_segment_list(segments: List[tuple]) -> bool:
    """Validate that a list of segments has no overlaps and is properly sorted."""
    if not segments:
        return True
    
    sorted_segments = _sort_segments_cached(segments)
    
    # Check for overlaps
    for i in range(len(sorted_segments) - 1):
        current_end = float(sorted_segments[i][1])
        next_start = float(sorted_segments[i + 1][0])
        
        if next_start < current_end - VideoProcessingConfig.DEFAULT_OVERLAP_THRESHOLD:
            logger.warning(f"Overlap detected between segments {i} and {i+1}")
            return False
    
    return True


if __name__ == "__main__":
    # Example usage
    test_segments = [
        create_test_segment(10.0, 15.0, "Opening segment", 2.5),
        create_test_segment(20.0, 25.0, "Middle segment", 3.0),
        create_test_segment(30.0, 35.0, "Closing segment", 2.0),
    ]
    
    result = example_improved_processing(test_segments, 100.0, 30.0)
    print(f"Selected segments: {result}")
    print(f"Validation passed: {validate_segment_list(result)}")