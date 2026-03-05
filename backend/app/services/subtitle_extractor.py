# backend/app/services/subtitle_extractor.py
"""
Subtitle Extraction Service

This module provides functionality to:
1. Extract embedded subtitles from video files
2. Parse SRT/VTT/ASS subtitle formats
3. Convert subtitles to transcription format for segment selection
4. Allow optional subtitle embedding in output videos (user can toggle on/off)

This avoids re-transcribing videos that already have embedded subtitles.
"""

import os
import re
import logging
import warnings

warnings.filterwarnings("ignore")
import subprocess
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
FFPROBE_TIMEOUT_SECONDS = float(os.getenv("FFPROBE_TIMEOUT_SECONDS", "20"))
FFMPEG_SUBTITLE_TIMEOUT_SECONDS = float(
    os.getenv(
        "FFMPEG_SUBTITLE_TIMEOUT_SECONDS",
        "360"
    )
)


@dataclass
class SubtitleInfo:
    """Information about a subtitle track in a video."""
    index: int
    language: str
    title: str
    codec: str
    is_default: bool
    is_forced: bool


def get_subtitle_tracks(video_path: str) -> List[SubtitleInfo]:
    """
    Get all subtitle tracks from a video file using FFprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        List of SubtitleInfo objects for each subtitle track
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "s",  # Select subtitle streams
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS
        )
        
        if result.returncode != 0:
            logger.warning(f"FFprobe error: {result.stderr}")
            return []
        
        data = json.loads(result.stdout)
        tracks = []
        
        for stream in data.get("streams", []):
            track = SubtitleInfo(
                index=stream.get("index", 0),
                language=stream.get("tags", {}).get("language", "und"),
                title=stream.get("tags", {}).get("title", ""),
                codec=stream.get("codec_name", "unknown"),
                is_default=stream.get("disposition", {}).get("default", 0) == 1,
                is_forced=stream.get("disposition", {}).get("forced", 0) == 1
            )
            tracks.append(track)
            logger.info(f"Found subtitle track: index={track.index}, lang={track.language}, codec={track.codec}")
        
        return tracks
        
    except Exception as e:
        logger.error(f"Error getting subtitle tracks: {e}")
        return []


def extract_subtitle_track(
    video_path: str,
    output_path: str,
    track_index: Optional[int] = None,
    language: Optional[str] = None
) -> Optional[str]:
    """
    Extract a subtitle track from a video file.
    
    Args:
        video_path: Path to the video file
        output_path: Path to save the extracted subtitle
        track_index: Specific track index to extract (optional)
        language: Language code to extract (e.g., 'en', 'eng')
        
    Returns:
        Path to the extracted subtitle file, or None if extraction failed
    """
    try:
        # Get available tracks
        tracks = get_subtitle_tracks(video_path)
        
        if not tracks:
            logger.info("No subtitle tracks found in video")
            return None
        
        # Select track to extract
        selected_track = None
        
        if track_index is not None:
            # Find track by index
            for track in tracks:
                if track.index == track_index:
                    selected_track = track
                    break
        elif language:
            # Find track by language
            for track in tracks:
                if track.language.lower().startswith(language.lower()):
                    selected_track = track
                    break
        else:
            # Select first track, preferring default
            for track in tracks:
                if track.is_default:
                    selected_track = track
                    break
            if not selected_track:
                selected_track = tracks[0]
        
        if not selected_track:
            logger.warning("No suitable subtitle track found")
            return None
        
        logger.info(f"Extracting subtitle track {selected_track.index} ({selected_track.language})")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Extract subtitle using FFmpeg
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-map", f"0:{selected_track.index}",
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFMPEG_SUBTITLE_TIMEOUT_SECONDS
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg extraction error: {result.stderr}")
            return None
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Subtitle extracted to {output_path}")
            return output_path
        else:
            logger.warning("Extracted subtitle file is empty or doesn't exist")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting subtitle: {e}")
        return None


def parse_srt_timestamp(timestamp: str) -> float:
    """
    Parse SRT timestamp to seconds.
    
    Args:
        timestamp: SRT timestamp string (HH:MM:SS,mmm)
        
    Returns:
        Time in seconds
    """
    # Handle both comma and dot for milliseconds
    timestamp = timestamp.replace(',', '.')
    
    parts = timestamp.strip().split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return 0.0


def parse_srt(srt_path: str) -> List[Dict]:
    """
    Parse SRT subtitle file to segment format.
    
    Args:
        srt_path: Path to the SRT file
        
    Returns:
        List of segments with 'start', 'end', 'text' keys
    """
    segments = []
    
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # SRT format: index, timestamp, text, blank line
        pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n(.*?)(?=\n\n|\n*$)'
        
        matches = re.findall(pattern, content, re.DOTALL)
        
        for match in matches:
            index, start_time, end_time, text = match
            
            segment = {
                'start': parse_srt_timestamp(start_time),
                'end': parse_srt_timestamp(end_time),
                'text': text.strip().replace('\n', ' ')
            }
            segments.append(segment)
        
        logger.info(f"Parsed {len(segments)} segments from SRT file")
        return segments
        
    except Exception as e:
        logger.error(f"Error parsing SRT file: {e}")
        return []


def parse_vtt(vtt_path: str) -> List[Dict]:
    """
    Parse VTT (WebVTT) subtitle file to segment format.
    
    Args:
        vtt_path: Path to the VTT file
        
    Returns:
        List of segments with 'start', 'end', 'text' keys
    """
    segments = []
    
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove WEBVTT header
        if content.startswith('WEBVTT'):
            content = content.split('\n\n', 1)[1] if '\n\n' in content else content
        
        # VTT timestamp format: HH:MM:SS.mmm or MM:SS.mmm
        pattern = r'(\d{1,2}:?\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:?\d{2}:\d{2}\.\d{3})\s*(?:.*?\n)?(.*?)(?=\n\n|\n*$)'
        
        matches = re.findall(pattern, content, re.DOTALL)
        
        for start_time, end_time, text in matches:
            # Handle both HH:MM:SS.mmm and MM:SS.mmm formats
            def parse_vtt_timestamp(ts: str) -> float:
                parts = ts.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = parts
                    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                elif len(parts) == 2:
                    minutes, seconds = parts
                    return int(minutes) * 60 + float(seconds)
                return 0.0
            
            segment = {
                'start': parse_vtt_timestamp(start_time),
                'end': parse_vtt_timestamp(end_time),
                'text': text.strip().replace('\n', ' ')
            }
            segments.append(segment)
        
        logger.info(f"Parsed {len(segments)} segments from VTT file")
        return segments
        
    except Exception as e:
        logger.error(f"Error parsing VTT file: {e}")
        return []


def parse_ass(ass_path: str) -> List[Dict]:
    """
    Parse ASS/SSA subtitle file to segment format.
    
    Args:
        ass_path: Path to the ASS file
        
    Returns:
        List of segments with 'start', 'end', 'text' keys
    """
    segments = []
    
    try:
        with open(ass_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the Events section
        events_start = content.find('[Events]')
        if events_start == -1:
            return []
        
        events_content = content[events_start:]
        
        # ASS format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        pattern = r'Dialogue:\s*\d+,(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2}),.*?,.*?,.*?,.*?,.*?,.*?,(.+)'
        
        matches = re.findall(pattern, events_content)
        
        for start_time, end_time, text in matches:
            def parse_ass_timestamp(ts: str) -> float:
                # ASS format: H:MM:SS.cc
                parts = ts.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = parts
                    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                return 0.0
            
            # Clean ASS formatting tags
            clean_text = re.sub(r'\{.*?\}', '', text)
            clean_text = clean_text.replace('\\N', ' ').strip()
            
            segment = {
                'start': parse_ass_timestamp(start_time),
                'end': parse_ass_timestamp(end_time),
                'text': clean_text
            }
            segments.append(segment)
        
        logger.info(f"Parsed {len(segments)} segments from ASS file")
        return segments
        
    except Exception as e:
        logger.error(f"Error parsing ASS file: {e}")
        return []


def parse_subtitle_file(subtitle_path: str) -> List[Dict]:
    """
    Parse any supported subtitle file format.
    
    Args:
        subtitle_path: Path to the subtitle file
        
    Returns:
        List of segments with 'start', 'end', 'text' keys
    """
    ext = os.path.splitext(subtitle_path)[1].lower()
    
    if ext == '.srt':
        return parse_srt(subtitle_path)
    elif ext == '.vtt':
        return parse_vtt(subtitle_path)
    elif ext in ['.ass', '.ssa']:
        return parse_ass(subtitle_path)
    else:
        logger.warning(f"Unsupported subtitle format: {ext}")
        return []


def extract_and_parse_subtitles(
    video_path: str,
    output_dir: str,
    track_index: Optional[int] = None,
    language: Optional[str] = None
) -> Tuple[Optional[str], List[Dict]]:
    """
    Extract subtitles from video and parse them.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted subtitle
        track_index: Specific track index to extract
        language: Language code to extract
        
    Returns:
        Tuple of (subtitle_file_path, segments_list)
    """
    # Check for existing subtitle files
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    for ext in ['.srt', '.vtt', '.ass']:
        existing_path = os.path.join(output_dir, f"{video_name}{ext}")
        if os.path.exists(existing_path):
            logger.info(f"Found existing subtitle file: {existing_path}")
            segments = parse_subtitle_file(existing_path)
            if segments:
                return existing_path, segments
    
    # Try to extract embedded subtitles
    subtitle_path = os.path.join(output_dir, f"{video_name}_extracted.srt")
    
    extracted_path = extract_subtitle_track(
        video_path,
        subtitle_path,
        track_index=track_index,
        language=language
    )
    
    if extracted_path:
        segments = parse_subtitle_file(extracted_path)
        if segments:
            return extracted_path, segments
    
    return None, []


def subtitles_to_transcription_format(
    segments: List[Dict],
    video_duration: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convert subtitle segments to Whisper transcription format.
    
    This allows the subtitle data to be used with the existing
    segment selection and video processing pipeline.
    
    Args:
        segments: List of subtitle segments
        video_duration: Total video duration (optional)
        
    Returns:
        Transcription data in Whisper format
    """
    if not segments:
        return {
            "text": "",
            "segments": [],
            "language": "unknown"
        }
    
    # Combine all text
    full_text = " ".join(seg.get("text", "") for seg in segments)
    
    # Calculate total duration from segments if not provided
    if video_duration is None:
        video_duration = max(seg.get("end", 0) for seg in segments) if segments else 0
    
    # Format segments for compatibility
    formatted_segments = []
    for i, seg in enumerate(segments):
        formatted_seg = {
            "id": i,
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": seg.get("text", ""),
            "tokens": [],  # Not available from subtitles
            "temperature": 0.0,
            "avg_logprob": 0.0,
            "compression_ratio": 0.0,
            "no_speech_prob": 0.0
        }
        formatted_segments.append(formatted_seg)
    
    return {
        "text": full_text,
        "segments": formatted_segments,
        "language": "extracted",  # Mark as extracted from video
        "duration": video_duration
    }


