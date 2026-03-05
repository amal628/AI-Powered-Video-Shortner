# backend/app/services/highlight_selector.py

import re
import logging
import warnings

warnings.filterwarnings("ignore")
import math
from collections import Counter
from typing import List, Tuple, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Content Type Detection - AI-based video content classification
# ------------------------------------------------------------

class ContentType(Enum):
    """Detected video content types."""
    TUTORIAL = "tutorial"
    VLOG = "vlog"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    REVIEW = "review"
    EDUCATIONAL = "educational"
    ENTERTAINMENT = "entertainment"
    NEWS = "news"
    MOTIVATIONAL = "motivational"
    PRODUCT_DEMO = "product_demo"
    STORYTELLING = "storytelling"
    UNKNOWN = "unknown"


@dataclass
class ContentAnalysis:
    """Result of content type analysis."""
    content_type: ContentType
    confidence: float
    detected_keywords: List[str]
    recommended_highlight_strategy: str


# Content type detection patterns
CONTENT_PATTERNS = {
    ContentType.TUTORIAL: {
        "keywords": [
            "step by step", "tutorial", "how to", "let me show you",
            "follow these steps", "first step", "next step", "finally",
            "in this tutorial", "i'm going to show", "here's how",
            "learn how", "guide", "walkthrough", "demonstration"
        ],
        "strategy": "distribute_evenly",  # Tutorials need even distribution
        "weight": 1.0
    },
    ContentType.VLOG: {
        "keywords": [
            "vlog", "day in my life", "follow me", "my routine",
            "morning routine", "night routine", "a day in",
            "life update", "what i did today", "my day"
        ],
        "strategy": "peak_moments",  # Vlogs have peak moments
        "weight": 1.0
    },
    ContentType.INTERVIEW: {
        "keywords": [
            "interview", "guest", "welcome", "thank you for joining",
            "let's welcome", "my guest today", "question for you",
            "can you tell us", "what do you think about"
        ],
        "strategy": "key_questions",  # Focus on Q&A highlights
        "weight": 1.0
    },
    ContentType.PODCAST: {
        "keywords": [
            "podcast", "episode", "today we're discussing",
            "let's talk about", "our topic today", "welcome back to",
            "thanks for listening", "on today's episode"
        ],
        "strategy": "topic_changes",  # Focus on topic transitions
        "weight": 1.0
    },
    ContentType.REVIEW: {
        "keywords": [
            "review", "my thoughts on", "pros and cons", "honest review",
            "is it worth", "should you buy", "let me review",
            "unboxing", "first impressions", "verdict"
        ],
        "strategy": "key_points",  # Focus on key points and verdict
        "weight": 1.0
    },
    ContentType.EDUCATIONAL: {
        "keywords": [
            "learn", "understand", "concept", "explain", "theory",
            "in this lesson", "let's learn", "the key concept",
            "important to understand", "definition", "principle"
        ],
        "strategy": "key_concepts",  # Focus on key concepts
        "weight": 1.0
    },
    ContentType.ENTERTAINMENT: {
        "keywords": [
            "funny", "hilarious", "comedy", "joke", "laugh",
            "entertainment", "prank", "challenge", "reaction"
        ],
        "strategy": "peak_moments",  # Focus on peak entertainment
        "weight": 1.0
    },
    ContentType.MOTIVATIONAL: {
        "keywords": [
            "motivation", "inspire", "believe in yourself", "success",
            "never give up", "you can do", "dream", "goal",
            "mindset", "achieve", "overcome", "push through"
        ],
        "strategy": "emotional_peaks",  # Focus on emotional peaks
        "weight": 1.0
    },
    ContentType.PRODUCT_DEMO: {
        "keywords": [
            "demo", "demonstration", "product", "feature", "show you",
            "let me demonstrate", "here's how it works", "functionality"
        ],
        "strategy": "key_features",  # Focus on key features
        "weight": 1.0
    },
    ContentType.STORYTELLING: {
        "keywords": [
            "story", "once upon", "let me tell you", "so basically",
            "this happened", "you won't believe", "story time",
            "long story short", "here's what happened"
        ],
        "strategy": "narrative_peaks",  # Focus on narrative peaks
        "weight": 1.0
    },
    ContentType.NEWS: {
        "keywords": [
            "breaking", "news", "report", "update", "latest",
            "just in", "developing story", "according to"
        ],
        "strategy": "key_headlines",  # Focus on key headlines
        "weight": 1.0
    }
}


def detect_content_type(segments: List[Dict], full_transcript: str) -> ContentAnalysis:
    """
    AI-based content type detection from transcript.
    
    Analyzes the transcript to determine the type of video content
    and recommends the best highlight selection strategy.
    
    Args:
        segments: List of transcription segments
        full_transcript: Full transcript text
        
    Returns:
        ContentAnalysis with detected type and strategy
    """
    text_lower = full_transcript.lower()
    
    # Score each content type
    scores = {}
    matched_keywords = {}
    
    for content_type, pattern in CONTENT_PATTERNS.items():
        score = 0
        found_keywords = []
        
        for keyword in pattern["keywords"]:
            # Count occurrences
            count = text_lower.count(keyword)
            if count > 0:
                score += count * pattern["weight"]
                found_keywords.append(keyword)
        
        scores[content_type] = score
        matched_keywords[content_type] = found_keywords
    
    # Find the best match
    best_type = ContentType.UNKNOWN
    best_score = 0
    
    for content_type, score in scores.items():
        if score > best_score:
            best_score = score
            best_type = content_type
    
    # Calculate confidence
    total_score = sum(scores.values())
    confidence = best_score / total_score if total_score > 0 else 0.0
    
    # Get recommended strategy
    strategy = CONTENT_PATTERNS.get(best_type, {}).get("strategy", "general")
    
    logger.info(f"Detected content type: {best_type.value} (confidence: {confidence:.2f})")
    logger.info(f"Matched keywords: {matched_keywords.get(best_type, [])}")
    
    return ContentAnalysis(
        content_type=best_type,
        confidence=confidence,
        detected_keywords=matched_keywords.get(best_type, []),
        recommended_highlight_strategy=strategy
    )


# ------------------------------------------------------------
# Importance Keywords for Highlight Detection
# ------------------------------------------------------------

