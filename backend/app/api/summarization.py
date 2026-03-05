# backend/app/api/summarization.py

from fastapi import APIRouter, HTTPException
from ..models import schemas
from ..services.summarizer_service import summarizer_service

router = APIRouter()


@router.post("/summarize", response_model=schemas.SummarizationResponse)
async def summarize_transcription(request: schemas.SummarizationRequest):
    """
    Summarize transcription text using FLAN-T5 model.
    """
    transcription = request.transcription
    
    if not transcription:
        raise HTTPException(status_code=400, detail="Transcription is required")
    
    try:
        summary = summarizer_service.summarize(transcription)
        return schemas.SummarizationResponse(summary=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