def format_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp string HH:MM:SS,mmm."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    millis = int((secs - int(secs)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{int(secs):02d},{millis:03d}"


def write_srt(segments: List[Dict], output_path: str):
    """Write a basic SRT file from whisper-style segments.

    Each segment dict is expected to have 'start', 'end', and 'text' keys.

    Args:
        segments: List of segment dictionaries with 'start', 'end', and 'text' keys
        output_path: Path where the SRT file will be written

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, start=1):
                start = format_timestamp(seg.get('start', 0))
                end = format_timestamp(seg.get('end', 0))
                text = seg.get('text', '').replace('\n', ' ')
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        logger.info(f"Generated SRT file at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing SRT file: {e}")
        return False


def split_text_for_youtube_style(text: str, max_chars_per_line: int = 42) -> str:
    """
    Split text into lines suitable for YouTube-style subtitles.
    
    Args:
        text: Input text to split
        max_chars_per_line: Maximum characters per line (default: 42)
        
    Returns:
        Formatted text with line breaks
    """
    if len(text) <= max_chars_per_line:
        return text
    
    # Split into words
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        # Check if adding this word would exceed the limit
        if len(current_line) + len(word) + (1 if current_line else 0) <= max_chars_per_line:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
        else:
            # Start a new line
            if current_line:
                lines.append(current_line)
            current_line = word
    
    # Add the last line
    if current_line:
        lines.append(current_line)
    
    # Limit to maximum 2 lines
    if len(lines) > 2:
        # Try to merge lines intelligently
        if len(lines[0]) + len(lines[1]) + 1 <= max_chars_per_line * 1.5:
            lines = [" ".join(lines[:2]), " ".join(lines[2:])]
        else:
            lines = lines[:2]
    
    return "\n".join(lines)


def write_youtube_style_srt(segments: List[Dict], output_path: str, max_chars_per_line: int = 42):
    """Write a YouTube-style SRT file with proper line breaks.

    Args:
        segments: List of segment dictionaries with 'start', 'end', and 'text' keys
        output_path: Path where the SRT file will be written
        max_chars_per_line: Maximum characters per line (default: 42)

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, start=1):
                start = format_timestamp(seg.get('start', 0))
                end = format_timestamp(seg.get('end', 0))
                text = seg.get('text', '')
                
                # Format text for YouTube style
                formatted_text = split_text_for_youtube_style(text, max_chars_per_line)
                
                f.write(f"{i}\n{start} --> {end}\n{formatted_text}\n\n")
        logger.info(f"Generated YouTube-style SRT file at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing YouTube-style SRT file: {e}")
        return False