# Importance indicators - words that signal key content
IMPORTANCE_KEYWORDS = {
    # High importance markers
    "critical": 5, "important": 5, "key": 5, "main": 4, "essential": 5,
    "crucial": 5, "vital": 5, "significant": 4, "major": 4,
    
    # Action/transition words
    "remember": 4, "note": 3, "highlight": 4, "focus": 3,
    "conclusion": 5, "finally": 4, "summary": 5, "overview": 4,
    
    # Emotional emphasis
    "amazing": 3, "incredible": 3, "awesome": 3, "excellent": 3,
    "best": 4, "worst": 4, "top": 3, "powerful": 3,
    
    # Engagement hooks
    "must": 4, "need": 3, "should": 2, "have to": 3,
    "don't miss": 5, "watch this": 5, "look at": 3,
    
    # Introduction/conclusion markers
    "welcome": 3, "hello": 2, "thank": 3, "today": 2,
    "first": 3, "last": 3, "start": 3, "begin": 3, "end": 3,
    
    # Explanatory markers
    "show": 3, "explain": 4, "demonstrate": 4, "example": 3,
    "step": 3, "how to": 4, "learn": 3, "understand": 3,
    
    # Question markers (often introduce important topics)
    "why": 3, "how": 3, "what": 3, "when": 2, "where": 2,
    
    # Certainty markers
    "always": 2, "never": 2, "definitely": 3, "absolutely": 3,
    "certainly": 3, "surely": 2, "actually": 2
}

# Filler words to penalize
FILLER_WORDS = {
    "um", "uh", "like", "you know", "sort of", "kind of",
    "basically", "actually", "literally", "just", "so", "right"
}

# Topic transition phrases
TRANSITION_PHRASES = [
    "now let's", "moving on", "next up", "another thing",
    "on the other hand", "in addition", "furthermore",
    "most importantly", "above all", "in conclusion"
]


def analyze_text_sentiment(text: str) -> float:
    """
    Analyze text for emotional intensity and engagement potential.
    Returns a score from 0 to 1.
    """
    text_lower = text.lower()
    score = 0.0
    
    # Exclamation marks indicate emphasis
    exclamation_count = text.count('!')
    score += min(exclamation_count * 0.1, 0.3)
    
    # Questions engage viewers
    question_count = text.count('?')
    score += min(question_count * 0.1, 0.2)
    
    # Capitalized words (emphasis)
    caps_words = len(re.findall(r'\b[A-Z]{2,}\b', text))
    score += min(caps_words * 0.05, 0.2)
    
    # Numbers and statistics
    numbers = len(re.findall(r'\b\d+%?\b', text))
    score += min(numbers * 0.05, 0.15)
    
    return min(score, 1.0)


def calculate_keyword_density(text: str, full_transcript: str) -> float:
    """
    Calculate how unique/important the segment's vocabulary is
    compared to the full transcript.
    """
    # Get word frequencies in full transcript
    all_words = re.findall(r'\b\w+\b', full_transcript.lower())
    word_freq = Counter(all_words)
    total_words = len(all_words)
    
    if total_words == 0:
        return 0.0
    
    # Get segment words
    segment_words = re.findall(r'\b\w+\b', text.lower())
    if not segment_words:
        return 0.0
    
    # Calculate TF-IDF-like score
    # Rare words in the segment get higher scores
    score = 0.0
    for word in segment_words:
        if len(word) > 3:  # Skip short words
            freq = word_freq.get(word, 0)
            if freq > 0:
                # Inverse frequency - rare words score higher
                idf = math.log(total_words / freq)
                score += idf
    
    # Normalize by segment length
    return score / len(segment_words) if segment_words else 0.0


def detect_topic_boundaries(segments: List[Dict]) -> List[int]:
    """
    Detect indices where topic changes occur.
    These are good candidates for highlight boundaries.
    """
    boundary_indices = []
    
    for i, segment in enumerate(segments):
        text = segment.get("text", "").lower()
        
        # Check for transition phrases
        for phrase in TRANSITION_PHRASES:
            if phrase in text:
                boundary_indices.append(i)
                break
    
    return boundary_indices


def score_segment_comprehensive(
    segment: Dict,
    full_transcript: str,
    position_ratio: float,
    is_topic_boundary: bool
) -> Tuple[float, Dict]:
    """
    Comprehensive segment scoring considering multiple factors.
    
    Returns:
        Tuple of (score, score_breakdown)
    """
    text = segment.get("text", "")
    text_lower = text.lower()
    score_breakdown = {}
    
    # 1. Keyword importance score (0-10)
    keyword_score = 0
    matched_keywords = []
    for keyword, weight in IMPORTANCE_KEYWORDS.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            keyword_score += weight
            matched_keywords.append(keyword)
    
    keyword_score = min(keyword_score, 10)
    score_breakdown['keyword'] = keyword_score
    score_breakdown['matched_keywords'] = matched_keywords
    
    # 2. Sentiment/engagement score (0-5)
    sentiment_score = analyze_text_sentiment(text) * 5
    score_breakdown['sentiment'] = sentiment_score
    
    # 3. Unique content score (TF-IDF-like) (0-5)
    density_score = min(calculate_keyword_density(text, full_transcript) * 2, 5)
    score_breakdown['density'] = density_score
    
    # 4. Position score - REDUCED BIAS to analyze entire video
    # We want to find highlights throughout the ENTIRE video, not just beginning/end
    # Position score is now minimal to let content quality dominate
    position_score = 1  # Base score for all positions
    if position_ratio < 0.1:  # First 10% - potential hook
        position_score = 2  # Slight bonus for hooks
    elif position_ratio > 0.9:  # Last 10% - potential conclusion
        position_score = 1.5  # Slight bonus for conclusions
    score_breakdown['position'] = position_score
    
    # 5. Topic boundary bonus (0-2)
    boundary_score = 2 if is_topic_boundary else 0
    score_breakdown['boundary'] = boundary_score
    
    # 6. Length appropriateness (0-2)
    # Prefer segments that are not too short or too long
    duration = segment.get("end", 0) - segment.get("start", 0)
    if 3 <= duration <= 15:  # Ideal segment length
        length_score = 2
    elif 2 <= duration <= 20:
        length_score = 1.5
    else:
        length_score = 1
    score_breakdown['length'] = length_score
    
    # 7. Filler penalty (0 to -3)
    filler_count = sum(1 for filler in FILLER_WORDS if filler in text_lower)
    filler_penalty = min(filler_count * 0.5, 3)
    score_breakdown['filler_penalty'] = -filler_penalty
    
    # 8. Speech clarity (segments with actual words)
    word_count = len(text.split())
    clarity_score = min(word_count / 5, 2) if word_count >= 3 else 0
    score_breakdown['clarity'] = clarity_score
    
    # Calculate total score
    total_score = (
        keyword_score +
        sentiment_score +
        density_score +
        position_score +
        boundary_score +
        length_score -
        filler_penalty +
        clarity_score
    )
    
    score_breakdown['total'] = total_score
    
    return total_score, score_breakdown


def merge_adjacent_segments(
    segments: List[Tuple[float, float]],
    gap_threshold: float = 2.0
) -> List[Tuple[float, float]]:
    """
    Merge segments that are close together to avoid jarring cuts.
    """
    if not segments:
        return []
    
    # Sort by start time
    sorted_segments = sorted(segments, key=lambda x: x[0])
    merged = [sorted_segments[0]]
    
    for current in sorted_segments[1:]:
        last = merged[-1]
        gap = current[0] - last[1]
        
        if gap <= gap_threshold:
            # Merge: extend the last segment
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    
    return merged


