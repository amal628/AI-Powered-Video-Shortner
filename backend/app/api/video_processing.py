from fastapi import APIRouter, HTTPException
from typing import List
import logging

from app.models.schemas import (
    Segment,
    SegmentRequest,
    SegmentResponse
)

from app.services.video_segmenter import VideoSegmenter


router = APIRouter()
logger = logging.getLogger(__name__)


# Initialize the segmenter once
segmenter = VideoSegmenter()


@router.post("/segment", response_model=SegmentResponse)
async def segment_video(request: SegmentRequest) -> SegmentResponse:
    """
    Segment a video based on transcript or narrative structure.
    """

    try:
        logger.info(f"Segmenting video: {request.video_id}")

        segments = segmenter.segment_video(request.video_id)

        segment_objects: List[Segment] = [
            Segment(
                start=s["start"],
                end=s["end"],
                text=s["text"]
            )
            for s in segments
        ]

        return SegmentResponse(segments=segment_objects)

    except Exception as e:
        logger.error(f"Video segmentation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Video segmentation failed"
        )