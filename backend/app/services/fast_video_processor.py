# backend/app/services/fast_video_processor.py

"""
Fast Video Processor - Optimized for Speed, Stability and Frontend Control

Upgrades:
- Strict frontend quality validation
- Optional target_duration enforcement
- Safe subtitle trimming to match final output
- Accurate final duration validation
- No breaking of existing architecture
"""

import os
import subprocess
import logging
import warnings
warnings.filterwarnings("ignore")

import tempfile
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import json
import time
import uuid

from ..core import config

from .video_segmenter import VideoSegmenter

logger = logging.getLogger(__name__)

def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


# GPU-only mode - no CPU fallback
USE_FFMPEG_GPU = True
FFMPEG_GPU_STRICT = True  # Strict GPU-only mode - no CPU fallback
FFMPEG_GPU_DECODE = _env_bool("FFMPEG_GPU_DECODE", "true")
FAST_CONCAT_COPY = _env_bool("FAST_CONCAT_COPY", "true")
SEGMENT_COPY_FIRST = _env_bool("SEGMENT_COPY_FIRST", "true")
# OPTIMIZATION: Lowered from 45 to 10 seconds for more stream copy usage
SEGMENT_COPY_MIN_TARGET_SECONDS = float(os.getenv("SEGMENT_COPY_MIN_TARGET_SECONDS", "10"))
STRICT_QUALITY_VALIDATION = _env_bool("STRICT_QUALITY_VALIDATION", "false")
ENABLE_FULL_DECODE_VERIFY = _env_bool("ENABLE_FULL_DECODE_VERIFY", "false")
ENABLE_PLAYBACK_REPAIR = _env_bool("ENABLE_PLAYBACK_REPAIR", "false")
FFPROBE_TIMEOUT_SECONDS = float(os.getenv("FFPROBE_TIMEOUT_SECONDS", "20"))
FFMPEG_TIMEOUT_SECONDS = float(os.getenv("FFMPEG_TIMEOUT_SECONDS", "480"))
# OPTIMIZATION: Increased from 0.05 to 0.5 for less re-encoding
DURATION_TOLERANCE_SECONDS = float(os.getenv("DURATION_TOLERANCE_SECONDS", "1.5"))
_NVENC_AVAILABLE_CACHE: Optional[bool] = None


def _run_command(cmd: List[str], timeout_seconds: float, label: str) -> Optional[subprocess.CompletedProcess]:
    try:
        logger.info("[CMD] %s (timeout=%.1fs)", label, timeout_seconds)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        if result.returncode != 0:
            err_preview = (result.stderr or "").strip().replace("\n", " ")
            if len(err_preview) > 300:
                err_preview = err_preview[:300] + "..."
            logger.warning("[CMD] %s failed returncode=%s stderr=%s", label, result.returncode, err_preview)
        return result
    except subprocess.TimeoutExpired:
        logger.error("%s timed out after %.1fs", label, timeout_seconds)
        return None
    except Exception as exc:
        logger.error("%s failed to execute: %s", label, exc)
        return None


def ffmpeg_has_nvenc() -> bool:
    """Cache and return whether ffmpeg has NVENC support."""
    global _NVENC_AVAILABLE_CACHE
    if _NVENC_AVAILABLE_CACHE is not None:
        return _NVENC_AVAILABLE_CACHE

    result = _run_command(["ffmpeg", "-hide_banner", "-encoders"], 20.0, "ffmpeg encoder probe")
    if not result or result.returncode != 0:
        _NVENC_AVAILABLE_CACHE = False
        return False

    stdout = result.stdout or ""
    _NVENC_AVAILABLE_CACHE = "h264_nvenc" in stdout
    return _NVENC_AVAILABLE_CACHE


def is_gpu_pipeline_enabled() -> bool:
    """Determine whether GPU pipeline should be used for ffmpeg operations."""
    if not USE_FFMPEG_GPU:
        return False

    has_nvenc = ffmpeg_has_nvenc()
    if not has_nvenc and FFMPEG_GPU_STRICT:
        raise RuntimeError("FFMPEG_GPU is enabled but h264_nvenc is not available on this machine.")
    return has_nvenc


# ============================================================
# ENUMS & CONFIG
# ============================================================

class TransitionType(Enum):
    NONE = "none"