def is_meaningful_speech(segments: List[Dict]) -> bool:
    """
    Check if the segments contain meaningful speech content.
    Returns False if the video only has music, silence, or very little speech.
    """
    if not segments:
        return False
    
    # Count total words across all segments
    total_words = 0
    meaningful_segments = 0
    
    # Common non-speech labels that Whisper might transcribe
    non_speech_labels = {"music", "[music]", "♪", "♫", "music.", "music..", 
                         "silence", "[silence]", "applause", "[applause]",
                         "laughing", "[laughing]", "♪♪", "🎵", "🎶"}
    
    for seg in segments:
        text = seg.get("text", "").strip().lower()
        
        # Skip non-speech labels
        if text in non_speech_labels:
            continue
        
        # Count words (excluding very short segments)
        words = text.split()
        if len(words) >= 3:  # At least 3 words to be meaningful
            meaningful_segments += 1
            total_words += len(words)
    
    # Need at least some meaningful speech
    # Either multiple meaningful segments or enough total words
    return meaningful_segments >= 3 or total_words >= 20


def select_top_segments(
    segments: List[Dict],
    total_duration: float,
    target_ratio: float = 0.20,
    min_duration: float = 10.0,
    max_duration: float = 60.0,
    platform: Optional[str] = None
) -> List[Tuple[float, float]]:
    """
    AI-powered segment selection that automatically:
    1. Detects video content type (tutorial, vlog, interview, etc.)
    2. Adapts highlight strategy based on content type
    3. Considers platform-specific requirements
    4. Analyzes the ENTIRE video for best highlights
    
    This function provides intelligent, adaptive highlight selection
    based on what type of content the video contains.
    
    Args:
        segments: List of transcription segments with 'start', 'end', 'text'
        total_duration: Total video duration in seconds
        target_ratio: Target ratio of original video (default 20%)
        min_duration: Minimum output duration (default 10s)
        max_duration: Maximum output duration (default 60s)
        platform: Target platform name for format-specific optimization
    
    Returns:
        List of (start, end) tuples for selected segments
    """
    if not segments:
        logger.warning("No segments provided to select_top_segments")
        return []
    
    logger.info(f"🤖 AI analyzing {len(segments)} segments across {total_duration:.1f}s video...")
    
    # Build full transcript for analysis
    full_transcript = " ".join(seg.get("text", "") for seg in segments)
    
    # ============================================
    # STEP 1: AI Content Type Detection
    # ============================================
    content_analysis = detect_content_type(segments, full_transcript)
    logger.info(f"📊 Detected content type: {content_analysis.content_type.value}")
    logger.info(f"📋 Strategy: {content_analysis.recommended_highlight_strategy}")
    
    # ============================================
    # STEP 2: Platform-Specific Optimization
    # ============================================
    try:
        from .social_media_formats import get_format_by_name
        platform_format = get_format_by_name(platform) if platform else None
        
        if platform_format:
            max_duration = min(max_duration, platform_format.max_duration)
            min_duration = max(min_duration, platform_format.min_duration)
            logger.info(f"📱 Platform '{platform}': min={min_duration}s, max={max_duration}s")
    except Exception as e:
        logger.warning(f"Could not load platform format: {e}")
    
    # ============================================
    # STEP 3: Calculate Target Duration
    # ============================================
    # Adjust target based on video length and content type
    target_duration = total_duration * target_ratio
    
    # For longer videos, be more selective
    if total_duration > 600:  # 10+ minutes
        target_duration = min(target_duration, max_duration)
        logger.info(f"🎬 Long video detected, targeting {target_duration:.1f}s of highlights")
    
    target_duration = max(target_duration, min_duration)
    target_duration = min(target_duration, max_duration, total_duration)
    
    logger.info(f"🎯 Target duration: {target_duration:.1f}s from {total_duration:.1f}s video")
    
    # Check if there's meaningful speech content
    if not is_meaningful_speech(segments):
        logger.info("No meaningful speech detected. Using time-based selection.")
        return [(0.0, min(target_duration, total_duration))]
    
    # ============================================
    # STEP 4: Score Segments with Content-Aware Strategy
    # ============================================
    boundary_indices = set(detect_topic_boundaries(segments))
    
    # Apply content-type specific scoring adjustments
    content_type = content_analysis.content_type
    strategy = content_analysis.recommended_highlight_strategy
    
    scored_segments = []
    for i, segment in enumerate(segments):
        position_ratio = i / len(segments) if segments else 0
        is_boundary = i in boundary_indices
        
        score, breakdown = score_segment_comprehensive(
            segment, full_transcript, position_ratio, is_boundary
        )
        
        # Apply content-type specific bonuses
        text_lower = segment.get("text", "").lower()
        
        if content_type == ContentType.TUTORIAL:
            # Tutorials: Bonus for step markers and explanations
            if any(kw in text_lower for kw in ["step", "first", "next", "finally", "now"]):
                score += 3
        
        elif content_type == ContentType.INTERVIEW:
            # Interviews: Bonus for questions and answers
            if "?" in segment.get("text", ""):
                score += 2
            if any(kw in text_lower for kw in ["think", "believe", "opinion", "important"]):
                score += 2
        
        elif content_type == ContentType.REVIEW:
            # Reviews: Bonus for verdicts and key points
            if any(kw in text_lower for kw in ["verdict", "rating", "score", "recommend", "worth"]):
                score += 4
            if any(kw in text_lower for kw in ["pros", "cons", "good", "bad", "best", "worst"]):
                score += 2
        
        elif content_type == ContentType.MOTIVATIONAL:
            # Motivational: Bonus for emotional peaks
            if any(kw in text_lower for kw in ["believe", "dream", "success", "never give up", "achieve"]):
                score += 3
        
        elif content_type == ContentType.STORYTELLING:
            # Stories: Bonus for narrative moments
            if any(kw in text_lower for kw in ["then", "suddenly", "realized", "happened", "moment"]):
                score += 3
        
        scored_segments.append({
            "index": i,
            "score": score,
            "start": segment.get("start", 0),
            "end": segment.get("end", 0),
            "duration": segment.get("end", 0) - segment.get("start", 0),
            "text": segment.get("text", ""),
            "breakdown": breakdown
        })
    
    # Sort by score (descending)
    scored_segments.sort(key=lambda x: x['score'], reverse=True)
    
    # Log top segments
    logger.info("🏆 Top 5 scored segments:")
    for i, seg in enumerate(scored_segments[:5]):
        logger.info(f"  {i+1}. Score: {seg['score']:.1f}, "
                   f"Time: {seg['start']:.1f}s-{seg['end']:.1f}s")
    
    # ============================================
    # STEP 5: Distributed Selection Across Entire Video
    # ============================================
    # Divide video into sections for DISTRIBUTED selection
    num_sections = max(3, int(target_duration / 10))
    
    logger.info(f"📐 Dividing video into {num_sections} sections for distributed highlights")
    
    # Group segments by section
    sections = [[] for _ in range(num_sections)]
    for seg in scored_segments:
        position_ratio = seg['index'] / len(segments) if segments else 0
        section_idx = min(int(position_ratio * num_sections), num_sections - 1)
        sections[section_idx].append(seg)
    
    # Sort each section by score
    for section in sections:
        section.sort(key=lambda x: x['score'], reverse=True)
    
    # ============================================
    # STEP 6: Select Segments with Strategy
    # ============================================
    selected_segments = []
    current_duration = 0.0
    used_indices = set()
    
    # Pick the best segment from each section
    for section_idx, section in enumerate(sections):
        if current_duration >= target_duration:
            break
        
        for seg in section:
            if seg['index'] in used_indices:
                continue
            
            if seg['duration'] <= 0:
                continue
            
            # Check overlap
            overlaps = False
            for start, end in selected_segments:
                if not (seg['end'] <= start or seg['start'] >= end):
                    overlaps = True
                    break
            
            if not overlaps:
                selected_segments.append((seg['start'], seg['end']))
                used_indices.add(seg['index'])
                current_duration += seg['duration']
                break
    
    # Fill remaining duration if needed
    if current_duration < target_duration * 0.7:
        logger.info("🔄 Filling remaining duration with additional highlights")
        
        for seg in scored_segments:
            if current_duration >= target_duration:
                break
            
            if seg['index'] in used_indices or seg['duration'] <= 0:
                continue
            
            overlaps = False
            for start, end in selected_segments:
                if not (seg['end'] <= start or seg['start'] >= end):
                    overlaps = True
                    break
            
            if not overlaps:
                selected_segments.append((seg['start'], seg['end']))
                used_indices.add(seg['index'])
                current_duration += seg['duration']
    
    # Fallback if no segments selected
    if not selected_segments:
        logger.info("⚠️ No segments selected, using distributed time-based selection")
        for i in range(num_sections):
            if current_duration >= target_duration:
                break
            time_point = (i / num_sections) * total_duration
            segment_duration = min(5.0, target_duration - current_duration)
            selected_segments.append((time_point, time_point + segment_duration))
            current_duration += segment_duration
    
    # Merge adjacent segments
    selected_segments = merge_adjacent_segments(selected_segments, gap_threshold=1.5)
    
    # Sort by start time
    selected_segments.sort(key=lambda x: x[0])
    
    # Calculate final duration
    final_duration = sum(end - start for start, end in selected_segments)
    
    logger.info(f"✅ Selected {len(selected_segments)} segments totaling {final_duration:.1f}s")
    logger.info(f"📍 Highlight time ranges: {selected_segments}")
    
    return selected_segments


