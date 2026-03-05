from fastapi import APIRouter, HTTPException, BackgroundTasks
from pathlib import Path
import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from ..services.subtitle_extractor import (
    generate_subtitles_for_video,
    write_youtube_style_srt,
    write_vtt,
    convert_to_multiple_languages,
    has_embedded_subtitles,
    get_subtitle_tracks,
    extract_and_parse_subtitles,
    parse_subtitle_file,
    generate_word_level_subtitles
)
from ..core.config import settings
from ..services.transcription_cache import transcription_cache
from ..services.whisper_service import whisper_service
from ..services.audio_extractor import extract_audio_from_video
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class SubtitleRequest(BaseModel):
    file_id: str
    language: str = "en"
    max_chars_per_line: int = 42
    include_vtt: bool = True
    include_word_level: bool = False
    target_languages: Optional[List[str]] = None


class SubtitleResponse(BaseModel):
    srt_path: str
    vtt_path: Optional[str] = None
    word_level_path: Optional[str] = None
    translated_files: Dict[str, str] = {}
    message: str


class SubtitleStatus(BaseModel):
    file_id: str
    has_embedded: bool
    available_tracks: List[Dict]
    generated_files: List[str]
    status: str


@router.get("/subtitle-status/{file_id}")
async def get_subtitle_status(file_id: str):
    """Get subtitle availability and status for a video file."""
    try:
        # Find uploaded video
        matching_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))
        if not matching_files:
            raise HTTPException(status_code=404, detail="Video file not found")

        video_path = matching_files[0]
        
        # Check for embedded subtitles
        has_embedded = has_embedded_subtitles(str(video_path))
        available_tracks = []
        
        if has_embedded:
            tracks = get_subtitle_tracks(str(video_path))
            available_tracks = [
                {
                    "index": track.index,
                    "language": track.language,
                    "title": track.title,
                    "codec": track.codec,
                    "is_default": track.is_default,
                    "is_forced": track.is_forced
                }
                for track in tracks
            ]

        # Check for generated subtitle files
        generated_files = []
        subtitle_dir = settings.OUTPUT_DIR / "subtitles"
        if subtitle_dir.exists():
            for ext in ['.srt', '.vtt']:
                subtitle_files = list(subtitle_dir.glob(f"{file_id}_subtitles{ext}"))
                generated_files.extend([str(f) for f in subtitle_files])

        return SubtitleStatus(
            file_id=file_id,
            has_embedded=has_embedded,
            available_tracks=available_tracks,
            generated_files=generated_files,
            status="ready"
        )

    except Exception as e:
        logger.error(f"Error getting subtitle status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking subtitle status: {str(e)}")


@router.post("/generate-subtitles", response_model=SubtitleResponse)
async def generate_subtitles(request: SubtitleRequest, background_tasks: BackgroundTasks):
    """Generate subtitles for a video file with YouTube-style formatting."""
    try:
        file_id = request.file_id
        
        # Find uploaded video
        matching_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))
        if not matching_files:
            raise HTTPException(status_code=404, detail="Video file not found")

        video_path = matching_files[0]
        subtitle_dir = settings.OUTPUT_DIR / "subtitles"
        subtitle_dir.mkdir(parents=True, exist_ok=True)

        # Check for cached transcription first
        cached_result = transcription_cache.load(file_id)
        segments = []
        
        if cached_result:
            logger.info(f"Using cached transcription for subtitle generation: {file_id}")
            segments = cached_result.get("segments", [])
        else:
            # Generate transcription if not cached
            logger.info(f"Generating transcription for subtitle generation: {file_id}")
            audio_filename = f"{file_id}_audio.wav"
            audio_path = extract_audio_from_video(str(video_path), audio_filename)
            
            if not audio_path:
                raise HTTPException(status_code=500, detail="Failed to extract audio for subtitle generation")
            
            # Transcribe with word-level timestamps if needed
            segments, detected_language = whisper_service.transcribe_video(
                audio_path,
                translate_to_english=True,
                target_language="en"
            )
            
            # Cache the result as a dict
            cache_result = {
                "segments": segments,
                "language": detected_language,
                "text": " ".join([seg.get("text", "") for seg in segments])
            }
            transcription_cache.save(file_id, cache_result)

        if not segments:
            raise HTTPException(status_code=400, detail="No transcription segments available for subtitle generation")

        # Generate YouTube-style SRT
        srt_filename = f"{file_id}_subtitles.srt"
        srt_path = subtitle_dir / srt_filename
        
        success = write_youtube_style_srt(
            segments,
            str(srt_path),
            max_chars_per_line=request.max_chars_per_line
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to generate SRT file")

        response_data: Dict[str, Any] = {
            "srt_path": str(srt_path),
            "message": f"Generated subtitles for {file_id}"
        }

        # Generate VTT file
        if request.include_vtt:
            vtt_filename = f"{file_id}_subtitles.vtt"
            vtt_path = subtitle_dir / vtt_filename
            
            if write_vtt(str(srt_path), str(vtt_path)):
                response_data["vtt_path"] = str(vtt_path)

        # Generate word-level subtitles
        if request.include_word_level:
            word_level_filename = f"{file_id}_subtitles_word_level.srt"
            word_level_path = subtitle_dir / word_level_filename
            
            if generate_word_level_subtitles(segments, str(word_level_path)):
                response_data["word_level_path"] = str(word_level_path)

        # Generate translations
        translated_files_dict: Dict[str, str] = {}
        if request.target_languages:
            translated_files = convert_to_multiple_languages(
                segments,
                request.target_languages,
                str(subtitle_dir)
            )
            translated_files_dict = translated_files

        response_data["translated_files"] = translated_files_dict

        logger.info(f"Successfully generated subtitles for {file_id}")
        return SubtitleResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"Subtitle generation failed: {str(e)}")


