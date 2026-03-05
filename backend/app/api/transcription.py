# backend/app/api/transcription.py

from fastapi import APIRouter, HTTPException
from pathlib import Path
import os
from ..models import schemas
from ..services.audio_extractor import extract_audio_from_video
from ..services.whisper_service import transcribe_audio
from ..services.whisper_service import whisper_service
from ..services.transcription_cache import transcription_cache
from ..services.subtitle_extractor import (
    has_embedded_subtitles,
    extract_and_parse_subtitles,
    subtitles_to_transcription_format,
    generate_subtitles_for_video,
    write_youtube_style_srt,
    write_vtt,
    convert_to_multiple_languages
)
from ..core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
USE_LLM_SUMMARY = os.getenv("USE_LLM_SUMMARY", "false").strip().lower() in ("1", "true", "yes")
FFPROBE_TIMEOUT_SECONDS = float(os.getenv("FFPROBE_TIMEOUT_SECONDS", "20"))


@router.get("/transcribe-runtime")
async def get_transcribe_runtime():
    """Return active Whisper runtime details (device + compute type)."""
    return whisper_service.get_runtime_info()


def get_video_info(video_path: str) -> tuple:
    """Get video duration and file size."""
    import subprocess
    import json
    
    file_size = os.path.getsize(video_path)
    
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info.get("format", {}).get("duration", 0))
            return duration, file_size
    except Exception as e:
        logger.warning(f"Could not get video info: {e}")
    
    return 0, file_size