# ============================================================
# PROFESSIONAL CINEMATIC TRAILER EDITOR
# ============================================================

# Cinematic trailer keywords with emotional intensity weights
CINEMATIC_KEYWORDS = {
    # 🎬 OPENING ATMOSPHERE - Slow, reflective, curiosity-building
    "opening_atmosphere": {
        # Reflective/contemplative phrases
        "once upon": 10, "long ago": 9, "in the beginning": 9, "it all started": 8,
        "i remember": 8, "when i was": 7, "back then": 7, "years ago": 6,
        "have you ever": 9, "did you know": 8, "imagine": 8, "picture this": 9,
        "let me tell you": 7, "there was a time": 8, "in a world": 10,
        "every story": 7, "every journey": 7, "it began": 8, "the story of": 7,
        # Mysterious/curiosity
        "nobody knows": 8, "the mystery": 9, "hidden": 7, "secret": 8,
        "what if": 9, "suppose": 7, "what would happen": 8,
        # Slow/dramatic openings
        "quietly": 6, "slowly": 6, "gently": 6, "softly": 6,
        "in silence": 8, "in the shadows": 9, "darkness": 7,
    },
    
    # 🎣 STRONG HOOK - Attention-grabbing, shocking, dramatic
    "strong_hook": {
        # Shocking statements
        "you won't believe": 10, "this is impossible": 10, "unbelievable": 9,
        "shocking": 10, "insane": 9, "crazy": 8, "impossible": 9,
        "never seen before": 10, "first time ever": 9, "history in the making": 10,
        # Attention grabbers
        "stop": 8, "wait": 8, "listen": 7, "watch this": 10, "look at this": 9,
        "you need to see": 10, "you have to see": 10, "don't miss": 8,
        # Dramatic revelations
        "the truth is": 10, "here's the truth": 10, "truth about": 9,
        "they don't want you to know": 10, "what they won't tell you": 10,
        "breaking": 9, "just in": 8, "urgent": 9, "alert": 8,
        # Game changers
        "game changer": 10, "changed everything": 10, "everything changed": 10,
        "revolutionary": 9, "groundbreaking": 9,
    },
    
    # 📖 STORY TEASE - Conflict introduction, tension, struggle
    "story_tease": {
        # Conflict introduction
        "the problem": 8, "the challenge": 8, "the struggle": 9,
        "we had to": 7, "i had to": 7, "they had to": 7,
        "against all odds": 10, "against the odds": 10,
        # Tension building
        "but then": 8, "however": 6, "suddenly": 8, "unexpectedly": 8,
        "nobody expected": 9, "no one saw": 9, "caught off guard": 8,
        # Struggle/hardship
        "fighting for": 9, "struggling": 8, "battling": 9, "facing": 7,
        "the enemy": 9, "the threat": 8, "the danger": 8,
        "at stake": 9, "on the line": 8, "risk": 7,
        # Quest/journey
        "the mission": 8, "the quest": 9, "the journey": 7,
        "we must": 8, "we have to": 7, "there's no choice": 9,
        # Mystery/intrigue
        "the mystery deepens": 10, "more questions": 8, "unanswered": 7,
        "what really happened": 9, "the real story": 8,
    },
    
    # 🔥 ESCALATION - Rising tension, action, emotional build
    "escalation": {
        # Rising action
        "getting worse": 8, "escalating": 9, "intensifying": 9,
        "spiral": 8, "unraveling": 8, "falling apart": 8,
        # Action/tension
        "chase": 9, "race against time": 10, "running out of time": 10,
        "no time": 8, "time is running": 9, "hurry": 7,
        "fight": 9, "battle": 10, "war": 9, "combat": 8,
        "attack": 8, "ambush": 9, "assault": 8,
        # Emotional escalation
        "tension rises": 10, "pressure mounting": 9, "stakes get higher": 10,
        "more dangerous": 8, "more intense": 8,
        # Desperation
        "desperate": 9, "last chance": 10, "final attempt": 9,
        "do or die": 10, "now or never": 10, "one shot": 9,
        # Confrontation
        "confront": 8, "face": 7, "stand up": 7, "challenge": 8,
        "showdown": 10, "face off": 9, "standoff": 9,
    },
    
    # 💥 CLIMAX - Most powerful, highest emotional intensity
    "climax": {
        # Peak emotional moments
        "this is it": 10, "the moment": 10, "right now": 8,
        "everything leads to": 10, "all for this": 10,
        # Dramatic peaks
        "climax": 10, "peak": 8, "pinnacle": 9, "summit": 8,
        "the ultimate": 10, "the final": 9, "at last": 8,
        # Emotional breakthrough
        "i realized": 9, "i finally understood": 10, "it all made sense": 9,
        "the answer": 8, "the solution": 7, "breakthrough": 9,
        # Powerful statements
        "i will": 9, "i must": 9, "i have to": 8,
        "this ends now": 10, "no more": 8, "enough": 8,
        # Life-changing moments
        "changed my life": 10, "life-changing": 10, "transformed": 9,
        "never be the same": 10, "everything different": 9,
        # High drama
        "revelation": 10, "the truth revealed": 10, "exposed": 9,
        "the secret": 9, "finally revealed": 10,
    },
    
    # 🎭 TEASER ENDING - Mysterious, powerful, leaves curiosity
    "teaser_ending": {
        # Mysterious endings
        "but that's not all": 10, "there's more": 9, "wait for it": 10,
        "coming soon": 8, "to be continued": 9, "not over yet": 9,
        # Powerful closing
        "this is just the beginning": 10, "it starts now": 9,
        "the real journey begins": 10, "chapter one": 8,
        # Intrigue
        "what happens next": 9, "you'll have to see": 9,
        "find out": 8, "discover": 7, "uncover": 8,
        # Dramatic pause endings
        "or is it": 10, "or so i thought": 10, "but i was wrong": 10,
        "little did i know": 10, "little did we know": 10,
        # Question endings
        "what would you do": 9, "the question is": 8,
        "only time will tell": 9, "we shall see": 8,
    },
    
    # 🚫 SPOILER INDICATORS - Avoid these (negative weight)
    "spoiler": {
        "in conclusion": -10, "to summarize": -10, "in the end": -8,
        "finally happened": -7, "the outcome": -8, "result was": -7,
        "ended up": -6, "turned out that": -7, "resolution": -8,
        "solved": -6, "resolved": -7, "concluded": -8,
        "the ending": -9, "how it ended": -10, "final result": -8,
        "happily ever after": -9, "the moral": -7,
    },
}