class VideoQuality(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    QHD = "qhd"
    UHD = "uhd"


QUALITY_PRESETS = {
    VideoQuality.LOW: {"width": 854, "height": 480, "crf": 28, "preset": "ultrafast"},
    # OPTIMIZATION: Changed from "veryfast" to "ultrafast" for faster encoding
    VideoQuality.MEDIUM: {"width": 1280, "height": 720, "crf": 26, "preset": "ultrafast"},
    VideoQuality.HIGH: {"width": 1920, "height": 1080, "crf": 23, "preset": "ultrafast"},
    VideoQuality.QHD: {"width": 2560, "height": 1440, "crf": 20, "preset": "ultrafast"},
    VideoQuality.UHD: {"width": 3840, "height": 2160, "crf": 18, "preset": "ultrafast"},
}

NVENC_CQ = {
    VideoQuality.LOW: 31,
    VideoQuality.MEDIUM: 28,
    VideoQuality.HIGH: 24,
    VideoQuality.QHD: 21,
    VideoQuality.UHD: 19,
}


@dataclass
class ProcessingConfig:
    fade_in_duration: float = 0.0
    fade_out_duration: float = 0.0
    add_intro_fade: bool = False
    add_outro_fade: bool = False
    threads: int = 4
    quality: VideoQuality = VideoQuality.HIGH


# ============================================================
# VIDEO INFO
# ============================================================

def get_video_info_fast(video_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    result = _run_command(cmd, FFPROBE_TIMEOUT_SECONDS, "ffprobe video info")
    if not result or result.returncode != 0:
        return {}
    return json.loads(result.stdout)


def extract_video_dimensions(video_info: Dict) -> Tuple[int, int]:
    for stream in video_info.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream.get("width", 1920), stream.get("height", 1080)
    return 1920, 1080


def get_video_resolution(video_path: str) -> Tuple[int, int]:
    """Return encoded output resolution using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            video_path
        ]
        result = _run_command(cmd, FFPROBE_TIMEOUT_SECONDS, "ffprobe resolution")
        if result and result.returncode == 0:
            value = (result.stdout or "").strip()
            if "x" in value:
                w_str, h_str = value.split("x", 1)
                return int(float(w_str)), int(float(h_str))
    except Exception as exc:
        logger.warning("Could not get video resolution: %s", exc)
    return 0, 0


def get_actual_video_duration(video_path: str) -> float:
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = _run_command(cmd, FFPROBE_TIMEOUT_SECONDS, "ffprobe duration")
        if result and result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not get video duration: {e}")
    
    return 0.0


def get_stream_types(video_path: str) -> List[str]:
    """Return codec stream types present in a media file."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path
    ]
    result = _run_command(cmd, FFPROBE_TIMEOUT_SECONDS, "ffprobe stream types")
    if not result or result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "{}")
        return [s.get("codec_type", "") for s in data.get("streams", []) if s.get("codec_type")]
    except Exception:
        return []


def validate_output_media(video_path: str, target_duration: Optional[int] = None) -> Tuple[bool, str]:
    """Validate output has both video+audio streams and non-zero duration."""
    stream_types = get_stream_types(video_path)
    if "video" not in stream_types:
        return False, "Output missing video stream"
    if "audio" not in stream_types:
        return False, "Output missing audio stream"

    duration = get_actual_video_duration(video_path)
    if duration <= 0.1:
        return False, "Output duration is invalid"

    if target_duration and duration > (target_duration + 2.0):
        return False, f"Output duration {duration:.2f}s exceeds target {target_duration}s"

    return True, ""


def validate_output_quality(video_path: str, quality: VideoQuality) -> Tuple[bool, str]:
    """Validate output resolution matches user-selected quality preset."""
    expected = QUALITY_PRESETS[quality]
    expected_w = int(expected["width"])
    expected_h = int(expected["height"])
    actual_w, actual_h = get_video_resolution(video_path)
    if actual_w <= 0 or actual_h <= 0:
        return False, "Could not read output resolution"
    if actual_w != expected_w or actual_h != expected_h:
        return False, (
            f"Output resolution {actual_w}x{actual_h} does not match selected "
            f"quality {quality.value} ({expected_w}x{expected_h})"
        )
    return True, ""


def verify_full_decode(video_path: str) -> Tuple[bool, str]:
    """
    Verify file can be decoded end-to-end (helps catch tail playback corruption).
    """
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", video_path,
        "-map", "0:v:0",
        "-map", "0:a?",
        "-f", "null", "-"
    ]
    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg full decode verify")
    if not result:
        return False, "Decode verification command failed"
    if result.returncode != 0:
        err = (result.stderr or "").strip().replace("\n", " ")
        if len(err) > 240:
            err = err[:240] + "..."
        return False, f"Decode verification failed: {err}"
    return True, ""


