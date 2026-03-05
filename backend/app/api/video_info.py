# backend/app/api/video_info.py

from fastapi import APIRouter, HTTPException
import logging
from pathlib import Path
import os
from typing import Dict, Any, Optional
from ..core.config import settings
from ..services.fast_video_processor import get_video_info_fast, get_actual_video_duration
from ..services.narrative_analyzer import analyze_video_narrative

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/video-info/{file_id}")
async def get_video_info(file_id: str) -> Dict[str, Any]:
    """
    Get detailed video information for a processed video file.
    
    Returns:
        Dict containing video metadata including duration, resolution, codec info, etc.
    """
    try:
        # Find video file - look for both patterns
        video_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))
        
        # If not found, try the original pattern without suffix
        if not video_files:
            video_files = list(settings.UPLOAD_DIR.glob(f"{file_id}.*"))
        
        if not video_files:
            raise HTTPException(status_code=404, detail="Video file not found")
        
        video_path = str(video_files[0])
        
        # Get video info using existing function
        info = get_video_info_fast(video_path)
        
        if not info:
            raise HTTPException(status_code=500, detail="Could not extract video information")
        
        # Extract key information
        video_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
        audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
        
        # Get video stream info
        video_info = video_streams[0] if video_streams else {}
        width = video_info.get("width", 0)
        height = video_info.get("height", 0)
        codec_name = video_info.get("codec_name", "unknown")
        fps = video_info.get("r_frame_rate", "unknown")
        
        # Get audio stream info
        audio_info = audio_streams[0] if audio_streams else {}
        audio_codec = audio_info.get("codec_name", "unknown")
        channels = audio_info.get("channels", 0)
        
        # Get format info
        format_info = info.get("format", {})
        file_size = format_info.get("size", "0")
        duration = format_info.get("duration", "0")
        
        # Calculate actual duration if not available from format
        if not duration or duration == "0":
            actual_duration = get_actual_video_duration(video_path)
            duration = str(actual_duration) if actual_duration > 0 else "0"
        
        # Get file size in human readable format
        try:
            file_size_bytes = int(file_size)
            if file_size_bytes >= 1024 * 1024:
                file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
                file_size_str = f"{file_size_mb} MB"
            elif file_size_bytes >= 1024:
                file_size_kb = round(file_size_bytes / 1024, 2)
                file_size_str = f"{file_size_kb} KB"
            else:
                file_size_str = f"{file_size_bytes} bytes"
        except (ValueError, TypeError):
            file_size_str = "Unknown"
        
        # Build response
        response = {
            "file_id": file_id,
            "duration": float(duration) if duration != "0" else 0.0,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}" if width and height else "Unknown",
            "codec": codec_name,
            "fps": fps,
            "audio_codec": audio_codec,
            "audio_channels": channels,
            "file_size": file_size_str,
            "file_size_bytes": int(file_size) if file_size.isdigit() else 0,
            "aspect_ratio": f"{width}:{height}" if width and height else "Unknown"
        }
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get video info: {str(e)}")


@router.get("/video-metadata/{file_id}")
async def get_video_metadata(file_id: str) -> Dict[str, Any]:
    """
    Get comprehensive video metadata including AI-analyzed information.
    
    Returns:
        Dict containing both technical and AI-analyzed metadata
    """
    try:
        # Find video file
        video_files = list(settings.UPLOAD_DIR.glob(f"{file_id}_original.*"))
        
        if not video_files:
            video_files = list(settings.UPLOAD_DIR.glob(f"{file_id}.*"))
        
        if not video_files:
            raise HTTPException(status_code=404, detail="Video file not found")
        
        video_path = str(video_files[0])
        
        # Get technical video info
        technical_info = await get_video_info(file_id)
        
        # Get AI-analyzed metadata
        try:
            ai_metadata = analyze_video_narrative(video_path)
        except Exception as e:
            logger.warning(f"AI metadata analysis failed: {str(e)}")
            ai_metadata = {
                "title": "Unknown",
                "language": "Unknown",
                "genre": "Unknown",
                "release_year": "Unknown",
                "starring": "Unknown"
            }
        
        # Combine technical and AI metadata
        response = {
            **technical_info,
            "ai_metadata": ai_metadata,
            "metadata_source": "realtime_analysis"
        }
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get video metadata: {str(e)}")

