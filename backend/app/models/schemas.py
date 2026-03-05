from pydantic import BaseModel
from typing import List, Optional


# -----------------------------
# Video Segment Models
# -----------------------------

class Segment(BaseModel):
    start: float
    end: float
    text: str


class SegmentRequest(BaseModel):
    video_id: str


class SegmentResponse(BaseModel):
    segments: List[Segment]


# -----------------------------
# Video Upload Models
# -----------------------------

class UploadResponse(BaseModel):
    video_id: str
    filename: str
    message: str


# -----------------------------
# Processing Status
# -----------------------------

class ProcessingStatus(BaseModel):
    video_id: str
    status: str
    progress: Optional[float] = None
    message: Optional[str] = None


# -----------------------------
# Subtitle Models
# -----------------------------

class SubtitleSegment(BaseModel):
    start: float
    end: float
    text: str


class SubtitleResponse(BaseModel):
    language: str
    subtitles: List[SubtitleSegment]


# -----------------------------
# Narrative Analysis Models
# -----------------------------

class NarrativeSegment(BaseModel):
    start: float
    end: float
    score: float
    text: str


class NarrativeResponse(BaseModel):
    segments: List[NarrativeSegment]


# -----------------------------
# Video Output Models
# -----------------------------

class VideoOutput(BaseModel):
    video_id: str
    output_url: str
    duration: Optional[float] = None
    resolution: Optional[str] = None