def generate_word_level_subtitles(segments: List[Dict], output_path: str):
    """Generate word-level timestamps for subtitles.
    
    This creates more granular subtitle segments for better timing.
    
    Args:
        segments: List of segment dictionaries with 'start', 'end', and 'text' keys
        output_path: Path where the word-level SRT file will be written
        
    Returns:
        True if successful, False otherwise
    """
    try:
        word_segments = []
        
        for seg in segments:
            start_time = seg.get('start', 0)
            end_time = seg.get('end', 0)
            text = seg.get('text', '')
            words = text.split()
            
            if not words:
                continue
                
            # Distribute time evenly among words (simple approach)
            # In a real implementation, you'd use word-level timestamps from Whisper
            segment_duration = end_time - start_time
            words_per_segment = 3  # Group words into small chunks
            
            for i in range(0, len(words), words_per_segment):
                chunk = words[i:i + words_per_segment]
                chunk_text = " ".join(chunk)
                
                # Calculate chunk timing
                chunk_start = start_time + (i / len(words)) * segment_duration
                chunk_end = start_time + ((i + words_per_segment) / len(words)) * segment_duration
                
                word_segments.append({
                    'start': chunk_start,
                    'end': chunk_end,
                    'text': chunk_text
                })
        
        # Write the word-level SRT
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(word_segments, start=1):
                start = format_timestamp(seg.get('start', 0))
                end = format_timestamp(seg.get('end', 0))
                text = split_text_for_youtube_style(seg.get('text', ''))
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
        
        logger.info(f"Generated word-level SRT file at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error generating word-level subtitles: {e}")
        return False


