# backend/app/api/share.py

from fastapi import APIRouter, HTTPException, Request
import logging
import urllib.parse
from ..core.config import settings
from ..models.schemas import ShareResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/share/{filename}", response_model=ShareResponse)
async def share_file(filename: str, request: Request):
    """Return a JSON object containing a shareable URL for the given filename.

    This constructs a link to the download endpoint, using the request base URL 
    to make it absolute so it can be shared via email or social apps.
    
    Args:
        filename: The name of the file to share (from outputs directory)
        request: The HTTP request object
        
    Returns:
        ShareResponse with absolute share URL
        
    Raises:
        HTTPException: If file not found (404) or invalid filename (400)
    """
    try:
        if not filename or not isinstance(filename, str):
            logger.warning(f"Invalid filename provided: {filename}")
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Handle URL-encoded filenames
        decoded_filename = urllib.parse.unquote(filename)
        logger.info(f"Processing share request for: {decoded_filename}")
        
        file_path = settings.OUTPUTS_DIR / decoded_filename
        logger.debug(f"Looking for file at: {file_path}")
        
        if not file_path.exists():
            logger.warning(f"Share requested for non-existent file: {decoded_filename}")
            raise HTTPException(status_code=404, detail="File not found")

        # Construct absolute URL from request
        base = str(request.base_url).rstrip('/')
        # Use URL-encoded filename in the response
        share_url = f"{base}/api/download/{urllib.parse.quote(decoded_filename)}"
        
        logger.info(f"Share URL generated for: {decoded_filename}")
        return ShareResponse(share_url=share_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating share URL for {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate share URL")