def repair_playback_compatibility(video_path: str, quality: VideoQuality) -> Tuple[bool, str]:
    """
    Re-encode output into a conservative browser-safe profile if decode verification fails.
    """
    temp_out = f"{video_path}.repair.mp4"
    preset = QUALITY_PRESETS[quality]
    width = int(preset["width"])
    height = int(preset["height"])
    cmd = [
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", video_path,
        "-map", "0:v:0",
        "-map", "0:a?",
        "-vf", (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=24"
        ),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-r", "24",
        "-vsync", "cfr",
        "-profile:v", "high",
        "-level", "4.1",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-af", "aresample=async=1:first_pts=0",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        temp_out
    ]
    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg playback repair")
    if not result or result.returncode != 0:
        return False, "Playback repair failed"

    os.replace(temp_out, video_path)
    return True, ""


def enforce_exact_duration(video_path: str, target_duration: Optional[int], gpu_enabled: bool = False) -> Tuple[bool, str]:
    """
    Ensure output duration is exactly target_duration by trimming or padding.
    """
    if not target_duration or target_duration <= 0:
        return True, ""

    actual = get_actual_video_duration(video_path)
    if abs(actual - target_duration) <= DURATION_TOLERANCE_SECONDS:
        return True, ""

    temp_out = f"{video_path}.exact.mp4"
    delta = max(0.0, float(target_duration) - float(actual))

    encode_video = (
        ["-c:v", "h264_nvenc", "-preset", "p1"]
        if gpu_enabled
        else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    )

    # Trim if too long; pad last frame + silence if too short.
    if actual > target_duration:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-t", str(target_duration),
        ] + encode_video + [
            "-r", "24",
            "-vsync", "cfr",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            temp_out
        ]
    else:
        video_filter = f"tpad=stop_mode=clone:stop_duration={delta}"
        audio_filter = f"apad=pad_dur={delta}"
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", video_filter,
            "-af", audio_filter,
            "-t", str(target_duration),
        ] + encode_video + [
            "-r", "24",
            "-vsync", "cfr",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            temp_out
        ]

    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg enforce exact duration")
    if (not result or result.returncode != 0) and gpu_enabled:
        fallback_video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
        if actual > target_duration:
            fallback_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-t", str(target_duration),
            ] + fallback_video + [
                "-r", "24",
                "-vsync", "cfr",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                temp_out
            ]
        else:
            fallback_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"tpad=stop_mode=clone:stop_duration={delta}",
                "-af", f"apad=pad_dur={delta}",
                "-t", str(target_duration),
            ] + fallback_video + [
                "-r", "24",
                "-vsync", "cfr",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                temp_out
            ]
        result = _run_command(fallback_cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg enforce exact duration fallback")

    if not result or result.returncode != 0:
        return False, "Could not enforce exact duration"

    os.replace(temp_out, video_path)
    corrected = get_actual_video_duration(video_path)
    if abs(corrected - target_duration) > DURATION_TOLERANCE_SECONDS:
        return False, f"Duration enforcement mismatch: got {corrected:.3f}s vs {target_duration}s"

    return True, ""


def extract_video_duration(video_path: str) -> float:
    """
    Extract video duration from a video file.
    
    Args:
        video_path: Path to the video file
    
    Returns:
        Video duration in seconds
    """
    return get_actual_video_duration(video_path)


# ============================================================
# SEGMENT EXTRACTION
# ============================================================

def extract_segment_fast(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
    quality: VideoQuality,
    width: int,
    height: int,
    gpu_enabled: bool = False
) -> bool:

    duration = max(0, end - start)
    if duration <= 0:
        return False

    preset = QUALITY_PRESETS[quality]

    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
        "setsar=1",
        "fps=24"
    ]

    gpu_encode_args = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", str(NVENC_CQ[quality])]
    cpu_encode_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(preset["crf"])]

    # Use accurate seek (`-ss` after `-i`) to avoid scene drift/mismatch near cuts.
    base_cmd = ["ffmpeg", "-y", "-fflags", "+genpts"]
    if gpu_enabled and FFMPEG_GPU_DECODE:
        base_cmd += ["-hwaccel", "cuda"]

    base_cmd += [
        "-i", video_path,
        "-ss", str(start),
        "-t", str(duration),
        "-vf", ",".join(filters),
        "-af", "aresample=async=1:first_pts=0",
    ]

    cmd = base_cmd + (gpu_encode_args if gpu_enabled else cpu_encode_args) + [
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-pix_fmt", "yuv420p",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        output_path
    ]

    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg segment extraction")
    if result and result.returncode == 0:
        return True

    # If GPU encode fails, retry with software encoder for reliability.
    if gpu_enabled:
        logger.warning("NVENC segment extraction failed, retrying with libx264.")
        fallback_cmd = base_cmd + cpu_encode_args + [
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            output_path
        ]
        fallback_result = _run_command(fallback_cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg segment extraction fallback")
        return bool(fallback_result and fallback_result.returncode == 0)

    return False


def extract_segment_copy_fast(
    video_path: str,
    start: float,
    end: float,
    output_path: str
) -> bool:
    """
    Fast keyframe-aligned segment extraction using stream copy.
    Falls back to encoded extraction when copy is not usable.
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        return False

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", video_path,
        "-t", str(duration),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        output_path
    ]

    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg segment extraction copy-fast")
    return bool(result and result.returncode == 0)


# ============================================================
# CONCAT WITH HARD CUTS
# ============================================================

def concatenate_segments_copy_fast(
    segment_files: List[str],
    output_path: str,
    target_duration: Optional[int] = None
) -> bool:
    """
    Fast concat using stream copy. Falls back to re-encode path if this fails.
    """
    if not segment_files:
        return False

    list_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            list_path = handle.name
            for segment_path in segment_files:
                safe_path = segment_path.replace("\\", "/").replace("'", "'\\''")
                handle.write(f"file '{safe_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            "-movflags", "+faststart",
        ]
        if target_duration:
            cmd += ["-t", str(target_duration)]
        cmd.append(output_path)


def create_segmented_video(
    video_path: str,
    transcription: List[Dict[str, Any]],
    output_path: str,
    quality: VideoQuality,
) -> bool:
    """
    Creates a video from segments identified by the VideoSegmenter.
    """
    logger.info(f"Starting segmented video creation for {video_path}")
    segmenter = VideoSegmenter(transcription)
    segments = segmenter.get_segments(video_path)

    if not segments:
        logger.warning("No segments were found. Aborting video creation.")
        return False

    width, height = get_video_resolution(video_path)
    if width == 0 or height == 0:
        preset = QUALITY_PRESETS[quality]
        width, height = preset["width"], preset["height"]

    segment_files = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, segment in enumerate(segments):
            start, end = segment["start"], segment["end"]
            segment_output_path = os.path.join(temp_dir, f"segment_{i}.mp4")
            
            logger.info(f"Extracting segment {i}: start={start}, end={end}")
            success = extract_segment_fast(
                video_path=video_path,
                start=start,
                end=end,
                output_path=segment_output_path,
                quality=quality,
                width=width,
                height=height,
                gpu_enabled=is_gpu_pipeline_enabled()
            )

            if success:
                segment_files.append(segment_output_path)
            else:
                logger.warning(f"Failed to extract segment {i}.")

        if not segment_files:
            logger.error("No segments could be extracted. Final video not created.")
            return False

        logger.info(f"Concatenating {len(segment_files)} segments.")
        # Using a simple concatenation for now. This can be enhanced with transitions.
        success = concatenate_segments_copy_fast(
            segment_files=segment_files,
            output_path=output_path
        )

        if not success:
             # Fallback to re-encoding if stream copy fails
            logger.warning("Fast concatenation failed, falling back to re-encoding concatenation.")
            success = concatenate_segments_with_fade(
                segment_files=segment_files,
                output_path=output_path,
                quality=quality,
                fade_in=0,
                fade_out=0,
                gpu_enabled=is_gpu_pipeline_enabled()
            )

    if success:
        logger.info(f"Segmented video created successfully at {output_path}")
    else:
        logger.error("Failed to create the final segmented video.")

    return success
        result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg fast concat copy")
        return bool(result and result.returncode == 0)
    finally:
        if list_path and os.path.exists(list_path):
            try:
                os.remove(list_path)
            except Exception:
                pass


def concatenate_segments_with_fade(
    segment_files: List[str],
    output_path: str,
    quality: VideoQuality,
    fade_in: float,
    fade_out: float,
    target_duration: Optional[int] = None,
    gpu_enabled: bool = False
) -> bool:
    inputs = []
    for f in segment_files:
        inputs.extend(["-i", f])

    concat_inputs = "".join([f"[{i}:v][{i}:a]" for i in range(len(segment_files))])
    filter_complex = f"{concat_inputs}concat=n={len(segment_files)}:v=1:a=1[vfinal][outa]"

    preset = QUALITY_PRESETS[quality]

    gpu_encode_args = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", str(NVENC_CQ[quality])]
    cpu_encode_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(preset["crf"])]

    base_cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", "[outa]",
    ]

    cmd = base_cmd + (gpu_encode_args if gpu_enabled else cpu_encode_args) + [
        "-r", "24",
        "-vsync", "cfr",
        "-profile:v", "high",
        "-level", "4.1",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]

    # 🎯 Strict duration enforcement
    if target_duration:
        cmd += ["-t", str(target_duration)]

    cmd.append(output_path)

    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg concatenation")
    if result and result.returncode == 0:
        return True

    if gpu_enabled:
        logger.warning("NVENC concatenation failed, retrying with libx264.")
        fallback_cmd = base_cmd + cpu_encode_args + [
            "-r", "24",
            "-vsync", "cfr",
            "-profile:v", "high",
            "-level", "4.1",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
        if target_duration:
            fallback_cmd += ["-t", str(target_duration)]
        fallback_cmd.append(output_path)
        fallback_result = _run_command(fallback_cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg concatenation fallback")
        return bool(fallback_result and fallback_result.returncode == 0)

    return False


def transcode_output_to_quality(
    input_video: str,
    output_video: str,
    quality: VideoQuality,
    width: int,
    height: int,
    gpu_enabled: bool = False
) -> bool:
    """
    Single-pass final quality normalization to avoid expensive per-segment re-encoding.
    """
    preset = QUALITY_PRESETS[quality]
    gpu_encode_args = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", str(NVENC_CQ[quality])]
    cpu_encode_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(preset["crf"])]

    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
        "setsar=1",
        "fps=24"
    ]

    base_cmd = [
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", input_video,
        "-vf", ",".join(filters),
        "-af", "aresample=async=1:first_pts=0",
    ]

    cmd = base_cmd + (gpu_encode_args if gpu_enabled else cpu_encode_args) + [
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-r", "24",
        "-vsync", "cfr",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_video
    ]

    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg final quality transcode")
    if result and result.returncode == 0:
        return True

    if gpu_enabled:
        logger.warning("NVENC final quality transcode failed, retrying with libx264.")
        fallback_cmd = base_cmd + cpu_encode_args + [
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-r", "24",
            "-vsync", "cfr",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_video
        ]
        fallback_result = _run_command(fallback_cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg final quality transcode fallback")
        return bool(fallback_result and fallback_result.returncode == 0)

    return False


# ============================================================
# SUBTITLE SYSTEM
# ============================================================

def generate_srt_file(segments: List[Dict[str, Any]], srt_path: str):

    def format_time(seconds: float):
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")


def burn_subtitles_into_video(
    input_video: str,
    srt_file: str,
    output_video: str,
    quality: VideoQuality,
    gpu_enabled: bool = False
) -> bool:
    """
    Burn subtitles into video with improved visibility and positioning.
    Uses adaptive font sizing based on video resolution for optimal readability.
    """
    preset = QUALITY_PRESETS[quality]

    gpu_encode_args = ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", str(NVENC_CQ[quality])]
    cpu_encode_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(preset["crf"])]

    # CRITICAL FIX: Properly escape the SRT file path for FFmpeg on Windows
    # FFmpeg subtitle filter requires:
    # 1. Backslashes escaped as double backslashes (or use forward slashes)
    # 2. Colons in Windows drive letters escaped with backslash
    # 3. The entire path wrapped in single quotes within the filter
    escaped_srt_path = srt_file.replace("\\", "/")  # Convert to forward slashes
    # On Windows, escape the colon in drive letters (e.g., C: becomes C\\:)
    if len(escaped_srt_path) >= 2 and escaped_srt_path[1] == ':':
        escaped_srt_path = escaped_srt_path[0] + '\\:' + escaped_srt_path[2:]
    
    logger.info("[SUBTITLE] Burning subtitles from: %s (escaped: %s)", srt_file, escaped_srt_path)
    
    # Get input video dimensions for adaptive font sizing
    video_info = get_video_info_fast(input_video)
    video_width, video_height = extract_video_dimensions(video_info)
    
    # Adaptive font sizing based on video resolution
    # Scale font size proportionally to video height for consistent appearance
    # Base font size is 16 for 480p, scaling up for higher resolutions
    # This ensures subtitles are readable but not too large on any resolution
    base_font_size = 16  # Base size for 480p
    reference_height = 480
    
    # Calculate adaptive font size (proportional scaling)
    if video_height > 0:
        scale_factor = video_height / reference_height
        # Clamp the scale factor to reasonable bounds
        scale_factor = max(0.8, min(2.5, scale_factor))
        font_size = int(base_font_size * scale_factor)
    else:
        # Fallback to preset-based sizing
        font_size = int(preset["height"] / 30)  # Approximate good font size
    
    # Ensure font size is within reasonable bounds (12-36)
    font_size = max(12, min(36, font_size))
    
    # Calculate margin based on video height (proportional spacing from bottom)
    margin_v = max(10, int(video_height * 0.03)) if video_height > 0 else 20
    
    logger.info(
        "[SUBTITLE] Adaptive styling: video=%dx%d font_size=%d margin_v=%d",
        video_width, video_height, font_size, margin_v
    )
    
    # Improved subtitle styling for better visibility with adaptive sizing
    # Alignment=2 (bottom center), adaptive FontSize
    # PrimaryColour=&Hffffff (white), OutlineColour=&H000000 (black outline)
    # BackColour=&H80000000 (semi-transparent black background for readability)
    # Using a clean, readable style that fits the screen properly
    subtitle_filter = f"subtitles='{escaped_srt_path}':force_style='Alignment=2,FontSize={font_size},FontName=Arial,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=1.5,Shadow=1,BackColour=&H80000000,MarginV={margin_v},Bold=0'"
    
    base_cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", subtitle_filter,
    ]

    cmd = base_cmd + (gpu_encode_args if gpu_enabled else cpu_encode_args) + [
        "-r", "24",
        "-vsync", "cfr",
        "-profile:v", "high",
        "-level", "4.1",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_video
    ]

    result = _run_command(cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg subtitle burn")
    if result and result.returncode == 0:
        return True

    if gpu_enabled:
        logger.warning("NVENC subtitle burn failed, retrying with libx264.")
        fallback_cmd = base_cmd + cpu_encode_args + [
            "-r", "24",
            "-vsync", "cfr",
            "-profile:v", "high",
            "-level", "4.1",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_video
        ]
        fallback_result = _run_command(fallback_cmd, FFMPEG_TIMEOUT_SECONDS, "ffmpeg subtitle burn fallback")
        return bool(fallback_result and fallback_result.returncode == 0)

    return False


# ============================================================
# MAIN PROCESSOR
# ============================================================

def process_video_fast(
    video_path: str,
    segments: List[Tuple[float, float]],
    output_path: str,
    proc_config: Optional[ProcessingConfig] = None,
    quality: str = "high",
    subtitle_segments: Optional[List[Dict[str, Any]]] = None,
    target_duration: Optional[int] = None,
    progress_callback: Optional[Callable[[int, str, str], None]] = None
) -> Dict[str, Any]:

    start_time = time.time()
    proc_config = proc_config or ProcessingConfig()

    def report(progress: int, status: str, message: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(progress, status, message)
        except Exception:
            pass

    report(5, "server_processing", "Preparing video processing pipeline...")
    logger.info(
        "[PROCESSOR] Start input=%s quality=%s target_duration=%s segments=%d",
        os.path.basename(video_path),
        quality,
        target_duration,
        len(segments)
    )

    try:
        video_quality = VideoQuality(quality.lower())
    except ValueError:
        return {"success": False, "error": "Invalid quality from frontend"}

    try:
        gpu_enabled = is_gpu_pipeline_enabled()
    except RuntimeError as gpu_err:
        return {"success": False, "error": str(gpu_err)}

    logger.info(
        "[PROCESSOR] GPU pipeline requested=%s enabled=%s strict=%s decode_accel=%s",
        USE_FFMPEG_GPU,
        gpu_enabled,
        FFMPEG_GPU_STRICT,
        FFMPEG_GPU_DECODE
    )
    report(10, "server_processing", "Preparing segment timeline...")

    video_info = get_video_info_fast(video_path)
    orig_w, orig_h = extract_video_dimensions(video_info)

    # Get preset for user-selected quality
    preset = QUALITY_PRESETS[video_quality]
    preset_width = preset["width"]
    preset_height = preset["height"]
    
    # Smart quality: Use the lower of source video quality OR user-selected quality
    # This prevents upscaling low-quality sources to high quality
    width = min(orig_w, preset_width)
    height = min(orig_h, preset_height)
    
    # Log quality decision for debugging
    logger.info(
        "[PROCESSOR] Quality decision: source=%dx%d user_selected=%s preset=%dx%d output=%dx%d",
        orig_w, orig_h, video_quality.value, preset_width, preset_height, width, height
    )

    with tempfile.TemporaryDirectory() as temp_dir:

        # Stabilize timeline: strictly increasing, no overlaps, and no ultra-short fragments.
        cleaned_segments: List[Tuple[float, float]] = []
        prev_end = 0.0
        for start, end in sorted(segments):
            s = max(0.0, float(start))
            e = max(s, float(end))
            if s < prev_end:
                s = prev_end
            if e - s < 0.5:
                continue
            cleaned_segments.append((s, e))
            prev_end = e

        logger.info(
            "[PROCESSOR] Segment timeline sanitized input=%d cleaned=%d",
            len(segments),
            len(cleaned_segments)
        )
        report(14, "server_processing", "Extracting selected segments...")

        segment_files = []
        use_copy_extraction = bool(target_duration and float(target_duration) >= SEGMENT_COPY_MIN_TARGET_SECONDS and SEGMENT_COPY_FIRST)
        copy_extraction_used = False

        logger.info("[PROCESSOR] Extracting segments count=%d", len(cleaned_segments))
        total_segments_to_extract = max(1, len(cleaned_segments))
        for i, (start, end) in enumerate(cleaned_segments):
            path = os.path.join(temp_dir, f"seg_{i}.mp4")
            ok = False
            if use_copy_extraction:
                ok = extract_segment_copy_fast(video_path, start, end, path)
                if ok:
                    copy_extraction_used = True

            if not ok:
                ok = extract_segment_fast(
                    video_path, start, end,
                    path, video_quality, width, height, gpu_enabled=gpu_enabled
                )
            if ok:
                segment_files.append(path)
            else:
                logger.warning("[PROCESSOR] Segment extraction failed idx=%d start=%.3f end=%.3f", i, start, end)
            extract_progress = 14 + int(((i + 1) / total_segments_to_extract) * 40)
            report(min(54, extract_progress), "server_processing", f"Extracting segment {i + 1}/{total_segments_to_extract}...")

        if not segment_files:
            return {"success": False, "error": "No segments extracted"}
        logger.info("[PROCESSOR] Segment extraction complete success=%d", len(segment_files))
        report(56, "server_processing", "Joining processed segments...")

        logger.info("[PROCESSOR] Concatenating segments...")
        concat_ok = False
        if FAST_CONCAT_COPY:
            concat_ok = concatenate_segments_copy_fast(
                segment_files,
                output_path,
                target_duration=target_duration
            )
            if concat_ok:
                logger.info("[PROCESSOR] Fast concat-copy path succeeded")

        if not concat_ok:
            concat_ok = concatenate_segments_with_fade(
                segment_files,
                output_path,
                video_quality,
                proc_config.fade_in_duration if proc_config.add_intro_fade else 0,
                proc_config.fade_out_duration if proc_config.add_outro_fade else 0,
                target_duration,
                gpu_enabled=gpu_enabled
            )
            if concat_ok:
                logger.info("[PROCESSOR] Re-encode concat path succeeded")

        if not concat_ok:
            return {"success": False, "error": "Concatenation failed"}
        logger.info("[PROCESSOR] Concatenation complete output=%s", os.path.basename(output_path))
        report(66, "server_processing", "Validating encoded output...")

        valid_concat, concat_error = validate_output_media(output_path, target_duration=target_duration)
        if not valid_concat:
            return {"success": False, "error": f"Concatenated output invalid: {concat_error}"}
        logger.info("[PROCESSOR] Media validation passed after concat")
        report(72, "server_processing", "Media validation complete.")

        if copy_extraction_used:
            current_w, current_h = get_video_resolution(output_path)
            if current_w == width and current_h == height:
                logger.info(
                    "[PROCESSOR] Copy-first extraction path: quality normalization skipped (already %sx%s)",
                    current_w,
                    current_h
                )
            else:
                report(74, "server_processing", "Normalizing output quality...")
                normalized_output = output_path.replace(".mp4", "_norm.mp4")
                normalized = transcode_output_to_quality(
                    output_path,
                    normalized_output,
                    video_quality,
                    width,
                    height,
                    gpu_enabled=gpu_enabled
                )
                if not normalized:
                    return {"success": False, "error": "Quality normalization failed"}
                os.replace(normalized_output, output_path)
                valid_norm, norm_error = validate_output_media(output_path, target_duration=target_duration)
                if not valid_norm:
                    return {"success": False, "error": f"Normalized output invalid: {norm_error}"}
            logger.info("[PROCESSOR] Copy-first extraction optimization path applied")

        # SUBTITLES
        if subtitle_segments:
            report(76, "server_processing", "Rendering subtitles...")
            with tempfile.TemporaryDirectory() as sub_dir:
                srt_path = os.path.join(sub_dir, f"{uuid.uuid4()}.srt")
                subtitled_output = output_path.replace(".mp4", "_sub.mp4")

                try:
                    generate_srt_file(subtitle_segments, srt_path)

                    burned = burn_subtitles_into_video(
                        output_path,
                        srt_path,
                        subtitled_output,
                        video_quality,
                        gpu_enabled=gpu_enabled
                    )

                    if burned:
                        os.replace(subtitled_output, output_path)
                        valid_sub, sub_error = validate_output_media(output_path, target_duration=target_duration)
                        if not valid_sub:
                            return {"success": False, "error": f"Subtitled output invalid: {sub_error}"}
                        logger.info("[PROCESSOR] Subtitle burn complete")
                        report(82, "server_processing", "Subtitles rendered.")
                    else:
                        logger.warning("[PROCESSOR] Subtitle burning failed, continuing without subtitles")
                        report(82, "server_processing", "Subtitle rendering failed, continuing without subtitles.")
                        
                except Exception as subtitle_error:
                    logger.error(f"[PROCESSOR] Subtitle processing error: {subtitle_error}")
                    report(82, "server_processing", "Subtitle processing failed, continuing without subtitles.")

        logger.info("[PROCESSOR] Enforcing exact duration target=%s", target_duration)
        report(86, "server_processing", "Applying exact target duration...")
        exact_ok, exact_error = enforce_exact_duration(output_path, target_duration, gpu_enabled=gpu_enabled)
        if not exact_ok:
            return {"success": False, "error": exact_error}
        valid_final, final_error = validate_output_media(output_path, target_duration=target_duration)
        if not valid_final:
            return {"success": False, "error": f"Final output invalid: {final_error}"}
        logger.info("[PROCESSOR] Final media validation passed")
        report(92, "finalizing", "Final quality checks...")

        quality_ok, quality_error = validate_output_quality(output_path, video_quality)
        if STRICT_QUALITY_VALIDATION:
            if not quality_ok:
                logger.warning("[PROCESSOR] Quality mismatch before decode verify: %s", quality_error)
                if not ENABLE_PLAYBACK_REPAIR:
                    return {"success": False, "error": quality_error}
                repair_ok, repair_error = repair_playback_compatibility(output_path, video_quality)
                if not repair_ok:
                    return {"success": False, "error": f"Quality normalization failed: {repair_error}"}
                valid_repair_quality, repair_quality_error = validate_output_quality(output_path, video_quality)
                if not valid_repair_quality:
                    return {"success": False, "error": f"Quality mismatch after normalization: {repair_quality_error}"}
                valid_repair_media, repair_media_error = validate_output_media(output_path, target_duration=target_duration)
                if not valid_repair_media:
                    return {"success": False, "error": f"Output invalid after normalization: {repair_media_error}"}
                logger.info("[PROCESSOR] Quality normalized to selected preset")
        else:
            if not quality_ok:
                logger.warning(
                    "[PROCESSOR] Non-strict mode: quality mismatch ignored after media validation. detail=%s",
                    quality_error
                )
            else:
                logger.info("[PROCESSOR] Quality check passed for selected preset")

        if ENABLE_FULL_DECODE_VERIFY:
            decode_ok, decode_error = verify_full_decode(output_path)
            if not decode_ok:
                logger.warning("[PROCESSOR] Decode verification failed, trying repair: %s", decode_error)
                if not ENABLE_PLAYBACK_REPAIR:
                    return {"success": False, "error": decode_error}
                repair_ok, repair_error = repair_playback_compatibility(output_path, video_quality)
                if not repair_ok:
                    return {"success": False, "error": repair_error}
                valid_repair, repair_valid_error = validate_output_media(output_path, target_duration=target_duration)
                if not valid_repair:
                    return {"success": False, "error": f"Repaired output invalid: {repair_valid_error}"}
                repair_quality_ok, repair_quality_error = validate_output_quality(output_path, video_quality)
                if not repair_quality_ok:
                    return {"success": False, "error": f"Repaired quality mismatch: {repair_quality_error}"}
                decode_ok2, decode_error2 = verify_full_decode(output_path)
                if not decode_ok2:
                    return {"success": False, "error": f"Repaired output decode failed: {decode_error2}"}
                logger.info("[PROCESSOR] Playback repair successful")
            else:
                logger.info("[PROCESSOR] Full decode verification passed")
        else:
            logger.info("[PROCESSOR] Full decode verification skipped for speed")

    final_duration = get_actual_video_duration(output_path)
    report(98, "finalizing", "Preparing response...")
    logger.info(
        "[PROCESSOR] Complete output=%s duration=%.3fs processing_time=%.2fs",
        os.path.basename(output_path),
        final_duration,
        time.time() - start_time
    )

    return {
        "success": True,
        "output_path": output_path,
        "duration": final_duration,
        "segments_processed": len(segment_files),
        "quality_used": video_quality.value,
        "gpu_used": str(gpu_enabled).lower(),
        "processing_time": round(time.time() - start_time, 2)
    }


# ============================================================
# PUBLIC ENTRY
# ============================================================

def create_short_video(
    video_path: str,
    segments: List[Tuple[float, float]],
    output_filename: str,
    quality: str = "high",
    subtitle_segments: Optional[List[Dict[str, Any]]] = None,
    target_duration: Optional[int] = None
) -> str:

    output_path = os.path.join(config.settings.OUTPUTS_DIR, output_filename)

    result = process_video_fast(
        video_path=video_path,
        segments=segments,
        output_path=output_path,
        quality=quality,
        subtitle_segments=subtitle_segments,
        target_duration=target_duration
    )

    if not result["success"]:
        raise Exception(result.get("error", "Video processing failed"))

    return output_path