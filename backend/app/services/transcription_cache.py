# backend/app/services/transcription_cache.py
"""
Transcription caching service to avoid re-transcribing videos.
Stores transcription results in JSON files for reuse.
"""

import json
import logging
import warnings

warnings.filterwarnings("ignore")
from pathlib import Path
from typing import Dict, Any, Optional
from ..core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionCache:
    """
    Manages caching of transcription results to avoid redundant processing.
    """

    def __init__(self):
        self.cache_dir = settings.AUDIO_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, file_id: str) -> Path:
        """Get the cache file path for a given file_id."""
        return self.cache_dir / f"{file_id}_transcription.json"

    def save(self, file_id: str, result: Dict[str, Any]) -> None:
        """
        Save transcription result to cache.
        
        Args:
            file_id: Unique identifier for the video
            result: Transcription result containing text, segments, etc.
        """
        cache_path = self._get_cache_path(file_id)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Cached transcription for {file_id}")
        except Exception as e:
            logger.warning(f"Failed to cache transcription: {e}")

    def load(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Load transcription result from cache.
        
        Args:
            file_id: Unique identifier for the video
            
        Returns:
            Cached transcription result or None if not found
        """
        cache_path = self._get_cache_path(file_id)
        try:
            if cache_path.exists():
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"✅ Loaded cached transcription for {file_id}")
                return data
        except Exception as e:
            logger.warning(f"Failed to load cached transcription: {e}")
        return None

    def exists(self, file_id: str) -> bool:
        """Check if a cached transcription exists."""
        return self._get_cache_path(file_id).exists()

    def delete(self, file_id: str) -> None:
        """Delete cached transcription."""
        cache_path = self._get_cache_path(file_id)
        try:
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Deleted cache for {file_id}")
        except Exception as e:
            logger.warning(f"Failed to delete cache: {e}")


# Global instance
transcription_cache = TranscriptionCache()
