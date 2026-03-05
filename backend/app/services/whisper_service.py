import logging
import os
import re
from typing import List, Dict, Tuple, Optional, Any
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Segment grouping configuration - group short Whisper segments into larger coherent chunks
GROUP_MIN_WORDS = int(os.getenv("WHISPER_GROUP_MIN_WORDS", "8"))
GROUP_MAX_WORDS = int(os.getenv("WHISPER_GROUP_MAX_WORDS", "30"))
GROUP_MAX_DURATION = float(os.getenv("WHISPER_GROUP_MAX_DURATION", "12.0"))

# OPTIMIZATION: Use CTranslate2 optimized models for GPU acceleration
# These are pre-converted models optimized for inference speed
USE_CT2_MODELS = os.getenv("WHISPER_USE_CT2", "true").strip().lower() in ("1", "true", "yes")


def _group_transcription_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group short Whisper segments into larger coherent chunks based on:
    - Sentence boundaries (., !, ?)
    - Word count limits
    - Duration limits
    
    This prevents having too many short segments that cause jarring cuts in the video.
    """
    if not segments:
        return segments
    
    # If segments are already large enough, return as-is
    if len(segments) <= 10:
        return segments
    
    grouped: List[Dict[str, Any]] = []
    current_group: List[Dict[str, Any]] = []
    current_start: float = 0.0
    current_end: float = 0.0
    current_text: List[str] = []
    current_words: int = 0
    
    for seg in segments:
        text = seg.get("text", "")
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        seg_duration = seg.get("end", 0) - seg.get("start", 0)
        
        # Check if we should start a new group
        should_flush = False
        
        # Check for sentence-ending punctuation
        sentence_end = re.search(r'[.!?]\s*$', text)
        
        # Check if adding this segment would exceed limits
        if current_words + word_count > GROUP_MAX_WORDS:
            should_flush = True
        elif seg_duration + (current_end - current_start) > GROUP_MAX_DURATION:
            should_flush = True
        elif sentence_end and current_words >= GROUP_MIN_WORDS:
            # Flush at sentence boundaries if we have enough content
            should_flush = True
        
        if should_flush and current_group:
            # Save current group
            grouped.append({
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_text).strip()
            })
            current_group = []
            current_text = []
            current_words = 0
        
        # Add to current group
        if not current_group:
            current_start = seg.get("start", 0)
        
        current_group.append(seg)
        current_end = seg.get("end", 0)
        current_text.append(text)
        current_words += word_count
    
    # Don't forget the last group
    if current_group:
        grouped.append({
            "start": current_start,
            "end": current_end,
            "text": " ".join(current_text).strip()
        })
    
    # If we have too few groups, return original segments
    if len(grouped) >= len(segments) * 0.5:
        return segments
    
    logger.info(f"Grouped {len(segments)} segments into {len(grouped)} larger chunks")
    return grouped


class WhisperService:
    """
    Multilingual transcription service with model selection.
    Optimized for speed with configurable parameters.
    Enhanced for better dialogue and music detection.
    """

    def __init__(self):
        # OPTIMIZATION: Now with CUDA available, enable GPU mode by default for faster processing
        self.strict_gpu = os.getenv("WHISPER_STRICT_GPU", "true").strip().lower() in ("1", "true", "yes")
        # Use "medium" model for better transcription accuracy (dialogue/music detection)
        # Can be overridden via environment variable for faster processing with "small"
        self.default_model_size = os.getenv("WHISPER_MODEL_SIZE", "medium").strip()

        # Beam size for transcription - higher values give better accuracy
        # Using beam_size=5 for better accuracy (default in faster-whisper is 1)
        self.default_beam_size = self._parse_int_env("WHISPER_BEAM_SIZE", 5)
        
        # Enable VAD (Voice Activity Detection) filter by default for better speech detection
        # This helps filter out non-speech segments and improves subtitle quality
        self.use_vad_filter = os.getenv("WHISPER_USE_VAD", "true").strip().lower() in ("1", "true", "yes")
        
        # Enable word timestamps for better subtitle timing
        self.use_word_timestamps = os.getenv("WHISPER_WORD_TIMESTAMPS", "false").strip().lower() in ("1", "true", "yes")
        
        # Temperature for transcription - lower values are more deterministic
        # Using 0.0 for most accurate transcription
        self.temperature = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
        
        # Compression ratio threshold - helps filter out low-quality transcriptions
        self.compression_ratio_threshold = float(os.getenv("WHISPER_COMPRESSION_RATIO_THRESHOLD", "2.4"))
        
        # No speech threshold - segments with no_speech_prob above this are considered silence
        self.no_speech_threshold = float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.6"))
        
        # Log probability threshold - filter out low-confidence segments
        self.log_prob_threshold = float(os.getenv("WHISPER_LOG_PROB_THRESHOLD", "-1.0"))

        # Cache models by size so mode switches do not require server restart.
        self._model_cache: Dict[str, WhisperModel] = {}
        self._device_cache: Dict[str, str] = {}
        self._compute_cache: Dict[str, str] = {}
        self._last_model_size = self.default_model_size

        # Warm start default model.
        self._get_or_create_model(self.default_model_size)

    @staticmethod
    def _parse_int_env(name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return default

    def _candidate_devices(self) -> List[Tuple[str, str]]:
        # GPU-only mode - no CPU fallback
        # CTranslate2 with CUDA provides excellent performance
        candidates: List[Tuple[str, str]] = [
            ("cuda", "float16"),
            ("cuda", "int8_float16"),
            ("cuda", "int8"),
        ]
        return candidates

    def _get_or_create_model(self, model_size: str) -> WhisperModel:
        if model_size in self._model_cache:
            return self._model_cache[model_size]

        last_error: Optional[Exception] = None
        
        # OPTIMIZATION: Try GPU with float16 for fastest inference
        if USE_CT2_MODELS:
            try:
                # Try to load model with GPU using float16 for best speed
                model = WhisperModel(
                    model_size,
                    device="cuda",
                    compute_type="float16"
                )
                self._model_cache[model_size] = model
                self._device_cache[model_size] = "cuda"
                self._compute_cache[model_size] = "float16"
                logger.info(
                    "Whisper GPU model loaded: model=%s device=cuda compute_type=float16",
                    model_size
                )
                return model
            except Exception as e:
                logger.warning(
                    "GPU model not available for %s: %s",
                    model_size, str(e)
                )
                last_error = e

        # GPU-only mode - try standard faster-whisper with GPU
        for device, compute_type in self._candidate_devices():
            try:
                model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type
                )
                self._model_cache[model_size] = model
                self._device_cache[model_size] = device
                self._compute_cache[model_size] = compute_type
                logger.info(
                    "Whisper model loaded: model=%s device=%s compute_type=%s",
                    model_size, device, compute_type
                )
                return model
            except Exception as e:
                last_error = e
                logger.warning(
                    "Whisper init failed for model=%s device=%s compute_type=%s: %s",
                    model_size, device, compute_type, e
                )

        # CPU fallback - try with CPU if GPU fails and strict mode is off
        if not self.strict_gpu:
            logger.info(f"Falling back to CPU for model '{model_size}'")
            try:
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
                self._model_cache[model_size] = model
                self._device_cache[model_size] = "cpu"
                self._compute_cache[model_size] = "int8"
                logger.info(
                    "Whisper CPU model loaded: model=%s device=cpu compute_type=int8",
                    model_size
                )
                return model
            except Exception as cpu_error:
                logger.error(f"CPU fallback also failed: {cpu_error}")
        
        raise RuntimeError(
            f"Whisper model '{model_size}' could not be loaded. "
            f"GPU error: {last_error}. Set WHISPER_STRICT_GPU=false to use CPU mode."
        ) from last_error

    def get_runtime_info(self) -> Dict[str, Any]:
        last = self._last_model_size
        return {
            "last_model_size": last,
            "last_device": self._device_cache.get(last, "unknown"),
            "last_compute_type": self._compute_cache.get(last, "unknown"),
            "default_model_size": self.default_model_size,
            "default_beam_size": str(self.default_beam_size),
            "strict_gpu": str(self.strict_gpu).lower(),
            "loaded_models": list(self._model_cache.keys()),
        }

    def transcribe_video(
        self,
        audio_path: str,
        translate_to_english: bool = True,
        model_size: Optional[str] = None,
        beam_size: Optional[int] = None,
        target_language: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Transcribe audio from video with enhanced settings for better dialogue/music detection.
        
        Args:
            audio_path: Path to the audio file
            translate_to_english: Whether to translate to English (default: True)
            model_size: Whisper model size (default: medium for better accuracy)
            beam_size: Beam size for transcription (default: 5 for better accuracy)
            target_language: Target language code (default: "en" for English)
            
        Returns:
            Tuple of (segments list, detected language)
        """
        effective_model = model_size or self.default_model_size
        effective_beam = max(1, int(beam_size or self.default_beam_size))

        model = self._get_or_create_model(effective_model)
        self._last_model_size = effective_model

        # ALWAYS ensure transcript is in English as per requirement
        # If target_language is not specified, default to English
        if target_language is None:
            target_language = "en"
        
        logger.info(
            f"Starting transcription: model={effective_model}, beam_size={effective_beam}, "
            f"vad_filter={self.use_vad_filter}, target_language={target_language}"
        )
        
        # First, detect the language with a quick transcription
        # Enhanced parameters for better speech/music detection
        try:
            segments_generator, info = model.transcribe(
                audio_path,
                beam_size=effective_beam,
                vad_filter=self.use_vad_filter,
                word_timestamps=self.use_word_timestamps,
                temperature=self.temperature,
                compression_ratio_threshold=self.compression_ratio_threshold,
                no_speech_threshold=self.no_speech_threshold,
                log_prob_threshold=self.log_prob_threshold,
                # Enable condition_on_previous_text for better context
                condition_on_previous_text=True,
            )
        except RuntimeError as e:
            if ("cublas" in str(e).lower() or "cuda" in str(e).lower()) and self.strict_gpu:
                raise RuntimeError(f"GPU transcription failed in strict GPU mode: {e}") from e
            raise

        detected_language = info.language
        language_probability = info.language_probability
        duration = info.duration if hasattr(info, 'duration') else 0
        
        logger.info(
            f"Detected Language: {detected_language} (probability: {language_probability:.2%}), "
            f"audio duration: {duration:.2f}s"
        )

        raw_segments: List[Dict[str, Any]] = []
        for segment in segments_generator:
            # Skip segments with very low confidence or no speech
            if hasattr(segment, 'no_speech_prob') and segment.no_speech_prob > self.no_speech_threshold:
                logger.debug(f"Skipping low-confidence segment: {segment.text[:50]}...")
                continue
            
            # Clean up the text
            text = segment.text.strip()
            
            # Skip empty or very short segments
            if not text or len(text) < 2:
                continue
            
            raw_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": text
            })
        
        logger.info(f"Raw transcription: {len(raw_segments)} segments extracted")
        
        # Group short segments into larger coherent chunks
        segments = _group_transcription_segments(raw_segments)

        # Handle translation to target language (default: English)
        # If detected language is different from target (English), translate
        if target_language and target_language.lower() != detected_language.lower():
            logger.info(f"Translating from {detected_language} to {target_language}...")
            translated_segments: List[Dict[str, Any]] = []
            
            # Map language codes to Whisper task parameters
            # Whisper uses ISO 639-1 codes for transcription and English for translation
            if target_language.lower() == 'en':
                # Translate to English using Whisper's built-in translation task
                logger.info("Using Whisper 'translate' task for English output")
                translated_generator, _ = model.transcribe(
                    audio_path,
                    task="translate",
                    beam_size=effective_beam,
                    vad_filter=self.use_vad_filter,
                    temperature=self.temperature,
                    compression_ratio_threshold=self.compression_ratio_threshold,
                    no_speech_threshold=self.no_speech_threshold,
                    log_prob_threshold=self.log_prob_threshold,
                    condition_on_previous_text=True,
                )
            else:
                # For other languages, we need to transcribe in that language
                # Note: This requires the model to support the target language
                translated_generator, _ = model.transcribe(
                    audio_path,
                    language=target_language,
                    beam_size=effective_beam,
                    vad_filter=self.use_vad_filter,
                    temperature=self.temperature,
                    compression_ratio_threshold=self.compression_ratio_threshold,
                    no_speech_threshold=self.no_speech_threshold,
                    log_prob_threshold=self.log_prob_threshold,
                    condition_on_previous_text=True,
                )
            
            for segment in translated_generator:
                # Skip segments with very low confidence
                if hasattr(segment, 'no_speech_prob') and segment.no_speech_prob > self.no_speech_threshold:
                    continue
                
                text = segment.text.strip()
                if not text or len(text) < 2:
                    continue
                    
                translated_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": text
                })
            
            # Group the translated segments as well
            translated_segments = _group_transcription_segments(translated_segments)
            logger.info(f"Translation complete: {len(translated_segments)} segments in {target_language}")
            return translated_segments, target_language

        # If detected language is already English, return as-is
        logger.info(f"Transcript language: {detected_language} (no translation needed), {len(segments)} segments")
        return segments, detected_language