# Emotional intensity multipliers for position-based scoring
EMOTIONAL_CURVE = {
    "opening": 0.7,      # Build slowly
    "hook": 1.0,         # Strong impact
    "story_tease": 0.8,  # Moderate tension
    "escalation": 1.2,   # Rising intensity
    "climax": 1.5,       # Peak intensity
    "teaser": 1.1,       # Leave them wanting more
}


def score_segment_cinematic(text: str, position_ratio: float) -> Dict[str, Any]:
    """
    Score a segment for cinematic trailer selection.
    
    Returns dict with scores for each trailer phase and emotional intensity.
    """
    text_lower = text.lower()
    scores = {
        "opening_atmosphere": 0.0,
        "strong_hook": 0.0,
        "story_tease": 0.0,
        "escalation": 0.0,
        "climax": 0.0,
        "teaser_ending": 0.0,
        "spoiler_penalty": 0.0,
        "emotional_intensity": 0.0,
        "total": 0.0
    }
    
    # Score for each cinematic phase
    for phase, keywords in CINEMATIC_KEYWORDS.items():
        phase_score = 0.0
        for keyword, weight in keywords.items():
            if keyword in text_lower:
                phase_score += weight
        
        if phase == "spoiler":
            scores["spoiler_penalty"] = abs(phase_score)
        else:
            scores[phase] = min(phase_score, 20)  # Cap at 20
    
    # Calculate emotional intensity (0-10 scale)
    emotional_words = [
        "love", "hate", "fear", "death", "life", "hope", "despair",
        "triumph", "defeat", "victory", "loss", "passion", "rage",
        "terror", "joy", "sorrow", "heartbreak", "destiny", "fate",
        "sacrifice", "betrayal", "redemption", "salvation", "doom"
    ]
    emotional_count = sum(1 for word in emotional_words if word in text_lower)
    scores["emotional_intensity"] = min(emotional_count * 2, 10)
    
    # Calculate total score with position-based emotional curve
    # Opening segments (0-15% of video) score higher for opening_atmosphere
    # Hook segments (0-25%) score higher for strong_hook
    # Middle segments (25-75%) score higher for story_tease and escalation
    # Late segments (75-95%) score higher for climax
    # End segments (95-100%) score higher for teaser_ending
    
    position_multiplier = 1.0
    if position_ratio < 0.15:
        position_multiplier = EMOTIONAL_CURVE["opening"]
        scores["total"] = scores["opening_atmosphere"] * 1.5 + scores["strong_hook"] * 0.5
    elif position_ratio < 0.30:
        position_multiplier = EMOTIONAL_CURVE["hook"]
        scores["total"] = scores["strong_hook"] * 1.5 + scores["story_tease"] * 0.5
    elif position_ratio < 0.60:
        position_multiplier = EMOTIONAL_CURVE["story_tease"]
        scores["total"] = scores["story_tease"] * 1.2 + scores["escalation"] * 0.8
    elif position_ratio < 0.80:
        position_multiplier = EMOTIONAL_CURVE["escalation"]
        scores["total"] = scores["escalation"] * 1.5 + scores["climax"] * 0.5
    elif position_ratio < 0.95:
        position_multiplier = EMOTIONAL_CURVE["climax"]
        scores["total"] = scores["climax"] * 2.0
    else:
        position_multiplier = EMOTIONAL_CURVE["teaser"]
        scores["total"] = scores["teaser_ending"] * 1.5 + scores["climax"] * 0.5
    
    # Apply emotional intensity bonus
    scores["total"] += scores["emotional_intensity"] * position_multiplier
    
    # Apply spoiler penalty
    scores["total"] -= scores["spoiler_penalty"] * 2  # Heavy penalty for spoilers
    
    # Ensure minimum score
    scores["total"] = max(scores["total"], 0)
    
    return scores