def generate_video_review(transcription_data: dict) -> str:
    """
    Generate a detailed video review/summary from transcription data.
    """
    text = transcription_data.get("text", "")
    segments = transcription_data.get("segments", [])
    language = transcription_data.get("language", "unknown")
    
    if not text or len(text.strip()) < 20:
        return "This video appears to have minimal or no speech content."
    
    # Calculate video statistics
    total_segments = len(segments)
    if segments:
        duration = segments[-1].get("end", 0)
        duration_min = int(duration // 60)
        duration_sec = int(duration % 60)
    else:
        duration_min = 0
        duration_sec = 0
    
    # Language name mapping
    language_names = {
        "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu",
        "ml": "Malayalam", "kn": "Kannada", "es": "Spanish", "fr": "French",
        "de": "German", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
        "ar": "Arabic", "pt": "Portuguese", "ru": "Russian", "it": "Italian"
    }
    language_name = language_names.get(language, language.upper())
    
    # Fast path summary by default (no heavy model load).
    summary = ""
    if USE_LLM_SUMMARY:
        try:
            from ..services.summarizer_service import summarizer_service
            summary = summarizer_service.summarize(text)
        except Exception as e:
            logger.warning(f"LLM summary unavailable, using fast summary: {e}")

    if not summary or "not available" in summary.lower() or "failed" in summary.lower():
        cleaned_text = " ".join(text.split())
        summary = cleaned_text[:500] + ("..." if len(cleaned_text) > 500 else "")
    
    # Build the review
    review_parts = [
        f"📹 **Video Overview**",
        f"Duration: {duration_min}m {duration_sec}s | Language: {language_name}",
        f"",
        f"📝 **Content Summary**",
        summary,
    ]
    
    # Add key topics if we have segments
    if total_segments > 3:
        # Extract key phrases from first few segments
        key_phrases = []
        for seg in segments[:5]:
            seg_text = seg.get("text", "").strip()
            if seg_text and len(seg_text) > 10:
                # Get first meaningful phrase
                words = seg_text.split()
                if len(words) > 3:
                    phrase = " ".join(words[:8])
                    if phrase not in key_phrases:
                        key_phrases.append(phrase)
        
        if key_phrases:
            review_parts.append("")
            review_parts.append("🔑 **Key Topics Discussed**")
            for i, phrase in enumerate(key_phrases[:3], 1):
                review_parts.append(f"{i}. {phrase}...")
    
    return "\n".join(review_parts)


@router.post("/transcribe", response_model=schemas.TranscriptionResponse)
async def transcribe_video(request: schemas.TranscriptionRequest):
    """
    Transcribe video audio using Whisper and generate a video review.
    Results are cached for reuse in video processing.
    
    NEW: First checks for embedded subtitles to avoid re-transcription.
    """

    file_id = request.file_id
    logger.info("[TRANSCRIBE] Start file_id=%s", file_id)

    try:
        def build_response(transcription_data: dict, review_text: str) -> schemas.TranscriptionResponse:
            payload = transcription_data if isinstance(transcription_data, dict) else {
                "text": str(transcription_data or ""),
                "segments": []
            }

            text = str((payload or {}).get("text", "") or "")
            segments = (payload or {}).get("segments", []) or []
            safe_segments = segments if isinstance(segments, list) else []

            language = str((payload or {}).get("language", "unknown") or "unknown")
            confidence_raw = (payload or {}).get("confidence", None)
            try:
                confidence = float(confidence_raw) if confidence_raw is not None else None
            except (TypeError, ValueError):
                confidence = None

            duration = 0.0
            if safe_segments:
                try:
                    duration = float(safe_segments[-1].get("end", 0) or 0)
                except (TypeError, ValueError, AttributeError):
                    duration = 0.0

            normalized_text = text.strip()
            word_count = len(normalized_text.split()) if normalized_text else 0

            return schemas.TranscriptionResponse(
                transcription=review_text,
                text=normalized_text,
                segments=safe_segments,
                duration=duration,
                language=language,
                confidence=confidence,
                wordCount=word_count
            )

        # --------------------------------------------------
        # 1️⃣ Check for cached transcription first
        # --------------------------------------------------
        cached_result = transcription_cache.load(file_id)
        if cached_result:
            logger.info(f"Using cached transcription for {file_id}")
            logger.info("[TRANSCRIBE] Cache hit file_id=%s", file_id)
            
            # Generate video review instead of raw transcript
            video_review = generate_video_review(cached_result)
            
            return build_response(cached_result, video_review)

        # --------------------------------------------------
        # 2️⃣ Find uploaded video dynamically
        # --------------------------------------------------
        matching_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))

        if not matching_files:
            raise HTTPException(status_code=404, detail="Video file not found")

        video_path = matching_files[0]
        logger.info("[TRANSCRIBE] Video located file_id=%s path=%s", file_id, video_path.name)
        
        # Get video info for auto model selection
        video_duration, video_file_size = get_video_info(str(video_path))
        logger.info(f"Video duration: {video_duration:.1f}s, size: {video_file_size / (1024*1024):.1f}MB")

        # --------------------------------------------------
        # 3️⃣ NEW: Check for embedded subtitles first
        # --------------------------------------------------
        if has_embedded_subtitles(str(video_path)):
            logger.info(f"🎬 Found embedded subtitles in video, extracting...")
            
            subtitle_path, subtitle_segments = extract_and_parse_subtitles(
                str(video_path),
                str(settings.AUDIO_DIR),
                language="en"  # Prefer English subtitles
            )
            
            if subtitle_segments:
                logger.info(f"✅ Extracted {len(subtitle_segments)} subtitle segments")
                
                # Convert to transcription format
                result = subtitles_to_transcription_format(
                    subtitle_segments,
                    video_duration=video_duration
                )
                
                # Cache the result
                transcription_cache.save(file_id, result)
                
                # Generate video review
                video_review = generate_video_review(result)
                
                return build_response(
                    result,
                    video_review + "\n\n[Subtitles extracted from video file]"
                )
            
            logger.info("Could not extract usable subtitles, falling back to transcription")

        # --------------------------------------------------
        # 4️⃣ Check for existing audio file (may exist from previous attempt)
        # --------------------------------------------------
        audio_path = None
        for ext in ['.wav', '.mp3']:
            potential_path = settings.AUDIO_DIR / f"{file_id}_audio{ext}"
            if potential_path.exists():
                audio_path = str(potential_path)
                logger.info(f"Found existing audio file: {audio_path}")
                break
        
        # Extract audio if not found
        if not audio_path:
            logger.info("[TRANSCRIBE] Extracting audio file_id=%s", file_id)
            audio_filename = f"{file_id}_audio.wav"
            audio_path = extract_audio_from_video(
                str(video_path),
                audio_filename
            )
        logger.info("[TRANSCRIBE] Audio ready file_id=%s path=%s", file_id, Path(audio_path).name)

        # --------------------------------------------------
        # 5️⃣ Transcribe using Whisper with auto model selection
        # --------------------------------------------------
        # REQUIREMENT: Transcripts must always be in English
        # The transcribe_audio function defaults to English output
        logger.info(f"Starting transcription for {file_id}...")
        logger.info(
            "[TRANSCRIBE] Runtime file_id=%s target_language=en",
            file_id
        )
        result = transcribe_audio(
            audio_path,
            video_duration=video_duration,
            video_file_size=video_file_size,
            translate_to_english=True,  # Always translate to English
            target_language="en"  # Ensure English output
        )

        # Check if no speech was detected
        if result.get("no_speech_detected", False):
            logger.warning(f"No speech detected in video {file_id}")
            # Cache the empty result to avoid re-processing
            transcription_cache.save(file_id, result)
            return build_response(
                result,
                "This video appears to contain only music or non-speech audio. No dialogue was detected for analysis."
            )

        # Whisper returns dict → extract text safely
        if isinstance(result, dict):
            transcription_text = result.get("text", "")
        else:
            transcription_text = str(result)

        if not transcription_text or transcription_text.strip() == "":
            logger.warning(f"Empty transcription for video {file_id}")
            transcription_cache.save(file_id, result)
            return build_response(result, "No speech could be transcribed from this video.")

        # --------------------------------------------------
        # 6️⃣ Cache the result for video processing
        # --------------------------------------------------
        transcription_cache.save(file_id, result)

        logger.info(f"✅ Transcription completed for {file_id}")
        logger.info(
            "[TRANSCRIBE] Complete file_id=%s text_chars=%d segments=%d",
            file_id,
            len(result.get("text", "")) if isinstance(result, dict) else len(str(result)),
            len(result.get("segments", [])) if isinstance(result, dict) else 0
        )

        # Generate video review instead of raw transcript
        video_review = generate_video_review(result)

        return build_response(result, video_review)

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )
