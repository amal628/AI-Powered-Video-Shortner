import os
import json
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import re
import asyncio
from collections import defaultdict

from ..models.schemas import VideoMetadata, TranscriptSegment, HighlightSegment
from ..services.whisper_service import WhisperService
from ..services.highlight_detector import HighlightDetector
from ..services.trailer_segment_selector import select_trailer_segments
from ..services.progress_tracker import ProcessingProgressTracker
from ..services.content_type_analyzer import content_type_analyzer

logger = logging.getLogger(__name__)

@dataclass
class NarrativeAnalysisResult:
    """Result of narrative analysis with all detected segments and metadata."""
    video_metadata: VideoMetadata
    transcript_segments: List[TranscriptSegment]
    highlight_segments: List[HighlightSegment]
    selected_segments: List[HighlightSegment]
    total_duration: float
    target_duration: float
    efficiency_ratio: float
    language: str
    analysis_timestamp: datetime

class NarrativeAnalyzer:
    """Enhanced narrative analyzer with improved segment detection and selection."""
    
    def __init__(self, whisper_service: WhisperService, progress_tracker: ProcessingProgressTracker):
        self.whisper_service = whisper_service
        self.progress_tracker = progress_tracker
        self.highlight_detector = HighlightDetector()
        # Use the function directly instead of creating a class instance
        self.select_trailer_segments = select_trailer_segments
        
        # Configuration
        self.min_segment_duration = 3.0  # Minimum segment duration in seconds
        self.max_segment_duration = 15.0  # Maximum segment duration in seconds
        self.target_duration_buffer = 2.0  # Buffer for target duration
        
    async def analyze_video(self, 
                          video_path: str, 
                          target_duration: float,
                          quality: str = "medium") -> NarrativeAnalysisResult:
        """Perform comprehensive narrative analysis of a video file."""
        try:
            # Step 1: Extract video metadata
            logger.info(f"Analyzing video: {video_path}")
            video_metadata = await self._extract_video_metadata(video_path)
            
            # Step 2: Generate transcript with Whisper (supports 99+ languages)
            logger.info("Generating transcript with Whisper...")
            transcript_segments, detected_language = self.whisper_service.transcribe_video(
                video_path
            )
            
            # Convert dict segments to TranscriptSegment objects
            transcript_segments_objects = []
            for seg in transcript_segments:
                transcript_seg = TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                    confidence=0.9,  # Default confidence since whisper_service doesn't provide it
                    language=detected_language
                )
                transcript_segments_objects.append(transcript_seg)
            
            # Create a simple result object to maintain compatibility
            class TranscriptResult:
                def __init__(self, segments, language):
                    self.segments = segments
                    self.language = language
                    self.video_metadata = video_metadata  # Use the metadata we already extracted
            
            transcript_result = TranscriptResult(transcript_segments_objects, detected_language)
            
            # Step 3: Detect highlight segments with improved detection
            logger.info("Detecting highlight segments...")
            # Convert TranscriptSegment objects to dict format for highlight detector
            transcript_dicts = []
            for seg in transcript_result.segments:
                transcript_dicts.append({
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text,
                    'duration': seg.duration,
                    'confidence': seg.confidence,
                    'language': seg.language
                })
            
            # Use merge_segments method from HighlightDetector
            highlight_segments_dicts = self.highlight_detector.merge_segments(
                transcript_dicts,
                target_duration=int(target_duration),  # Convert to int as expected by method
                top_k=5  # Get top 5 highlights
            )
            
            # Convert dict highlight segments to HighlightSegment objects
            highlight_segments = []
            for seg_dict in highlight_segments_dicts:
                highlight_seg = HighlightSegment(
                    start=seg_dict["start"],
                    end=seg_dict["end"],
                    duration=seg_dict["duration"],
                    score=seg_dict.get("score", 0.5),  # Default score if not provided
                    type="highlight",
                    keywords=[],
                    text=seg_dict.get("text", "")
                )
                highlight_segments.append(highlight_seg)
            
            # Step 4: Select optimal segments for target duration
            logger.info(f"Selecting segments for target duration: {target_duration}s")
            # Use select_trailer_segments function directly
            trailer_plan = self.select_trailer_segments(
                transcript_result.segments,
                transcript_result.video_metadata.duration if hasattr(transcript_result, 'video_metadata') else 0,
                target_duration
            )
            
            # Extract selected segments from trailer plan
            trailer_segments = trailer_plan.get_all_segments()
            
            # Convert CategorizedSegment to HighlightSegment for compatibility
            selected_segments = []
            for seg in trailer_segments:
                highlight_seg = HighlightSegment(
                    start=seg.start,
                    end=seg.end,
                    duration=seg.duration,
                    score=seg.score,
                    type=seg.category.value,
                    keywords=[],  # Could extract keywords from text if needed
                    text=seg.text
                )
                selected_segments.append(highlight_seg)
            
            # Step 5: Calculate efficiency metrics
            total_duration = sum(segment.duration for segment in selected_segments)
            efficiency_ratio = total_duration / target_duration if target_duration > 0 else 0
            
            # Step 6: Create analysis result
            result = NarrativeAnalysisResult(
                video_metadata=video_metadata,
                transcript_segments=transcript_result.segments,
                highlight_segments=highlight_segments,
                selected_segments=selected_segments,
                total_duration=total_duration,
                target_duration=target_duration,
                efficiency_ratio=efficiency_ratio,
                language=transcript_result.language,
                analysis_timestamp=datetime.now()
            )
            
            logger.info(f"Analysis complete. Selected {len(selected_segments)} segments, "
                       f"total duration: {total_duration:.2f}s, efficiency: {efficiency_ratio:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during narrative analysis: {str(e)}", exc_info=True)
            raise
    
    async def _extract_video_metadata(self, video_path: str) -> VideoMetadata:
        """Extract metadata from video file using ffprobe."""
        try:
            import subprocess
            
            # Use ffprobe to get video metadata
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(f"ffprobe failed: {result.stderr}")
            
            metadata = json.loads(result.stdout)
            
            # Extract relevant information
            format_info = metadata.get('format', {})
            streams = metadata.get('streams', [])
            
            # Find video stream
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
            audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
            
            return VideoMetadata(
                filename=os.path.basename(video_path),
                duration=float(format_info.get('duration', 0)),
                size=int(format_info.get('size', 0)),
                format_name=format_info.get('format_name', ''),
                video_codec=video_stream.get('codec_name', ''),
                audio_codec=audio_stream.get('codec_name', ''),
                width=video_stream.get('width', 0),
                height=video_stream.get('height', 0),
                fps=self._parse_fps(video_stream.get('r_frame_rate', '0/1')),
                bitrate=int(format_info.get('bit_rate', 0)),
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error extracting video metadata: {str(e)}")
            # Return default metadata if extraction fails
            return VideoMetadata(
                filename=os.path.basename(video_path),
                duration=0,
                size=0,
                format_name='',
                video_codec='',
                audio_codec='',
                width=0,
                height=0,
                fps=0,
                bitrate=0,
                created_at=datetime.now()
            )
    
    def _parse_fps(self, fps_string: str) -> float:
        """Parse FPS from ffprobe output (e.g., '30000/1001' -> 29.97)."""
        try:
            if '/' in fps_string:
                num, den = map(int, fps_string.split('/'))
                return num / den
            return float(fps_string)
        except:
            return 30.0  # Default FPS
    
    def get_analysis_summary(self, result: NarrativeAnalysisResult) -> Dict[str, Any]:
        """Get a summary of the narrative analysis."""
        return {
            'video_info': {
                'filename': result.video_metadata.filename,
                'duration': result.video_metadata.duration,
                'resolution': f"{result.video_metadata.width}x{result.video_metadata.height}",
                'language': result.language
            },
            'transcript_info': {
                'total_segments': len(result.transcript_segments),
                'total_words': sum(len(segment.text.split()) for segment in result.transcript_segments),
                'average_confidence': np.mean([s.confidence for s in result.transcript_segments]) if result.transcript_segments else 0
            },
            'highlight_info': {
                'total_highlights': len(result.highlight_segments),
                'selected_highlights': len(result.selected_segments),
                'selection_efficiency': result.efficiency_ratio
            },
            'timing_info': {
                'target_duration': result.target_duration,
                'actual_duration': result.total_duration,
                'time_saved': result.video_metadata.duration - result.total_duration
            }
        }
    
    def export_analysis_report(self, result: NarrativeAnalysisResult, output_path: str):
        """Export detailed analysis report to JSON file."""
        try:
            report = {
                'analysis_metadata': {
                    'timestamp': result.analysis_timestamp.isoformat(),
                    'version': '2.0',
                    'target_duration': result.target_duration,
                    'actual_duration': result.total_duration,
                    'efficiency_ratio': result.efficiency_ratio
                },
                'video_metadata': {
                    'filename': result.video_metadata.filename,
                    'duration': result.video_metadata.duration,
                    'size': result.video_metadata.size,
                    'resolution': f"{result.video_metadata.width}x{result.video_metadata.height}",
                    'format': result.video_metadata.format_name,
                    'video_codec': result.video_metadata.video_codec,
                    'audio_codec': result.video_metadata.audio_codec,
                    'fps': result.video_metadata.fps,
                    'bitrate': result.video_metadata.bitrate
                },
                'transcript': [
                    {
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text,
                        'confidence': segment.confidence,
                        'speaker': getattr(segment, 'speaker', None)
                    }
                    for segment in result.transcript_segments
                ],
                'highlights': [
                    {
                        'start': segment.start,
                        'end': segment.end,
                        'duration': segment.duration,
                        'score': segment.score,
                        'type': segment.type,
                        'keywords': segment.keywords,
                        'text': segment.text
                    }
                    for segment in result.highlight_segments
                ],
                'selected_segments': [
                    {
                        'start': segment.start,
                        'end': segment.end,
                        'duration': segment.duration,
                        'score': segment.score,
                        'type': segment.type
                    }
                    for segment in result.selected_segments
                ]
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Analysis report exported to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error exporting analysis report: {str(e)}")
            raise

class EnhancedNarrativeAnalyzer:
    """Enhanced narrative analyzer with auto segmentation, concatenation, and language support."""
    
    # Filler words and pauses for different languages
    FILLER_WORDS = {
        'en': ['um', 'uh', 'like', 'you know', 'so', 'well', 'actually', 'basically', 'literally', 'really', 'just', 'totally'],
        'es': ['este', 'eh', 'bueno', 'pues', 'como', 'este', 'verás', 'pues', 'bueno', 'entonces'],
        'fr': ['euh', 'ben', 'alors', 'voilà', 'enfin', 'bon', 'alors', 'comme', 'quoi', 'en fait'],
        'de': ['äh', 'ähm', 'also', 'naja', 'mal', 'halt', 'eigentlich', 'einfach', 'doch', 'mal sehen'],
        'it': ['ehm', 'allora', 'cioè', 'insomma', 'beh', 'allora', 'come', 'quindi', 'allora', 'insomma'],
        'pt': ['é', 'então', 'tipo', 'né', 'então', 'tipo', 'então', 'tipo', 'né', 'então'],
        'ru': ['это', 'ну', 'вот', 'так', 'вот', 'ну', 'вот', 'так', 'вот', 'ну'],
        'ja': ['あの', 'えっと', 'つまり', 'なんか', 'あの', 'えっと', 'つまり', 'なんか', 'あの', 'えっと'],
        'ko': ['그', '뭐', '그러니까', '뭐', '그', '뭐', '그러니까', '뭐', '그', '뭐'],
        'zh': ['那个', '呃', '然后', '就是', '那个', '呃', '然后', '就是', '那个', '呃']
    }
    
    PAUSE_PATTERNS = [
        r'\.{2,}',  # Multiple dots
        r'\s+',     # Multiple spaces
        r'—+',     # Em dashes
        r'-+',      # Hyphens
    ]
    
    # Platform-specific duration limits
    PLATFORM_DURATIONS = {
        'instagram_reels': 90,
        'tiktok': 60,
        'youtube_shorts': 60,
        'facebook_reels': 90,
        'twitter': 140,
        'snapchat': 60,
        'default': 120
    }
    
    def __init__(self, whisper_service: WhisperService, progress_tracker: ProcessingProgressTracker):
        self.whisper_service = whisper_service
        self.progress_tracker = progress_tracker
        self.narrative_analyzer = NarrativeAnalyzer(whisper_service, progress_tracker)
        self.highlight_detector = HighlightDetector()
        # Use the function directly instead of creating a class instance
        self.select_trailer_segments = select_trailer_segments
        
    async def analyze_and_optimize_video(
        self, 
        video_path: str, 
        platform: str = 'default',
        quality: str = "medium"
    ) -> Dict:
        """Complete video analysis and optimization pipeline."""
        try:
            # Step 1: Get platform-specific target duration
            target_duration = self._get_platform_duration(platform)
            
            # Step 2: Perform comprehensive analysis
            analysis_result = await self.narrative_analyzer.analyze_video(
                video_path, target_duration, quality
            )
            
            # Step 3: Clean transcript (remove fillers and pauses)
            cleaned_segments = self._clean_transcript(analysis_result.transcript_segments)
            
            # Step 4: Auto-detect optimal segments
            optimal_segments = self._auto_detect_segments(cleaned_segments, target_duration)
            
            # Step 5: Generate concatenation plan
            concatenation_plan = self._generate_concatenation_plan(optimal_segments)
            
            # Step 6: Create optimization report
            optimization_report = self._create_optimization_report(
                analysis_result, cleaned_segments, optimal_segments, concatenation_plan
            )
            
            return optimization_report
            
        except Exception as e:
            logger.error(f"Error in video optimization: {str(e)}", exc_info=True)
            raise
    
    def _get_platform_duration(self, platform: str) -> float:
        """Get target duration based on social media platform."""
        return self.PLATFORM_DURATIONS.get(platform.lower(), self.PLATFORM_DURATIONS['default'])
    
    def _clean_transcript(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Remove filler words and pauses from transcript segments."""
        cleaned_segments = []
        total_filler_time = 0
        
        for segment in segments:
            original_text = segment.text
            cleaned_text = self._remove_fillers_and_pauses(original_text, segment.language)
            
            # Calculate time saved from removing fillers
            if cleaned_text != original_text:
                # Estimate time saved (rough approximation)
                filler_words_removed = len(original_text.split()) - len(cleaned_text.split())
                estimated_time_saved = filler_words_removed * 0.3  # 0.3 seconds per word
                total_filler_time += estimated_time_saved
            
            cleaned_segment = TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=cleaned_text,
                confidence=segment.confidence,
                language=segment.language,
                speaker=getattr(segment, 'speaker', None)
            )
            cleaned_segments.append(cleaned_segment)
        
        logger.info(f"Removed fillers and pauses, estimated time saved: {total_filler_time:.2f}s")
        return cleaned_segments
    
    def _remove_fillers_and_pauses(self, text: str, language: str) -> str:
        """Remove filler words and pause patterns from text."""
        # Remove pause patterns
        for pattern in self.PAUSE_PATTERNS:
            text = re.sub(pattern, ' ', text)
        
        # Remove filler words based on language
        filler_words = self.FILLER_WORDS.get(language, self.FILLER_WORDS['en'])
        words = text.split()
        filtered_words = [word for word in words if word.lower() not in filler_words]
        return ' '.join(filtered_words)
    
    def _auto_detect_segments(
        self, 
        cleaned_segments: List[TranscriptSegment], 
        target_duration: float
    ) -> List[HighlightSegment]:
        """Auto-detect optimal segments for concatenation."""
        # Convert TranscriptSegment objects to dict format for highlight detector
        segment_dicts = []
        for seg in cleaned_segments:
            segment_dicts.append({
                'start': seg.start,
                'end': seg.end,
                'text': seg.text,
                'duration': seg.duration,
                'confidence': seg.confidence,
                'language': seg.language
            })
        
        # Detect highlights with improved detection
        highlight_segments_dicts = self.highlight_detector.merge_segments(
            segment_dicts,
            target_duration=int(target_duration),  # Convert to int as expected by method
            top_k=3  # Get top 3 highlights
        )
        
        # Convert dict highlight segments to HighlightSegment objects
        highlight_segments_from_detector = []
        for seg_dict in highlight_segments_dicts:
            highlight_seg = HighlightSegment(
                start=seg_dict["start"],
                end=seg_dict["end"],
                duration=seg_dict["duration"],
                score=seg_dict.get("score", 0.5),  # Default score if not provided
                type="highlight",
                keywords=[],
                text=seg_dict.get("text", "")
            )
            highlight_segments_from_detector.append(highlight_seg)
        
        # Convert TranscriptSegment to dict format for trailer selector
        segment_dicts = []
        for seg in cleaned_segments:
            segment_dicts.append({
                'start': seg.start,
                'end': seg.end,
                'text': seg.text,
                'duration': seg.duration,
                'confidence': seg.confidence,
                'language': seg.language
            })
        
        # Select segments optimized for target duration
        trailer_plan = self.select_trailer_segments(
            segment_dicts,
            sum(seg.duration for seg in cleaned_segments),
            target_duration
        )
        
        # Extract selected segments from trailer plan
        selected_segments = trailer_plan.get_all_segments()
        
        # Convert to HighlightSegment objects for compatibility
        highlight_segments = []
        for seg in selected_segments:
            highlight_seg = HighlightSegment(
                start=seg.start,
                end=seg.end,
                duration=seg.duration,
                score=seg.score,
                type=seg.category.value,
                keywords=[],  # Could extract keywords from text if needed
                text=seg.text
            )
            highlight_segments.append(highlight_seg)
        
        # Further optimize by removing low-importance segments
        optimized_segments = self._optimize_segment_selection(highlight_segments, target_duration)
        
        return optimized_segments
    
    def _optimize_segment_selection(
        self, 
        segments: List[HighlightSegment], 
        target_duration: float
    ) -> List[HighlightSegment]:
        """Optimize segment selection by removing low-importance segments."""
        if not segments:
            return segments
        
        # Sort by score (importance)
        sorted_segments = sorted(segments, key=lambda x: x.score, reverse=True)
        
        # Select segments until we reach target duration
        selected = []
        current_duration = 0.0
        
        for segment in sorted_segments:
            if current_duration + segment.duration <= target_duration:
                selected.append(segment)
                current_duration += segment.duration
            elif current_duration >= target_duration * 0.8:  # Stop if we're close to target
                break
        
        return selected
    
    def _generate_concatenation_plan(self, segments: List[HighlightSegment]) -> Dict:
        """Generate optimal concatenation plan."""
        if not segments:
            return {"segments": [], "transitions": [], "total_duration": 0}
        
        # Sort segments by start time to maintain chronological order
        sorted_segments = sorted(segments, key=lambda x: x.start)
        
        concatenation_segments = []
        transitions = []
        total_duration = 0
        
        for i, segment in enumerate(sorted_segments):
            segment_info = {
                "order": i + 1,
                "start_time": segment.start,
                "end_time": segment.end,
                "duration": segment.duration,
                "score": segment.score,
                "type": segment.type,
                "text_preview": segment.text[:50] + "..." if len(segment.text) > 50 else segment.text
            }
            concatenation_segments.append(segment_info)
            total_duration += segment.duration
            
            # Add transition info (except for last segment)
            if i < len(sorted_segments) - 1:
                next_segment = sorted_segments[i + 1]
                transition = {
                    "from_segment": i + 1,
                    "to_segment": i + 2,
                    "transition_type": "smooth_cut",
                    "suggested_gap": 0.1,  # Minimal gap for smooth flow
                    "transition_effect": "crossfade"
                }
                transitions.append(transition)
        
        return {
            "segments": concatenation_segments,
            "transitions": transitions,
            "total_duration": total_duration,
            "segment_count": len(sorted_segments)
        }
    
    def _create_optimization_report(
        self, 
        analysis_result: NarrativeAnalysisResult,
        cleaned_segments: List[TranscriptSegment],
        optimal_segments: List[HighlightSegment],
        concatenation_plan: Dict
    ) -> Dict:
        """Create comprehensive optimization report."""
        original_duration = analysis_result.video_metadata.duration
        optimized_duration = concatenation_plan["total_duration"]
        time_saved = original_duration - optimized_duration
        efficiency = (time_saved / original_duration) * 100 if original_duration > 0 else 0
        
        return {
            "optimization_metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "3.0",
                "language_detected": analysis_result.language,
                "original_duration": original_duration,
                "optimized_duration": optimized_duration,
                "time_saved": time_saved,
                "efficiency_percentage": efficiency
            },
            "transcript_optimization": {
                "original_segments": len(analysis_result.transcript_segments),
                "cleaned_segments": len(cleaned_segments),
                "filler_removal": "Completed",
                "pause_removal": "Completed"
            },
            "segment_optimization": {
                "detected_highlights": len(analysis_result.highlight_segments),
                "selected_segments": len(optimal_segments),
                "segment_selection_method": "Auto-detection with AI scoring"
            },
            "concatenation_plan": concatenation_plan,
            "quality_metrics": {
                "average_confidence": np.mean([s.confidence for s in cleaned_segments]) if cleaned_segments else 0,
                "total_words": sum(len(s.text.split()) for s in cleaned_segments),
                "segment_diversity": len(set(s.type for s in optimal_segments)) if optimal_segments else 0
            }
        }

# Create global instances - these will be properly initialized when imported
narrative_analyzer = None
enhanced_analyzer = None

# Legacy narrative analyzer for backward compatibility
class LegacyNarrativeAnalyzer:
    """Legacy narrative analyzer for backward compatibility."""
    
    def __init__(self):
        self.narrative_segments = []
        
        # Scene type priority configuration
        self.scene_type_priority = {
            "action": 1.0,      # Highest priority
            "drama": 0.9,
            "comedy": 0.8,
            "romance": 0.7,
            "thriller": 0.9,
            "horror": 0.8,
            "sci-fi": 0.7,
            "documentary": 0.6,
            "educational": 0.5,
            "sports": 0.9,
            "gaming": 0.8,
            "music": 0.7,
            "vlog": 0.6,
            "tutorial": 0.5,
            "interview": 0.4,
            "travel": 0.6,
            "food": 0.5,
            "lifestyle": 0.4
        }
        
        # AI override configuration
        self.ai_override_enabled = True
        self.user_override_segments = []
        self.ai_suggestions = []
        
    def enable_ai_override(self) -> None:
        """Enable AI override functionality."""
        self.ai_override_enabled = True
        
    def disable_ai_override(self) -> None:
        """Disable AI override functionality."""
        self.ai_override_enabled = False
        
    def add_user_override_segment(self, segment: Dict) -> None:
        """Add a user-selected segment to override AI suggestions."""
        self.user_override_segments.append(segment)
        
    def clear_user_override_segments(self) -> None:
        """Clear all user override segments."""
        self.user_override_segments = []
        
    def get_ai_suggestions(self, segments: List[Dict]) -> List[Dict]:
        """Generate AI suggestions for segment selection."""
        if not self.ai_override_enabled:
            return []
            
        suggestions = []
        
        # Analyze segments and provide AI recommendations
        for i, segment in enumerate(segments):
            text = segment.get("text", "").lower()
            duration = segment["end"] - segment["start"]
            position_ratio = i / len(segments) if len(segments) > 1 else 0
            
            # Calculate suggestion score based on content analysis
            score = self._calculate_suggestion_score(text, duration, position_ratio)
            
            if score > 0.7:  # High confidence suggestion
                suggestion = {
                    "segment": segment,
                    "reason": self._get_suggestion_reason(text, position_ratio),
                    "confidence": score,
                    "type": "ai_suggestion",
                    "recommended_action": "include"
                }
                suggestions.append(suggestion)
                
        self.ai_suggestions = suggestions
        return suggestions
    
    def _calculate_suggestion_score(self, text: str, duration: float, position_ratio: float) -> float:
        """Calculate AI suggestion score for a segment."""
        score = 0.0
        
        # Content quality indicators
        if len(text.split()) > 10:  # Substantial content
            score += 0.2
            
        # Keyword analysis for engagement
        engagement_keywords = ["amazing", "incredible", "wow", "must see", "important", "key", "essential"]
        for keyword in engagement_keywords:
            if keyword in text:
                score += 0.1
                
        # Position-based scoring
        if 0.1 < position_ratio < 0.9:  # Not at extreme ends
            score += 0.1
            
        # Duration-based scoring
        if 5 <= duration <= 30:  # Optimal duration range
            score += 0.2
            
        # Question or call-to-action indicators
        if "?" in text or any(phrase in text for phrase in ["check this out", "look at this"]):
            score += 0.2
            
        return min(score, 1.0)
    
    def _get_suggestion_reason(self, text: str, position_ratio: float) -> str:
        """Get reason for AI suggestion."""
        reasons = []
        
        if "amazing" in text or "incredible" in text:
            reasons.append("High engagement content detected")
            
        if "?" in text:
            reasons.append("Question format increases viewer interaction")
            
        if 0.2 < position_ratio < 0.8:
            reasons.append("Optimal positioning in video flow")
            
        if len(text.split()) > 15:
            reasons.append("Substantial content value")
            
        return " | ".join(reasons) if reasons else "AI analysis recommends inclusion"
    
    def apply_user_overrides(self, segments: List[Dict]) -> List[Dict]:
        """Apply user overrides to segment selection."""
        if not self.ai_override_enabled or not self.user_override_segments:
            return segments
            
        # Convert user override segments to a set for faster lookup
        override_starts = {seg["start"] for seg in self.user_override_segments}
        
        # Filter segments to include user overrides
        filtered_segments = []
        for segment in segments:
            if segment["start"] in override_starts:
                # Mark as user-selected
                segment_copy = segment.copy()
                segment_copy["selection_source"] = "user_override"
                filtered_segments.append(segment_copy)
            else:
                # Keep AI-selected segments
                segment_copy = segment.copy()
                segment_copy["selection_source"] = "ai_selected"
                filtered_segments.append(segment_copy)
                
        return filtered_segments
        
    def analyze_narrative_structure(
        self, 
        segments: List[Dict],
        video_duration: Optional[float] = None
    ) -> Dict:
        """
        Main method to analyze narrative structure of video segments
        """
        if not segments:
            return {"error": "No segments provided"}
            
        # Reset for new analysis
        self.narrative_segments = []
        
        # Step 1: Score each segment for different narrative elements
        scored_segments = self._score_narrative_elements(segments)
        
        # Step 2: Detect narrative boundaries and transitions
        narrative_boundaries = self._detect_narrative_boundaries(scored_segments)
        
        # Step 3: Create narrative segments
        narrative_segments = self._create_narrative_segments(
            scored_segments, 
            narrative_boundaries,
            video_duration
        )
        
        # Step 4: Optimize narrative flow
        optimized_segments = self._optimize_narrative_flow(narrative_segments)
        
        # Step 5: Generate concatenation plan
        concatenation_plan = self._generate_concatenation_plan(optimized_segments)
        
        return {
            "narrative_segments": optimized_segments,
            "concatenation_plan": concatenation_plan,
            "narrative_flow": self._analyze_narrative_flow(optimized_segments),
            "total_segments": len(optimized_segments),
            "estimated_final_duration": sum(seg["duration"] for seg in optimized_segments)
        }
    
    def _score_narrative_elements(self, segments: List[Dict]) -> List[Dict]:
        """
        Score each segment for different narrative element types
        """
        scored_segments = []
        
        # Analyze overall content type for context
        content_analysis = content_type_analyzer.analyze_content_type(segments)
        content_type_priority = content_type_analyzer.get_content_type_priority(content_analysis.primary_type)
        
        for i, segment in enumerate(segments):
            text = segment.get("text", "").lower()
            duration = segment["end"] - segment["start"]
            position_ratio = i / len(segments) if len(segments) > 1 else 0
            
            scores = {
                "opening": self._score_opening(text, position_ratio, duration),
                "hook": self._score_hook(text, position_ratio, duration),
                "rising_action": self._score_rising_action(text, position_ratio, duration),
                "emotional_moment": self._score_emotional_moment(text, duration),
                "action_sequence": self._score_action_sequence(text, duration),
                "climax": self._score_climax(text, position_ratio, duration),
                "conclusion": self._score_conclusion(text, position_ratio, duration)
            }
            
            # Add emotional analysis
            emotional_analysis = self._analyze_emotional_content(text)
            
            # Apply content type priority boost
            for element_type in scores:
                if self._should_boost_for_content_type(element_type, content_analysis.primary_type):
                    scores[element_type] *= content_type_priority
            
            scored_segment = {
                **segment,
                "narrative_scores": scores,
                "emotional_analysis": emotional_analysis,
                "position_ratio": position_ratio,
                "primary_element": max(scores.items(), key=lambda x: x[1])[0],
                "max_score": max(scores.values()),
                "content_type": content_analysis.primary_type.value,
                "content_confidence": content_analysis.confidence
            }
            
            scored_segments.append(scored_segment)
            
        return scored_segments
    
    def _should_boost_for_content_type(self, element_type: str, content_type: Any) -> bool:
        """Determine if an element type should be boosted for a given content type."""
        content_boosts = {
            "action": ["action_sequence", "climax", "rising_action"],
            "sports": ["action_sequence", "climax", "rising_action"],
            "gaming": ["action_sequence", "climax", "hook"],
            "comedy": ["emotional_moment", "hook", "opening"],
            "music": ["emotional_moment", "hook", "climax"],
            "drama": ["emotional_moment", "climax", "rising_action"],
            "romance": ["emotional_moment", "hook", "conclusion"],
            "thriller": ["climax", "rising_action", "hook"],
            "horror": ["climax", "emotional_moment", "hook"],
            "educational": ["opening", "conclusion", "rising_action"],
            "tutorial": ["opening", "conclusion", "rising_action"],
            "documentary": ["opening", "conclusion", "emotional_moment"]
        }
        
        content_type_name = content_type.value if hasattr(content_type, 'value') else str(content_type)
        boosted_elements = content_boosts.get(content_type_name, [])
        return element_type in boosted_elements
    
    def _score_opening(self, text: str, position_ratio: float, duration: float) -> float:
        """
        Score segment as potential opening
        """
        score = 0.0
        
        # Position weight (openings are usually at the beginning)
        if position_ratio < 0.15:
            score += 8
        elif position_ratio < 0.3:
            score += 4
            
        # Keyword matching
        for keyword in ["welcome", "hello", "today", "going to", "start", "begin", "introduce", "story", "tell you", "once upon", "let me"]:
            if keyword in text:
                score += 2
                
        # Duration preference (not too short, not too long)
        if 5 <= duration <= 20:
            score += 3
            
        # Introduction patterns
        if any(pattern in text for pattern in ["my name", "i'm", "this is", "welcome to"]):
            score += 4
            
        return score
    
    def _score_hook(self, text: str, position_ratio: float, duration: float) -> float:
        """
        Score segment as potential hook
        """
        score = 0.0
        
        # Position weight (hooks are usually early but after opening)
        if 0.05 < position_ratio < 0.25:
            score += 6
        elif position_ratio < 0.4:
            score += 3
            
        # Keyword matching
        for keyword in ["but", "however", "suddenly", "then", "what if", "imagine", "secret", "shocking", "unbelievable", "never", "always", "warning", "danger", "mystery", "reveal"]:
            if keyword in text:
                score += 3
                
        # Question patterns (hooks often pose questions)
        question_count = text.count("?")
        score += min(question_count * 2, 6)
        
        # Dramatic patterns
        if any(pattern in text for pattern in ["but what", "little did", "however", "suddenly"]):
            score += 4
            
        return score
    
    def _score_rising_action(self, text: str, position_ratio: float, duration: float) -> float:
        """
        Score segment as potential rising action
        """
        score = 0.0
        
        # Position weight (rising action is in the middle)
        if 0.2 < position_ratio < 0.7:
            score += 5
        elif 0.1 < position_ratio < 0.8:
            score += 2
            
        # Progression indicators
        progression_words = ["then", "next", "after", "meanwhile", "later", "soon"]
        for word in progression_words:
            if word in text:
                score += 2
                
        # Conflict indicators
        conflict_words = ["problem", "challenge", "difficult", "struggle", "against"]
        for word in conflict_words:
            if word in text:
                score += 3
                
        return score
    
    def _score_emotional_moment(self, text: str, duration: float) -> float:
        """
        Score segment as potential emotional moment
        """
        score = 0.0
        
        # Check all emotional categories
        emotional_keywords = {
            "comedy": ["funny", "hilarious", "joke", "laugh", "humor", "ridiculous", "silly"],
            "sadness": ["sad", "cry", "tears", "heartbreak", "loss", "grief", "tragic"],
            "excitement": ["amazing", "incredible", "wow", "fantastic", "awesome", "unbelievable"],
            "fear": ["scary", "terrifying", "afraid", "panic", "horror", "nightmare"],
            "anger": ["angry", "furious", "rage", "mad", "hate", "disgusting"]
        }
        
        for emotion_type, keywords in emotional_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    score += 3
                    
        # Emotional intensifiers
        intensifiers = ["very", "extremely", "incredibly", "absolutely", "completely"]
        for intensifier in intensifiers:
            if intensifier in text:
                score += 1
                
        # Exclamation marks indicate emotion
        exclamation_count = text.count("!")
        score += min(exclamation_count * 2, 4)
        
        return score
    
    def _score_action_sequence(self, text: str, duration: float) -> float:
        """
        Score segment as potential action sequence
        """
        score = 0.0
        
        # Action keywords
        for keyword in ["fight", "battle", "chase", "run", "attack", "defend", "explosion", "crash", "hit", "strike", "fast", "quick", "action", "intense"]:
            if keyword in text:
                score += 3
                
        # Fast-paced indicators
        if duration < 10:  # Short, punchy segments
            score += 2
            
        # Action verbs pattern
        action_verbs = ["run", "jump", "fight", "chase", "escape", "attack"]
        for verb in action_verbs:
            if verb in text:
                score += 2
                
        return score
    
    def _score_climax(self, text: str, position_ratio: float, duration: float) -> float:
        """
        Score segment as potential climax
        """
        score = 0.0
        
        # Position weight (climax is usually in the latter part)
        if 0.6 < position_ratio < 0.9:
            score += 8
        elif 0.5 < position_ratio < 0.95:
            score += 4
            
        # Climax keywords
        for keyword in ["finally", "ultimate", "decisive", "turning point", "crucial", "everything", "all or nothing", "final", "last chance", "peak"]:
            if keyword in text:
                score += 4
                
        # Intensity indicators
        if any(word in text for word in ["most", "biggest", "ultimate", "final"]):
            score += 3
            
        return score
    
    def _score_conclusion(self, text: str, position_ratio: float, duration: float) -> float:
        """
        Score segment as potential conclusion
        """
        score = 0.0
        
        # Position weight (conclusions are at the end)
        if position_ratio > 0.85:
            score += 8
        elif position_ratio > 0.7:
            score += 4
            
        # Conclusion keywords
        for keyword in ["conclusion", "end", "finally", "summary", "wrap up", "that's all", "goodbye", "see you", "thanks", "remember", "takeaway"]:
            if keyword in text:
                score += 3
                
        # Closing patterns
        if any(pattern in text for pattern in ["in conclusion", "to summarize", "that's all"]):
            score += 5
            
        return score
    
    def _analyze_emotional_content(self, text: str) -> Dict:
        """
        Analyze emotional content of text
        """
        emotions = {}
        total_emotional_words = 0
        
        emotional_keywords = {
            "comedy": ["funny", "hilarious", "joke", "laugh", "humor", "ridiculous", "silly"],
            "sadness": ["sad", "cry", "tears", "heartbreak", "loss", "grief", "tragic"],
            "excitement": ["amazing", "incredible", "wow", "fantastic", "awesome", "unbelievable"],
            "fear": ["scary", "terrifying", "afraid", "panic", "horror", "nightmare"],
            "anger": ["angry", "furious", "rage", "mad", "hate", "disgusting"]
        }
        
        for emotion_type, keywords in emotional_keywords.items():
            count = sum(1 for keyword in keywords if keyword in text)
            emotions[emotion_type] = count
            total_emotional_words += count
            
        # Calculate emotional intensity
        emotional_intensity = min(total_emotional_words / 3, 1.0)
        
        # Determine dominant emotion
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])[0] if total_emotional_words > 0 else "neutral"
        
        return {
            "emotions": emotions,
            "emotional_intensity": emotional_intensity,
            "dominant_emotion": dominant_emotion,
            "total_emotional_words": total_emotional_words
        }
    
    def _detect_narrative_boundaries(self, scored_segments: List[Dict]) -> List[int]:
        """
        Detect boundaries between different narrative elements
        """
        boundaries = [0]  # Always start with first segment
        
        for i in range(1, len(scored_segments)):
            current = scored_segments[i]
            previous = scored_segments[i-1]
            
            # Check for significant change in narrative element type
            if current["primary_element"] != previous["primary_element"]:
                # Additional validation based on score difference
                if current["max_score"] > 3 and previous["max_score"] > 3:
                    boundaries.append(i)
        
        boundaries.append(len(scored_segments))  # Always end with last segment
        return boundaries
    
    def _create_narrative_segments(
        self, 
        scored_segments: List[Dict], 
        boundaries: List[int],
        video_duration: Optional[float] = None
    ) -> List[Dict]:
        """
        Create narrative segments from boundaries
        """
        narrative_segments = []
        
        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i + 1]
            
            segment_group = scored_segments[start_idx:end_idx]
            
            if not segment_group:
                continue
                
            # Determine the dominant narrative element for this group
            element_counts = {}
            for seg in segment_group:
                element = seg["primary_element"]
                element_counts[element] = element_counts.get(element, 0) + 1
                
            dominant_element = max(element_counts.items(), key=lambda x: x[1])[0]
            
            # Calculate segment properties
            start_time = segment_group[0]["start"]
            end_time = segment_group[-1]["end"]
            duration = end_time - start_time
            
            # Combine text
            combined_text = " ".join(seg.get("text", "") for seg in segment_group)
            
            # Calculate confidence and importance
            avg_score = float(np.mean([seg["max_score"] for seg in segment_group]))
            confidence = float(min(avg_score / 10, 1.0))
            
            # Calculate emotional intensity
            emotional_intensities = [seg["emotional_analysis"]["emotional_intensity"] for seg in segment_group]
            avg_emotional_intensity = float(np.mean(emotional_intensities))
            
            # Calculate narrative importance based on element type and position
            importance_weights = {
                "opening": 0.8,
                "hook": 0.9,
                "rising_action": 0.6,
                "emotional_moment": 0.7,
                "action_sequence": 0.8,
                "climax": 1.0,
                "conclusion": 0.7
            }
            
            base_importance = importance_weights.get(dominant_element, 0.5)
            position_ratio = start_time / (video_duration or end_time) if (video_duration or end_time) > 0 else 0
            
            if dominant_element == "hook" and position_ratio < 0.3:
                base_importance += 0.1
            elif dominant_element == "climax" and 0.6 < position_ratio < 0.9:
                base_importance += 0.1
            
            narrative_importance = min(base_importance, 1.0)
            
            narrative_segment = {
                "element_type": dominant_element,
                "start": start_time,
                "end": end_time,
                "duration": duration,
                "confidence": confidence,
                "text": combined_text,
                "emotional_intensity": avg_emotional_intensity,
                "narrative_importance": narrative_importance,
                "segments": segment_group
            }
            
            narrative_segments.append(narrative_segment)
            
        return narrative_segments
    
    def _optimize_narrative_flow(self, segments: List[Dict]) -> List[Dict]:
        """
        Optimize segments for better narrative flow
        """
        if not segments:
            return segments
            
        # Sort by narrative importance and maintain some chronological order
        segments_with_priority = []
        
        for segment in segments:
            # Calculate priority score
            priority = (
                segment["narrative_importance"] * 0.4 + 
                segment["confidence"] * 0.3 + 
                segment["emotional_intensity"] * 0.2 + 
                (1.0 if segment["element_type"] in ["opening", "hook", "climax"] else 0.5) * 0.1
            )
            
            segments_with_priority.append((segment, priority))
            
        # Sort by priority but maintain narrative order for key elements
        key_elements = ["opening", "hook", "climax", "conclusion"]
        
        key_segments = [seg for seg, _ in segments_with_priority if seg["element_type"] in key_elements]
        other_segments = [seg for seg, priority in segments_with_priority if seg["element_type"] not in key_elements]
        
        # Sort key segments by their natural narrative order
        key_segments.sort(key=lambda x: x["start"])
        
        # Sort other segments by priority
        other_segments.sort(key=lambda x: segments_with_priority[[s for s, _ in segments_with_priority].index(x)][1], reverse=True)
        
        # Combine maintaining narrative flow
        optimized = []
        
        # Add opening if exists
        opening_segments = [s for s in key_segments if s["element_type"] == "opening"]
        if opening_segments:
            optimized.extend(opening_segments)
            
        # Add hook if exists
        hook_segments = [s for s in key_segments if s["element_type"] == "hook"]
        if hook_segments:
            optimized.extend(hook_segments)
            
        # Add best other segments (rising action, emotional moments, action)
        optimized.extend(other_segments[:3])  # Limit to top 3 for pacing
        
        # Add climax if exists
        climax_segments = [s for s in key_segments if s["element_type"] == "climax"]
        if climax_segments:
            optimized.extend(climax_segments)
            
        # Add conclusion if exists
        conclusion_segments = [s for s in key_segments if s["element_type"] == "conclusion"]
        if conclusion_segments:
            optimized.extend(conclusion_segments)
            
        return optimized
    
    def _generate_concatenation_plan(self, segments: List[Dict]) -> Dict:
        """
        Generate a plan for concatenating segments
        """
        if not segments:
            return {"segments": [], "transitions": []}
            
        concatenation_segments = []
        transitions = []
        
        for i, segment in enumerate(segments):
            # Add segment info
            segment_info = {
                "order": i + 1,
                "element_type": segment["element_type"],
                "start_time": segment["start"],
                "end_time": segment["end"],
                "duration": segment["duration"],
                "confidence": segment["confidence"],
                "narrative_importance": segment["narrative_importance"],
                "text_preview": segment["text"][:100] + "..." if len(segment["text"]) > 100 else segment["text"]
            }
            concatenation_segments.append(segment_info)
            
            # Add transition info (except for last segment)
            if i < len(segments) - 1:
                next_segment = segments[i + 1]
                transition = {
                    "from_element": segment["element_type"],
                    "to_element": next_segment["element_type"],
                    "transition_type": self._determine_transition_type(segment["element_type"], next_segment["element_type"]),
                    "suggested_effect": self._suggest_transition_effect(segment["element_type"], next_segment["element_type"])
                }
                transitions.append(transition)
                
        return {
            "segments": concatenation_segments,
            "transitions": transitions,
            "total_duration": sum(seg.get("duration", 0) for seg in segments),
            "segment_count": len(segments)
        }
    
    def _determine_transition_type(self, from_element: str, to_element: str) -> str:
        """
        Determine appropriate transition type between elements
        """
        transition_map = {
            ("opening", "hook"): "smooth",
            ("hook", "rising_action"): "build",
            ("rising_action", "climax"): "intensify",
            ("climax", "conclusion"): "resolve",
            ("emotional_moment", "action_sequence"): "contrast",
            ("action_sequence", "emotional_moment"): "calm"
        }
        
        return transition_map.get((from_element, to_element), "cut")
    
    def _suggest_transition_effect(self, from_element: str, to_element: str) -> str:
        """
        Suggest visual/audio transition effect
        """
        effect_map = {
            "smooth": "fade",
            "build": "crossfade_with_music_build",
            "intensify": "quick_cut_with_sound_effect",
            "resolve": "slow_fade_with_music_fade",
            "contrast": "hard_cut",
            "calm": "fade_to_black_then_fade_in",
            "cut": "straight_cut"
        }
        
        transition_type = self._determine_transition_type(from_element, to_element)
        return effect_map.get(transition_type, "straight_cut")
    
    def _analyze_narrative_flow(self, segments: List[Dict]) -> str:
        """
        Analyze and describe the narrative flow
        """
        if not segments:
            return "No narrative structure detected"
            
        element_sequence = [seg["element_type"] for seg in segments]
        
        # Check for complete narrative arc
        has_opening = any(elem == "opening" for elem in element_sequence)
        has_hook = any(elem == "hook" for elem in element_sequence)
        has_climax = any(elem == "climax" for elem in element_sequence)
        has_conclusion = any(elem == "conclusion" for elem in element_sequence)
        
        flow_quality = "Complete" if all([has_opening, has_hook, has_climax, has_conclusion]) else "Partial"
        
        # Analyze pacing
        total_duration = sum(seg["duration"] for seg in segments)
        avg_segment_duration = total_duration / len(segments)
        
        if avg_segment_duration < 15:
            pacing = "Fast-paced"
        elif avg_segment_duration > 30:
            pacing = "Slow-paced"
        else:
            pacing = "Well-paced"
            
        return f"{flow_quality} narrative arc with {pacing.lower()} segments"


# Create global instance
legacy_narrative_analyzer = LegacyNarrativeAnalyzer()


def analyze_video_narrative(video_path: str) -> Dict[str, Any]:
    """
    Standalone function to analyze video narrative for backward compatibility.
    This function uses the legacy narrative analyzer to provide basic metadata.
    
    Args:
        video_path: Path to the video file to analyze
        
    Returns:
        Dict containing basic video metadata and narrative analysis
    """
    try:
        import subprocess
        import json
        
        # Use ffprobe to get basic video metadata
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Exception(f"ffprobe failed: {result.stderr}")
        
        metadata = json.loads(result.stdout)
        
        # Extract relevant information
        format_info = metadata.get('format', {})
        streams = metadata.get('streams', [])
        
        # Find video stream
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), {})
        
        # Basic metadata extraction
        duration = float(format_info.get('duration', 0))
        width = video_stream.get('width', 0)
        height = video_stream.get('height', 0)
        codec_name = video_stream.get('codec_name', 'unknown')
        
        # Return basic metadata structure
        return {
            "title": f"Video Analysis - {video_stream.get('codec_name', 'unknown')}",
            "language": "Unknown",  # Would need transcription to detect
            "genre": "Unknown",     # Would need AI analysis to detect
            "release_year": "Unknown",  # Would need AI analysis to detect
            "starring": "Unknown",      # Would need AI analysis to detect
            "duration": duration,
            "resolution": f"{width}x{height}" if width and height else "Unknown",
            "codec": codec_name,
            "file_size": format_info.get('size', '0'),
            "analysis_complete": True
        }
        
    except Exception as e:
        logger.error(f"Error analyzing video narrative: {str(e)}")
        return {
            "title": "Unknown",
            "language": "Unknown",
            "genre": "Unknown",
            "release_year": "Unknown",
            "starring": "Unknown",
            "error": str(e)
        }