@router.get("/download-subtitle/{file_id}/{language}")
async def download_subtitle(file_id: str, language: str = "en"):
    """Download subtitle file for a video."""
    try:
        subtitle_dir = settings.OUTPUT_DIR / "subtitles"
        subtitle_file = subtitle_dir / f"{file_id}_subtitles_{language}.srt"
        
        if not subtitle_file.exists():
            # Try default English subtitle
            subtitle_file = subtitle_dir / f"{file_id}_subtitles.srt"
            
        if not subtitle_file.exists():
            raise HTTPException(status_code=404, detail="Subtitle file not found")

        return {
            "file_path": str(subtitle_file),
            "filename": subtitle_file.name,
            "content_type": "text/vtt" if subtitle_file.suffix == '.vtt' else "text/srt"
        }

    except Exception as e:
        logger.error(f"Error downloading subtitle: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading subtitle: {str(e)}")


@router.get("/extract-embedded-subtitles/{file_id}")
async def extract_embedded_subtitles(file_id: str, language: str = "en"):
    """Extract embedded subtitles from video file."""
    try:
        # Find uploaded video
        matching_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))
        if not matching_files:
            raise HTTPException(status_code=404, detail="Video file not found")

        video_path = matching_files[0]
        subtitle_dir = settings.OUTPUT_DIR / "subtitles"
        subtitle_dir.mkdir(parents=True, exist_ok=True)

        # Extract embedded subtitles
        subtitle_path, subtitle_segments = extract_and_parse_subtitles(
            str(video_path),
            str(subtitle_dir),
            language=language
        )

        if not subtitle_segments:
            raise HTTPException(status_code=404, detail="No embedded subtitles found or extraction failed")

        # Generate YouTube-style formatting
        formatted_srt_path = subtitle_dir / f"{file_id}_extracted_subtitles.srt"
        write_youtube_style_srt(subtitle_segments, str(formatted_srt_path))

        return {
            "extracted_file": str(subtitle_path) if subtitle_path else None,
            "formatted_file": str(formatted_srt_path),
            "segments_count": len(subtitle_segments),
            "message": f"Extracted and formatted {len(subtitle_segments)} subtitle segments"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting embedded subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"Embedded subtitle extraction failed: {str(e)}")


@router.get("/subtitle-languages/{file_id}")
async def get_subtitle_languages(file_id: str):
    """Get available subtitle languages for a video."""
    try:
        # Find uploaded video
        matching_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))
        if not matching_files:
            raise HTTPException(status_code=404, detail="Video file not found")

        video_path = matching_files[0]
        
        # Check for embedded subtitle tracks
        embedded_languages = []
        if has_embedded_subtitles(str(video_path)):
            tracks = get_subtitle_tracks(str(video_path))
            embedded_languages = [track.language for track in tracks]

        # Check for generated subtitle files
        generated_languages = []
        subtitle_dir = settings.OUTPUT_DIR / "subtitles"
        if subtitle_dir.exists():
            subtitle_files = list(subtitle_dir.glob(f"{file_id}_subtitles_*.srt"))
            for file in subtitle_files:
                # Extract language from filename
                parts = file.stem.split('_')
                if len(parts) > 2:
                    lang = parts[-1]
                    generated_languages.append(lang)

        return {
            "file_id": file_id,
            "embedded_languages": embedded_languages,
            "generated_languages": generated_languages,
            "has_embedded": len(embedded_languages) > 0
        }

    except Exception as e:
        logger.error(f"Error getting subtitle languages: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting subtitle languages: {str(e)}")


@router.delete("/clear-subtitles/{file_id}")
async def clear_subtitles(file_id: str):
    """Clear all subtitle files for a video."""
    try:
        subtitle_dir = settings.OUTPUT_DIR / "subtitles"
        if not subtitle_dir.exists():
            return {"message": "No subtitle files to clear"}

        # Find and remove subtitle files for this video
        subtitle_files = list(subtitle_dir.glob(f"{file_id}_*"))
        deleted_files = []
        
        for file in subtitle_files:
            try:
                file.unlink()
                deleted_files.append(str(file))
            except Exception as e:
                logger.warning(f"Could not delete subtitle file {file}: {e}")

        return {
            "message": f"Cleared {len(deleted_files)} subtitle files",
            "deleted_files": deleted_files
        }

    except Exception as e:
        logger.error(f"Error clearing subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing subtitles: {str(e)}")