whisper_service = WhisperService()


def transcribe_audio(
    audio_path: str,
    video_duration: Optional[float] = None,
    video_file_size: Optional[float] = None,
    translate_to_english: Optional[bool] = None,
    target_language: Optional[str] = None
) -> Dict[str, Any]:
    # REQUIREMENT: Transcripts must be in English by default
    # The whisper_service.transcribe_video will default target_language to "en"
    # This ensures all transcripts are in English regardless of video's original language
    
    # If target_language is not explicitly set, default to English
    if target_language is None:
        target_language = "en"

    selected_model = whisper_service.default_model_size
    selected_beam = whisper_service.default_beam_size

    segments, language = whisper_service.transcribe_video(
        audio_path,
        translate_to_english=True,  # Always translate to English
        model_size=selected_model,
        beam_size=selected_beam,
        target_language=target_language
    )

    no_speech_detected = len(segments) == 0
    result: Dict[str, Any] = {
        "text": " ".join([seg["text"] for seg in segments]),
        "segments": segments,
        "language": language,
        "no_speech_detected": no_speech_detected,
        "model_size_used": selected_model,
        "beam_size_used": selected_beam
    }

    if video_duration is not None:
        result["video_duration"] = video_duration
    if video_file_size is not None:
        result["video_file_size"] = video_file_size

    return result
