from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
import shutil
import os
import subprocess
import logging
import json
import time
from pathlib import Path

from ..core.config import settings
from ..models import schemas

router = APIRouter()
logger = logging.getLogger(__name__)
UPLOAD_NORMALIZE_TIMEOUT_SECONDS = int(os.getenv("UPLOAD_NORMALIZE_TIMEOUT_SECONDS", "1800"))
FFPROBE_TIMEOUT_SECONDS = int(os.getenv("FFPROBE_TIMEOUT_SECONDS", "20"))
# Use GPU if available, but fallback to CPU
USE_FFMPEG_GPU = os.getenv("USE_FFMPEG_GPU", "true").strip().lower() in ("1", "true", "yes")
FFMPEG_GPU_STRICT = os.getenv("FFMPEG_GPU_STRICT", "false").strip().lower() in ("1", "true", "yes")


def probe_media_info(input_path: Path) -> dict:
    """Return ffprobe JSON for media streams/format; empty dict on failure."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS
        )
        if result.returncode != 0 or not result.stdout:
            return {}
        return json.loads(result.stdout)
    except Exception:
        return {}


def run_ffmpeg_command(cmd: list, label: str) -> subprocess.CompletedProcess:
    logger.info("[UPLOAD] ffmpeg step=%s", label)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=UPLOAD_NORMALIZE_TIMEOUT_SECONDS
    )


def normalize_to_browser_mp4(input_path: Path, output_path: Path) -> None:
    """
    Normalize uploaded video to browser-friendly MP4 (H.264 + AAC).
    This allows broad source format support while keeping downstream stable.
    """
    started_at = time.time()

    probe = probe_media_info(input_path)
    streams = probe.get("streams", []) if isinstance(probe, dict) else []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise HTTPException(status_code=400, detail="Uploaded file does not contain a valid video stream.")

    video_codec = (video_stream.get("codec_name") or "").lower()
    pixel_format = (video_stream.get("pix_fmt") or "").lower()
    audio_codec = (audio_stream.get("codec_name") or "").lower() if audio_stream else ""

    # Fast path: avoid heavy re-encode when source is already browser-safe H.264.
    is_h264 = video_codec == "h264"
    is_420_like = pixel_format in ("", "yuv420p", "yuvj420p", "nv12")
    audio_is_aac_or_missing = (not audio_stream) or (audio_codec == "aac")

    if is_h264 and is_420_like:
        if audio_is_aac_or_missing:
            remux_copy_cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c", "copy",
                "-movflags", "+faststart",
                str(output_path),
            ]
            remux_result = run_ffmpeg_command(remux_copy_cmd, "fast_remux_copy")
            if remux_result.returncode == 0:
                logger.info("[UPLOAD] Fast remux complete elapsed=%.2fs", time.time() - started_at)
                return
            logger.warning(
                "[UPLOAD] Fast remux failed stderr=%s",
                (remux_result.stderr[:280] + "...") if len(remux_result.stderr or "") > 280 else (remux_result.stderr or "")
            )
        else:
            remux_audio_cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path),
            ]
            remux_audio_result = run_ffmpeg_command(remux_audio_cmd, "fast_remux_audio_transcode")
            if remux_audio_result.returncode == 0:
                logger.info("[UPLOAD] Fast remux+audio complete elapsed=%.2fs", time.time() - started_at)
                return
            logger.warning(
                "[UPLOAD] Fast remux+audio failed stderr=%s",
                (remux_audio_result.stderr[:280] + "...") if len(remux_audio_result.stderr or "") > 280 else (remux_audio_result.stderr or "")
            )

    # Slow path: full transcode to browser-friendly H.264/AAC.
    base_cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-map", "0:v:0",
        "-map", "0:a?",
    ]
    gpu_cmd = base_cmd + [
        "-c:v", "h264_nvenc",
        "-preset", "p1",
        "-cq", "24",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    cpu_cmd = base_cmd + [
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    # Build command plan based on GPU settings
    if USE_FFMPEG_GPU:
        if FFMPEG_GPU_STRICT:
            # GPU strict mode: only try GPU, no CPU fallback
            command_plan = [("gpu", gpu_cmd)]
        else:
            # GPU preferred mode: try GPU first, fallback to CPU
            command_plan = [("gpu", gpu_cmd), ("cpu", cpu_cmd)]
    else:
        # CPU-only mode
        command_plan = [("cpu", cpu_cmd)]

    last_stderr = ""

    for mode, cmd in command_plan:
        try:
            logger.info("[UPLOAD] Normalization attempt mode=%s", mode)
            result = run_ffmpeg_command(cmd, f"full_transcode_{mode}")
            if result.returncode == 0:
                logger.info("[UPLOAD] Normalization succeeded mode=%s elapsed=%.2fs", mode, time.time() - started_at)
                return
            last_stderr = result.stderr or ""
            logger.warning("[UPLOAD] Normalization failed mode=%s stderr=%s", mode, (last_stderr[:280] + "...") if len(last_stderr) > 280 else last_stderr)
        except subprocess.TimeoutExpired:
            logger.error("[UPLOAD] Normalization timed out mode=%s", mode)
            raise HTTPException(status_code=408, detail="Upload normalization timed out.")

    # All attempts failed
    logger.error("[UPLOAD] All normalization attempts failed. Last error: %s", last_stderr)
    raise HTTPException(
        status_code=500,
        detail=f"Video encoding failed. Could not convert your video to a browser-compatible format. Error: {last_stderr[:300]}"
    )


@router.post("/upload-video/", response_model=schemas.UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Invalid video file.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    try:
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix.lower()
        logger.info("[UPLOAD] Start file_id=%s filename=%s content_type=%s", file_id, file.filename, file.content_type)

        if not file_extension:
            raise HTTPException(status_code=400, detail="File must have extension.")

        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        raw_filename = f"{file_id}_raw{file_extension}"
        raw_location = settings.UPLOAD_DIR / raw_filename
        normalized_filename = f"{file_id}_original.mp4"
        normalized_location = settings.UPLOAD_DIR / normalized_filename

        with open(raw_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        raw_size_mb = raw_location.stat().st_size / (1024 * 1024)
        logger.info("[UPLOAD] Saved raw file_id=%s path=%s size=%.2fMB", file_id, raw_location.name, raw_size_mb)

        logger.info("[UPLOAD] Normalizing to browser MP4 file_id=%s", file_id)
        normalize_to_browser_mp4(raw_location, normalized_location)
        norm_size_mb = normalized_location.stat().st_size / (1024 * 1024)
        logger.info("[UPLOAD] Normalized file_id=%s path=%s size=%.2fMB", file_id, normalized_location.name, norm_size_mb)
        try:
            raw_location.unlink(missing_ok=True)
        except Exception:
            pass
        logger.info("[UPLOAD] Complete file_id=%s", file_id)

        return schemas.UploadResponse(
            file_id=file_id,
            message="Video uploaded successfully",
            subtitle_url=None
        )

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Upload normalization timed out.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
