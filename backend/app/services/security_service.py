# backend/app/services/security_service.py

from typing import Optional, Dict, Any
import os
import logging
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.services.metrics_service import record_system_metric

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Handles file validation and security checks.
    """

    ALLOWED_VIDEO_TYPES = {
        "video/mp4",
        "video/mov",
        "video/avi",
        "video/mkv"
    }

    def __init__(self) -> None:
        self.max_size: int = settings.MAX_VIDEO_SIZE

    async def validate_video_upload(
        self,
        file: UploadFile,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validates uploaded video file.
        """

        if file.content_type not in self.ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Unsupported video format."
            )

        # Read file size safely
        contents = await file.read()
        file_size: int = len(contents)

        # Reset file pointer
        await file.seek(0)

        if file_size > self.max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum size of {self.max_size} bytes."
            )

        await record_system_metric(
            "video_upload_validated",
            1.0,
            metadata or {}
        )

    def validate_path(self, path: str) -> str:
        """
        Prevent directory traversal attacks.
        """

        normalized_path = os.path.abspath(path)

        if ".." in normalized_path:
            raise HTTPException(
                status_code=400,
                detail="Invalid file path."
            )

        return normalized_path


security_service = SecurityService()