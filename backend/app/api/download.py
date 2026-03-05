# backend/app/api/download.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import urllib.parse
import logging
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download a processed video file.
    
    Args:
        filename: The filename to download (may be URL-encoded)
        
    Returns:
        FileResponse with the video file
        
    Raises:
        HTTPException: If file not found (404)
    """
    try:
        # Handle URL-encoded filenames
        decoded_filename = urllib.parse.unquote(filename)
        logger.info(f"Download requested for: {decoded_filename}")
        
        file_path = settings.OUTPUTS_DIR / decoded_filename
        logger.debug(f"Looking for file at: {file_path}")

        if not file_path.exists():
            logger.warning(f"Download requested for non-existent file: {decoded_filename}")
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"Sending file: {decoded_filename}")
        return FileResponse(
            path=str(file_path),
            media_type="video/mp4",
            filename=decoded_filename,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file")