def convert_to_multiple_languages(segments: List[Dict], languages: List[str], output_dir: str):
    """Convert subtitles to multiple languages using translation API.
    
    Args:
        segments: List of segment dictionaries
        languages: List of language codes to translate to
        output_dir: Directory to save translated subtitle files
        
    Returns:
        Dictionary mapping language codes to file paths
    """
    translated_files = {}
    
    try:
        for lang in languages:
            # In a real implementation, you'd use a translation API like Google Translate
            # For now, we'll just copy the original with language suffix
            translated_segments = []
            for seg in segments:
                translated_segments.append({
                    'start': seg.get('start', 0),
                    'end': seg.get('end', 0),
                    'text': f"[{lang.upper()}] {seg.get('text', '')}"  # Placeholder
                })
            
            output_path = os.path.join(output_dir, f"subtitles_{lang}.srt")
            if write_youtube_style_srt(translated_segments, output_path):
                translated_files[lang] = output_path
        
        logger.info(f"Generated subtitles for {len(translated_files)} languages")
        return translated_files
        
    except Exception as e:
        logger.error(f"Error converting to multiple languages: {e}")
        return translated_files


def write_vtt(srt_path: str, vtt_path: str) -> bool:
    """Convert SRT file to VTT format.

    VTT is a web-friendly subtitle format that's compatible with most browsers.
    The main difference is the header and timestamp format (comma instead of dot).

    Args:
        srt_path: Path to the source SRT file
        vtt_path: Path where the VTT file will be written

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(srt_path, 'r', encoding='utf-8') as fin, open(vtt_path, 'w', encoding='utf-8') as fout:
            fout.write("WEBVTT\n\n")
            for line in fin:
                # Replace comma with dot in timestamps (SRT uses comma, VTT uses dot)
                # Keep the rest of the content unchanged
                fout.write(line.replace(',', '.'))
        logger.info(f"Generated VTT file at {vtt_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing VTT file: {e}")
        return False


def generate_subtitles_for_video(
    video_path: str,
    output_dir: str,
    filename_prefix: str = "subtitles"
) -> Optional[str]:
    """Transcribe a video and save SRT/VTT subtitle files.

    This helper extracts audio from the provided video, runs the
    transcription service and then writes an .srt file (and a .vtt
    companion). Returns the path to the .srt file or ``None`` if the
    generation failed.

    Args:
        video_path: Path to the video file to transcribe
        output_dir: Directory where subtitle files will be saved
        filename_prefix: Prefix for output filename (without extension)

    Returns:
        Path to the generated SRT file, or None if generation failed

    Raises:
        ValueError: If input parameters are invalid
    """
    from pathlib import Path
    from .audio_extractor import extract_audio_from_video
    from .whisper_service import whisper_service

    # Validate input parameters
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        logger.error(f"Video file does not exist: {video_path}")
        return None

    output_dir_obj = Path(output_dir)
    output_dir_obj.mkdir(parents=True, exist_ok=True)

    if not filename_prefix:
        logger.error("Filename prefix cannot be empty")
        return None

    audio_filename = f"{filename_prefix}_audio.wav"
    audio_path = None

    try:
        # Step 1: Extract audio from video
        logger.info(f"Starting subtitle generation for: {video_path}")
        audio_path = extract_audio_from_video(video_path, audio_filename)

        if not audio_path or not Path(audio_path).exists():
            logger.warning("Failed to extract audio for subtitle generation")
            return None

        # Step 2: Get video metadata
        video_size = video_path_obj.stat().st_size
        logger.debug(f"Video size: {video_size / (1024 * 1024):.2f} MB")

        # Step 3: Run transcription
        # REQUIREMENT: All transcripts must be in English for proper subtitle generation
        logger.info("Running Whisper transcription (translating to English)...")
        segments, detected_language = whisper_service.transcribe_video(
            str(audio_path),
            translate_to_english=True,
            target_language="en"  # Ensure English output
        )

        # Step 4: Validate transcription result
        if not segments:
            logger.warning("No segments returned from transcription when generating subtitles")
            return None

        logger.info(f"Transcription successful: {len(segments)} segments generated, language: {detected_language}")

        # Step 5: Write SRT file
        srt_path = output_dir_obj / f"{filename_prefix}.srt"
        if not write_srt(segments, str(srt_path)):
            logger.error("Failed to write SRT file")
            return None

        # Step 6: Generate VTT file as companion
        vtt_path = output_dir_obj / f"{filename_prefix}.vtt"
        if not write_vtt(str(srt_path), str(vtt_path)):
            logger.warning("Failed to write VTT file, but SRT was generated successfully")

        logger.info(f"Successfully generated subtitles at: {srt_path}")
        return str(srt_path)

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error during audio extraction: {e}")
        return None
    except PermissionError as e:
        logger.error(f"Permission denied accessing file: {e}")
        return None
    except OSError as e:
        logger.error(f"OS error during subtitle generation: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating subtitles for video: {e}", exc_info=True)
        return None
    finally:
        # Cleanup: Remove temporary audio file
        if audio_path and Path(audio_path).exists():
            try:
                Path(audio_path).unlink()
                logger.debug(f"Cleaned up temporary audio file: {audio_path}")
            except OSError as e:
                logger.warning(f"Failed to cleanup temporary audio file: {e}")


def has_embedded_subtitles(video_path: str) -> bool:
    """
    Check if a video file has embedded subtitles.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        True if the video has embedded subtitles
    """
    tracks = get_subtitle_tracks(video_path)
    return len(tracks) > 0


def get_best_subtitle_track(video_path: str, preferred_language: str = "en") -> Optional[SubtitleInfo]:
    """
    Get the best subtitle track from a video.
    
    Priority:
    1. Default track with preferred language
    2. Any track with preferred language
    3. Default track
    4. First available track
    
    Args:
        video_path: Path to the video file
        preferred_language: Preferred language code
        
    Returns:
        Best SubtitleInfo or None
    """
    tracks = get_subtitle_tracks(video_path)
    
    if not tracks:
        return None
    
    # Priority 1: Default track with preferred language
    for track in tracks:
        if track.is_default and track.language.lower().startswith(preferred_language.lower()):
            return track
    
    # Priority 2: Any track with preferred language
    for track in tracks:
        if track.language.lower().startswith(preferred_language.lower()):
            return track
    
    # Priority 3: Default track
    for track in tracks:
        if track.is_default:
            return track
    
    # Priority 4: First track
    return tracks[0]