def select_trailer_segments(
    segments: List[Dict],
    total_duration: float,
    target_duration: float,
    platform: Optional[str] = None
) -> List[Tuple[float, float]]:
    """
    PROFESSIONAL CINEMATIC TRAILER EDITOR
    
    Creates a dramatic, emotional, cinematic trailer following professional
    movie trailer structure. Total duration will be exactly as specified.
    
    TRAILER STRUCTURE:
    1. OPENING ATMOSPHERE (5-10s) - Slow, reflective, curiosity-building
    2. STRONG HOOK (5-12s) - Attention-grabbing, shocking, dramatic
    3. STORY TEASE (20-30s) - Conflict introduction, tension, 2-3 segments
    4. ESCALATION (15-20s) - Rising tension, action, emotional build
    5. CLIMAX MOMENT (8-15s) - Most powerful dialogue, highest intensity
    6. TEASER ENDING (3-6s) - Mysterious, powerful, leaves curiosity
    
    Total: 60-90 seconds (matches user-specified duration)
    
    Args:
        segments: List of transcription segments with 'start', 'end', 'text'
        total_duration: Total video duration in seconds
        target_duration: Target output duration in seconds (user-specified)
        platform: Target platform name (unused, kept for compatibility)
    
    Returns:
        List of (start, end) tuples for selected segments in chronological order
    """
    # ============================================
    # HANDLE NO SPEECH DETECTED - TIME-BASED FALLBACK
    # ============================================
    if not segments:
        logger.warning("No segments provided for trailer selection - using time-based fallback")
        return _create_time_based_trailer(total_duration, target_duration)
    
    logger.info("=" * 60)
    logger.info("🎬 PROFESSIONAL CINEMATIC TRAILER EDITOR")
    logger.info("=" * 60)
    logger.info(f"📹 Source video: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    logger.info(f"🎯 Target duration: {target_duration:.1f}s (USER-SPECIFIED)")
    logger.info(f"📊 Analyzing {len(segments)} transcript segments...")
    
    # ============================================
    # STEP 1: Calculate Time Budgets for Each Phase
    # ============================================
    # Proportional allocation based on target duration
    # Minimum 60s, maximum 90s for cinematic feel
    
    # Calculate phase budgets (proportional to target)
    phase_budgets = {
        "opening_atmosphere": max(5, min(10, target_duration * 0.10)),   # 10%
        "strong_hook": max(5, min(12, target_duration * 0.12)),          # 12%
        "story_tease": max(20, min(30, target_duration * 0.30)),         # 30%
        "escalation": max(15, min(20, target_duration * 0.20)),          # 20%
        "climax": max(8, min(15, target_duration * 0.18)),               # 18%
        "teaser_ending": max(3, min(6, target_duration * 0.10)),         # 10%
    }
    
    # Adjust budgets to exactly match target duration
    total_budget = sum(phase_budgets.values())
    if total_budget != target_duration:
        # Scale all budgets proportionally
        scale = target_duration / total_budget
        for phase in phase_budgets:
            phase_budgets[phase] *= scale
    
    logger.info(f"📊 Phase budgets:")
    logger.info(f"   🌅 Opening Atmosphere: {phase_budgets['opening_atmosphere']:.1f}s")
    logger.info(f"   🎣 Strong Hook: {phase_budgets['strong_hook']:.1f}s")
    logger.info(f"   📖 Story Tease: {phase_budgets['story_tease']:.1f}s")
    logger.info(f"   🔥 Escalation: {phase_budgets['escalation']:.1f}s")
    logger.info(f"   💥 Climax: {phase_budgets['climax']:.1f}s")
    logger.info(f"   🎭 Teaser Ending: {phase_budgets['teaser_ending']:.1f}s")
    logger.info(f"   📏 TOTAL: {sum(phase_budgets.values()):.1f}s")
    
    # ============================================
    # STEP 2: Score All Segments
    # ============================================
    scored_segments = []
    for i, segment in enumerate(segments):
        start = segment.get("start", 0)
        end = segment.get("end", 0)
        text = segment.get("text", "")
        duration = end - start
        
        if duration <= 0 or not text.strip():
            continue
        
        position_ratio = start / total_duration if total_duration > 0 else 0
        
        # Get cinematic scores
        cinematic_scores = score_segment_cinematic(text, position_ratio)
        
        # Determine optimal phase for this segment based on position and scores
        best_phase = "story_tease"  # default
        best_phase_score = 0
        
        for phase in ["opening_atmosphere", "strong_hook", "story_tease", "escalation", "climax", "teaser_ending"]:
            phase_score = cinematic_scores[phase]
            # Position-based bonus
            if phase == "opening_atmosphere" and position_ratio < 0.20:
                phase_score *= 1.5
            elif phase == "strong_hook" and position_ratio < 0.30:
                phase_score *= 1.3
            elif phase == "teaser_ending" and position_ratio > 0.85:
                phase_score *= 1.5
            elif phase == "climax" and 0.70 < position_ratio < 0.95:
                phase_score *= 1.4
            
            if phase_score > best_phase_score:
                best_phase_score = phase_score
                best_phase = phase
        
        scored_segments.append({
            "index": i,
            "start": start,
            "end": end,
            "duration": duration,
            "text": text,
            "position_ratio": position_ratio,
            "best_phase": best_phase,
            "opening_score": cinematic_scores["opening_atmosphere"],
            "hook_score": cinematic_scores["strong_hook"],
            "story_score": cinematic_scores["story_tease"],
            "escalation_score": cinematic_scores["escalation"],
            "climax_score": cinematic_scores["climax"],
            "teaser_score": cinematic_scores["teaser_ending"],
            "spoiler_penalty": cinematic_scores["spoiler_penalty"],
            "emotional_intensity": cinematic_scores["emotional_intensity"],
            "total_score": cinematic_scores["total"],
        })
    
    logger.info(f"✅ Scored {len(scored_segments)} segments")
    
    # ============================================
    # STEP 3: Select Segments for Each Phase
    # ============================================
    selected_segments = []
    used_indices = set()
    phase_durations = {phase: 0.0 for phase in phase_budgets}
    
    def select_for_phase(phase: str, score_key: str, budget: float, 
                         position_filter=None, min_score: float = 3.0):
        """Select segments for a specific trailer phase."""
        nonlocal selected_segments, used_indices, phase_durations
        
        # Filter available segments
        available = [s for s in scored_segments if s["index"] not in used_indices]
        
        # Apply position filter if specified
        if position_filter:
            if position_filter == "early":
                available = [s for s in available if s["position_ratio"] < 0.30]
            elif position_filter == "middle":
                available = [s for s in available if 0.20 <= s["position_ratio"] <= 0.80]
            elif position_filter == "late":
                available = [s for s in available if s["position_ratio"] > 0.70]
            elif position_filter == "end":
                available = [s for s in available if s["position_ratio"] > 0.85]
        
        # Sort by phase-specific score (with spoiler penalty)
        available.sort(key=lambda x: x[score_key] - x["spoiler_penalty"], reverse=True)
        
        selected = []
        duration_used = 0.0
        
        for seg in available:
            if duration_used >= budget:
                break
            
            # Check minimum score threshold
            if seg[score_key] < min_score:
                continue
            
            # Don't select segments with high spoiler penalty
            if seg["spoiler_penalty"] > 5:
                continue
            
            selected.append(seg)
            used_indices.add(seg["index"])
            duration_used += seg["duration"]
            phase_durations[phase] += seg["duration"]
            
            logger.info(f"   {phase.upper()}: {seg['start']:.1f}s-{seg['end']:.1f}s "
                       f"(score: {seg[score_key]:.1f}, intensity: {seg['emotional_intensity']:.1f})")
        
        return selected
    
    # PHASE 1: Opening Atmosphere (early in video, reflective)
    logger.info("🌅 Selecting OPENING ATMOSPHERE segments...")
    opening_segments = select_for_phase(
        "opening_atmosphere", "opening_score", 
        phase_budgets["opening_atmosphere"],
        position_filter="early", min_score=2.0
    )
    
    # PHASE 2: Strong Hook (attention-grabbing)
    logger.info("🎣 Selecting STRONG HOOK segments...")
    hook_segments = select_for_phase(
        "strong_hook", "hook_score",
        phase_budgets["strong_hook"],
        position_filter=None, min_score=3.0
    )
    
    # PHASE 3: Story Tease (2-3 segments, conflict introduction)
    logger.info("📖 Selecting STORY TEASE segments...")
    story_segments = select_for_phase(
        "story_tease", "story_score",
        phase_budgets["story_tease"],
        position_filter="middle", min_score=2.0
    )
    
    # PHASE 4: Escalation (rising tension)
    logger.info("🔥 Selecting ESCALATION segments...")
    escalation_segments = select_for_phase(
        "escalation", "escalation_score",
        phase_budgets["escalation"],
        position_filter=None, min_score=2.0
    )
    
    # PHASE 5: Climax (most powerful, late in video)
    logger.info("💥 Selecting CLIMAX segments...")
    climax_segments = select_for_phase(
        "climax", "climax_score",
        phase_budgets["climax"],
        position_filter="late", min_score=3.0
    )
    
    # PHASE 6: Teaser Ending (mysterious, from end)
    logger.info("🎭 Selecting TEASER ENDING segments...")
    teaser_segments = select_for_phase(
        "teaser_ending", "teaser_score",
        phase_budgets["teaser_ending"],
        position_filter="end", min_score=2.0
    )
    
    # ============================================
    # STEP 4: Assemble Trailer in Cinematic Order
    # ============================================
    # Order: Opening → Hook → Story → Escalation → Climax → Teaser
    
    trailer_structure = (
        opening_segments +
        hook_segments +
        story_segments +
        escalation_segments +
        climax_segments +
        teaser_segments
    )
    
    # Convert to (start, end) tuples
    selected_segments = [(seg["start"], seg["end"]) for seg in trailer_structure]
    
    # ============================================
    # STEP 5: Sort Chronologically and Merge
    # ============================================
    selected_segments.sort(key=lambda x: x[0])
    selected_segments = merge_adjacent_segments(selected_segments, gap_threshold=1.5)
    selected_segments.sort(key=lambda x: x[0])
    
    # ============================================
    # STEP 6: Enforce EXACT Target Duration
    # ============================================
    # TOLERANCE: 0.1 seconds for "exact" duration matching
    DURATION_TOLERANCE = 0.1
    
    current_total = sum(end - start for start, end in selected_segments)
    
    logger.info(f"📏 Current duration: {current_total:.1f}s, Target: {target_duration:.1f}s")
    
    # Trim or extend to match exact target
    if current_total > target_duration:
        logger.info(f"✂️ Trimming to exact target duration...")
        trimmed = []
        accumulated = 0.0
        for start, end in selected_segments:
            seg_dur = end - start
            if accumulated + seg_dur <= target_duration:
                trimmed.append((start, end))
                accumulated += seg_dur
            elif accumulated < target_duration:
                remaining = target_duration - accumulated
                if remaining >= DURATION_TOLERANCE:
                    trimmed.append((start, start + remaining))
                accumulated = target_duration
                break
        selected_segments = trimmed
        
    elif current_total < target_duration - DURATION_TOLERANCE:
        logger.info(f"➕ Extending to reach target duration...")
        # Add more high-scoring segments
        remaining = sorted(
            [s for s in scored_segments if s["index"] not in used_indices],
            key=lambda x: x["total_score"],
            reverse=True
        )
        
        for seg in remaining:
            current_total = sum(end - start for start, end in selected_segments)
            if current_total >= target_duration - DURATION_TOLERANCE:
                break
            
            needed = target_duration - current_total
            if seg["duration"] <= needed:
                selected_segments.append((seg["start"], seg["end"]))
                used_indices.add(seg["index"])
            elif needed >= DURATION_TOLERANCE:
                selected_segments.append((seg["start"], seg["start"] + needed))
                break
        
        selected_segments.sort(key=lambda x: x[0])
        selected_segments = merge_adjacent_segments(selected_segments, gap_threshold=1.5)
        selected_segments.sort(key=lambda x: x[0])
    
    # Final adjustment
    final_duration = sum(end - start for start, end in selected_segments)
    
    if final_duration > target_duration:
        # Final trim
        trimmed = []
        accumulated = 0.0
        for start, end in selected_segments:
            seg_dur = end - start
            if accumulated + seg_dur <= target_duration:
                trimmed.append((start, end))
                accumulated += seg_dur
            elif accumulated < target_duration:
                remaining = target_duration - accumulated
                if remaining >= DURATION_TOLERANCE:
                    trimmed.append((start, start + remaining))
                break
        selected_segments = trimmed
    elif final_duration < target_duration - DURATION_TOLERANCE:
        # Extend last segment
        deficit = target_duration - final_duration
        if selected_segments and deficit > 0:
            last_start, last_end = selected_segments[-1]
            new_end = min(last_end + deficit, total_duration)
            selected_segments[-1] = (last_start, new_end)
    
    # ============================================
    # STEP 7: Final Output
    # ============================================
    final_duration = sum(end - start for start, end in selected_segments)
    
    logger.info("=" * 60)
    logger.info("🎬 CINEMATIC TRAILER COMPLETE")
    logger.info("=" * 60)
    logger.info(f"✅ Segments: {len(selected_segments)}")
    logger.info(f"✅ Final Duration: {final_duration:.1f}s (Target: {target_duration:.1f}s)")
    logger.info(f"📊 Phase breakdown:")
    logger.info(f"   🌅 Opening: {phase_durations['opening_atmosphere']:.1f}s")
    logger.info(f"   🎣 Hook: {phase_durations['strong_hook']:.1f}s")
    logger.info(f"   📖 Story: {phase_durations['story_tease']:.1f}s")
    logger.info(f"   🔥 Escalation: {phase_durations['escalation']:.1f}s")
    logger.info(f"   💥 Climax: {phase_durations['climax']:.1f}s")
    logger.info(f"   🎭 Teaser: {phase_durations['teaser_ending']:.1f}s")
    logger.info(f"📍 Segments: {selected_segments}")
    logger.info("=" * 60)
    
    return selected_segments


def _create_time_based_trailer(
    total_duration: float,
    target_duration: float
) -> List[Tuple[float, float]]:
    """
    Create a time-based cinematic trailer for videos with no speech detected.
    
    This function creates a professionally structured trailer by distributing
    segments across the video timeline following cinematic trailer structure:
    1. Opening Atmosphere - from early video (0-15%)
    2. Strong Hook - from early-middle (10-30%)
    3. Story Tease - from middle (25-60%)
    4. Escalation - from middle-late (50-80%)
    5. Climax - from late (70-95%)
    6. Teaser Ending - from end (85-100%)
    
    Args:
        total_duration: Total video duration in seconds
        target_duration: Target output duration in seconds
        
    Returns:
        List of (start, end) tuples for selected segments
    """
    logger.info("=" * 60)
    logger.info("🎬 TIME-BASED CINEMATIC TRAILER (No Speech Detected)")
    logger.info("=" * 60)
    logger.info(f"📹 Source video: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    logger.info(f"🎯 Target duration: {target_duration:.1f}s")
    
    # Calculate phase budgets (proportional to target)
    phase_budgets = {
        "opening_atmosphere": max(5, min(10, target_duration * 0.10)),   # 10%
        "strong_hook": max(5, min(12, target_duration * 0.12)),          # 12%
        "story_tease": max(20, min(30, target_duration * 0.30)),         # 30%
        "escalation": max(15, min(20, target_duration * 0.20)),          # 20%
        "climax": max(8, min(15, target_duration * 0.18)),               # 18%
        "teaser_ending": max(3, min(6, target_duration * 0.10)),         # 10%
    }
    
    # Adjust budgets to exactly match target duration
    total_budget = sum(phase_budgets.values())
    if total_budget != target_duration:
        scale = target_duration / total_budget
        for phase in phase_budgets:
            phase_budgets[phase] *= scale
    
    # Define time ranges for each phase (as ratios of total duration)
    phase_time_ranges = {
        "opening_atmosphere": (0.0, 0.15),    # First 15% of video
        "strong_hook": (0.10, 0.30),          # 10-30% of video
        "story_tease": (0.25, 0.60),          # 25-60% of video
        "escalation": (0.50, 0.80),           # 50-80% of video
        "climax": (0.70, 0.95),               # 70-95% of video
        "teaser_ending": (0.85, 1.0),         # 85-100% of video
    }
    
    selected_segments = []
    phase_durations = {phase: 0.0 for phase in phase_budgets}
    used_time_ranges = []  # Track used time ranges to avoid overlap
    
    def is_overlapping(start: float, end: float) -> bool:
        """Check if time range overlaps with already selected segments."""
        for used_start, used_end in used_time_ranges:
            if not (end <= used_start or start >= used_end):
                return True
        return False
    
    def select_time_segment(phase: str, budget: float) -> Optional[Tuple[float, float]]:
        """Select a time segment for a phase from the appropriate video section."""
        start_ratio, end_ratio = phase_time_ranges[phase]
        
        # Calculate available time range in this phase's section
        section_start = start_ratio * total_duration
        section_end = end_ratio * total_duration
        section_duration = section_end - section_start
        
        if section_duration < 1.0:
            return None
        
        # Calculate segment duration (use budget or available, whichever is smaller)
        segment_duration = min(budget, section_duration * 0.5)  # Max 50% of section
        segment_duration = max(segment_duration, 2.0)  # Minimum 2 seconds
        
        # Find a non-overlapping segment in this section
        # Try multiple start positions within the section
        num_attempts = 10
        for i in range(num_attempts):
            # Calculate start position distributed across section
            progress = i / (num_attempts - 1) if num_attempts > 1 else 0
            potential_start = section_start + progress * (section_duration - segment_duration)
            potential_end = potential_start + segment_duration
            
            # Ensure we don't exceed total duration
            if potential_end > total_duration:
                potential_end = total_duration
                potential_start = max(section_start, potential_end - segment_duration)
            
            if not is_overlapping(potential_start, potential_end):
                return (potential_start, potential_end)
        
        return None
    
    # Select segments for each phase in cinematic order
    phase_order = [
        ("opening_atmosphere", "🌅 Opening Atmosphere"),
        ("strong_hook", "🎣 Strong Hook"),
        ("story_tease", "📖 Story Tease"),
        ("escalation", "🔥 Escalation"),
        ("climax", "💥 Climax"),
        ("teaser_ending", "🎭 Teaser Ending"),
    ]
    
    for phase_key, phase_name in phase_order:
        budget = phase_budgets[phase_key]
        logger.info(f"{phase_name}: Selecting {budget:.1f}s...")
        
        segment = select_time_segment(phase_key, budget)
        if segment:
            start, end = segment
            selected_segments.append((start, end))
            used_time_ranges.append((start, end))
            phase_durations[phase_key] = end - start
            logger.info(f"   ✅ Selected: {start:.1f}s - {end:.1f}s")
        else:
            logger.info(f"   ⚠️ Could not find suitable segment")
    
    # Sort segments chronologically
    selected_segments.sort(key=lambda x: x[0])
    
    # Ensure we have at least some content
    if not selected_segments:
        logger.warning("No segments selected, using fallback distribution")
        # Create evenly distributed segments
        num_segments = max(1, int(target_duration / 10))
        segment_duration = target_duration / num_segments
        for i in range(num_segments):
            start = (i / num_segments) * (total_duration - segment_duration)
            end = start + segment_duration
            selected_segments.append((start, min(end, total_duration)))
    
    # Adjust to match target duration exactly
    current_duration = sum(end - start for start, end in selected_segments)
    
    if current_duration < target_duration:
        # Extend the last segment
        if selected_segments:
            last_start, last_end = selected_segments[-1]
            extension = min(target_duration - current_duration, total_duration - last_end)
            selected_segments[-1] = (last_start, last_end + extension)
    elif current_duration > target_duration:
        # Trim segments from the end
        trimmed = []
        accumulated = 0.0
        for start, end in selected_segments:
            seg_dur = end - start
            if accumulated + seg_dur <= target_duration:
                trimmed.append((start, end))
                accumulated += seg_dur
            elif accumulated < target_duration:
                remaining = target_duration - accumulated
                if remaining >= 1.0:
                    trimmed.append((start, start + remaining))
                break
        selected_segments = trimmed
    
    # Calculate final phase durations for logging
    final_duration = sum(end - start for start, end in selected_segments)
    
    logger.info("=" * 60)
    logger.info("🎬 TIME-BASED TRAILER COMPLETE")
    logger.info("=" * 60)
    logger.info(f"✅ Segments: {len(selected_segments)}")
    logger.info(f"✅ Final Duration: {final_duration:.1f}s (Target: {target_duration:.1f}s)")
    logger.info(f"📊 Phase breakdown:")
    logger.info(f"   🌅 Opening: {phase_durations['opening_atmosphere']:.1f}s")
    logger.info(f"   🎣 Hook: {phase_durations['strong_hook']:.1f}s")
    logger.info(f"   📖 Story: {phase_durations['story_tease']:.1f}s")
    logger.info(f"   🔥 Escalation: {phase_durations['escalation']:.1f}s")
    logger.info(f"   💥 Climax: {phase_durations['climax']:.1f}s")
    logger.info(f"   🎭 Teaser: {phase_durations['teaser_ending']:.1f}s")
    logger.info(f"📍 Segments: {selected_segments}")
    logger.info("=" * 60)
    
    return selected_segments
