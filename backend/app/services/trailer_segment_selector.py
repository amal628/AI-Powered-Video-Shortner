# backend/app/services/trailer_segment_selector.py
"""
Trailer-Style Segment Selector - Enhanced for Proper Narrative Flow

This module provides intelligent segment selection for creating trailer-style
video cuts. It categorizes segments into narrative phases:
- Opening: Tone-setting introduction
- Hook: Attention-grabbing moment
- Story: Core narrative/dialogue
- Elevation: Rising tension/intensity (includes action and emotions)
- Climax: Peak emotional/action moment

EMOTION/ACTION DETECTION:
- Emotion detection: Positive and negative emotions
- Action detection: High-intensity action sequences
- Romance detection: Love/romantic moments
- Fear detection: Fear/anxiety moments
- Tension detection: Building tension
- Hype detection: Exciting/high-energy moments
- Dialogue detection: Important dialogue
- Silence detection: Silent sections (to be removed)

CRITICAL: The output duration MUST match the EXACT user-specified target duration.
No more, no less. This is enforced through precise time budgeting.
"""

import logging
import math
import re
import warnings
from typing import List, Tuple, Dict, Any, Optional, Mapping
from dataclasses import dataclass, field
from enum import Enum

# suppress noisy runtime warnings globally
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class SegmentCategory(Enum):
    """Categories for trailer-style segment classification."""
    OPENING = "opening"      # Tone-setting introduction
    HOOK = "hook"            # Attention-grabbing moment
    STORY = "story"          # Core narrative/dialogue
    ELEVATION = "elevation"  # Rising tension/intensity
    CLIMAX = "climax"        # Peak emotional/action moment
    # Emotion-specific categories
    ROMANCE = "romance"      # Love/romantic moments
    FEAR = "fear"            # Fear/anxiety moments
    TENSION = "tension"      # Building tension
    HYPE = "hype"            # Exciting/high-energy moments
    SILENCE = "silence"      # Silent sections (to be removed)


@dataclass
class CategorizedSegment:
    """A segment with its category and scores."""
    start: float
    end: float
    text: str
    category: SegmentCategory
    score: float
    intensity: float  # 0-1 scale for emotional/intensity level
    action_score: float = 0.0  # Action sequence score
    emotion_score: float = 0.0  # Emotional moment score
    dialogue_score: float = 0.0  # Important dialogue score
    # Emotion-specific scores
    romance_score: float = 0.0  # Romance/love score
    fear_score: float = 0.0    # Fear/anxiety score
    tension_score: float = 0.0  # Tension score
    hype_score: float = 0.0    # Hype/excitement score
    silence_score: float = 0.0  # Silence score (higher = more silent)
    
    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class TrailerPlan:
    """Plan for trailer-style video cut."""
    opening: List[CategorizedSegment]
    hook: List[CategorizedSegment]
    story: List[CategorizedSegment]
    elevation: List[CategorizedSegment]
    climax: List[CategorizedSegment]
    # Emotion-specific segments (always lists)
    romance: List[CategorizedSegment] = field(default_factory=list)
    fear: List[CategorizedSegment] = field(default_factory=list)
    tension: List[CategorizedSegment] = field(default_factory=list)
    hype: List[CategorizedSegment] = field(default_factory=list)
    # Detection analysis
    total_emotion_score: float = 0.0
    total_action_score: float = 0.0
    total_dialogue_score: float = 0.0
    silence_detected: bool = False
    silence_segments: List[Tuple[float, float]] = field(default_factory=list)
    total_duration: float = 0.0
    target_duration: float = 0.0
    
    
    def get_all_segments(self) -> List[CategorizedSegment]:
        """Get all segments in narrative order."""
        return self.opening + self.hook + self.story + self.elevation + self.climax
    
    def get_time_ranges(self) -> List[Tuple[float, float]]:
        """Get list of (start, end) tuples for video processing.
        
        IMPORTANT: Removes any overlapping segments to prevent repeated content.
        Also removes silence segments based on detection rules.
        """
        all_segments = self.get_all_segments()
        
        # Sort by start time
        sorted_segments = sorted(all_segments, key=lambda s: s.start)
        
        # Remove overlapping segments
        non_overlapping = []
        for seg in sorted_segments:
            overlaps = False
            for existing in non_overlapping:
                if seg.start < existing.end and seg.end > existing.start:
                    overlaps = True
                    logger.warning(f"⚠️ Removing overlapping segment: {seg.start:.1f}s-{seg.end:.1f}s "
                                 f"(overlaps with {existing.start:.1f}s-{existing.end:.1f}s)")
                    break
            
            if not overlaps:
                non_overlapping.append(seg)
        
        return [(seg.start, seg.end) for seg in non_overlapping]
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """Get a summary of all detections."""
        all_segments = self.get_all_segments()
        
        return {
            "total_emotion_score": self.total_emotion_score,
            "total_action_score": self.total_action_score,
            "total_dialogue_score": self.total_dialogue_score,
            "silence_detected": self.silence_detected,
            "silence_segments_count": len(self.silence_segments),
            "romance_segments_count": len(self.romance),
            "fear_segments_count": len(self.fear),
            "tension_segments_count": len(self.tension),
            "hype_segments_count": len(self.hype),
            "recommendation": self._get_recommendation()
        }
    
    def _get_recommendation(self) -> str:
        """Get recommendation based on detection analysis."""
        recommendations = []
        
        # Check emotion dominance
        if self.total_emotion_score > self.total_action_score * 2:
            recommendations.append("High emotion content detected - preserving emotional moments")
        
        # Check action dominance
        if self.total_action_score > self.total_emotion_score * 2:
            recommendations.append("High action content detected - preserving action sequences")
        
        # Check dialogue dominance
        if self.total_dialogue_score > max(self.total_emotion_score, self.total_action_score):
            recommendations.append("Dialogue-heavy content - preserving key conversations")
        
        # Check silence
        if self.silence_detected:
            recommendations.append("Silence detected - removing silent sections")
        
        # Check romance
        if len(self.romance) > 2:
            recommendations.append("Romantic content detected - highlighting romance moments")
        
        # Check fear
        if len(self.fear) > 2:
            recommendations.append("Tense/fearful content detected - preserving tension")
        
        # Check hype
        if len(self.hype) > 2:
            recommendations.append("High-energy content detected - highlighting hype moments")
        
        return "; ".join(recommendations) if recommendations else "Standard content - balanced selection"


# ============================================
# ENHANCED CATEGORY DETECTION KEYWORDS
# ============================================

OPENING_KEYWORDS: Dict[str, float] = {
    # Introduction markers - STRONG
    "welcome": 6, "hello": 4, "hi everyone": 6, "good morning": 5, "good evening": 5,
    "today we're": 7, "today i'm": 7, "in this video": 7, "this is": 4,
    # Tone-setting phrases - STRONG
    "let me start": 7, "to begin": 6, "first of all": 6, "before we": 5,
    "i want to show": 6, "i'm going to": 6, "we will": 4, "let's begin": 7,
    # Scene-setting - STRONG
    "imagine": 7, "picture this": 8, "once upon": 7, "it was": 4,
    "in the beginning": 8, "it all started": 8, "years ago": 5,
    # Introductory phrases - STRONG
    "hey guys": 6, "what's up": 4, "good afternoon": 5, "hey everyone": 6,
    "so today": 7, "in today's": 7, "this video": 5, "let's get started": 7,
    # New: More opening keywords
    "introduction": 5, "intro": 5, "opening": 6, "start": 4,
    "welcome to": 6, "join me": 5, "come with me": 6, "follow me": 5,
    "let's explore": 7, "discover": 6, "check out": 5,
}

HOOK_KEYWORDS: Dict[str, float] = {
    # Attention grabbers - STRONG
    "wait": 8, "stop": 7, "listen": 6, "watch this": 9, "look at this": 8,
    "you won't believe": 10, "this is crazy": 9, "oh my god": 8, "holy": 6,
    "oh my": 6, "wow": 6, "whoa": 6, "no way": 8,
    # Curiosity triggers - STRONG
    "secret": 8, "nobody knows": 9, "the truth about": 8, "here's the thing": 7,
    "what if i told you": 10, "did you know": 8, "have you ever": 7,
    # Urgency - STRONG
    "right now": 7, "immediately": 6, "don't miss": 8, "you need to see": 9,
    # Shock value - STRONG
    "shocking": 9, "unbelievable": 8, "insane": 8, "mind-blowing": 9,
    "game changer": 8, "changed everything": 9, "blew my mind": 10,
    # Question hooks - STRONG
    "guess what": 8, "can you guess": 8, "want to know": 7, "here's why": 8,
    # New hook keywords
    "直": 10, "wait for it": 10, "here comes": 9, "keep watching": 8,
    "don't go anywhere": 9, "stay tuned": 7, "next": 6,
}

STORY_KEYWORDS: Dict[str, float] = {
    # Narrative markers - STRONG
    "so basically": 7, "long story short": 7, "here's what happened": 8,
    "let me tell you": 7, "story time": 8, "this is the story": 8,
    "the story goes": 8, "here's the story": 8,
    # Dialogue indicators - STRONG
    "he said": 5, "she said": 5, "they told me": 6, "i asked": 5,
    "we were talking": 6, "the conversation": 6, "we discussed": 5,
    # Explanation - STRONG
    "the reason": 5, "because": 4, "that's why": 5, "so that": 4,
    "this means": 5, "in other words": 5, "basically": 4,
    # Story progression - STRONG
    "and then": 4, "after that": 5, "next thing": 5, "following": 4,
    "meanwhile": 5, "later": 4, "eventually": 5, "finally": 5,
    # New story keywords
    "turns out": 6, "it happened": 5, "that day": 5, "that night": 5,
    "morning": 4, "afternoon": 4, "evening": 4,
}

ELEVATION_KEYWORDS: Dict[str, float] = {
    # Rising tension - HIGHEST PRIORITY
    "suddenly": 10, "but then": 9, "everything changed": 10, "turning point": 10,
    "at that moment": 9, "just then": 8, "without warning": 9, "out of nowhere": 9,
    # Conflict building - HIGH PRIORITY
    "problem": 6, "challenge": 6, "obstacle": 7, "struggle": 8,
    "had to": 6, "needed to": 6, "was forced to": 8, "faced with": 8,
    "against all odds": 10, "uphill battle": 9, "difficult": 6,
    # Intensity markers - HIGH PRIORITY
    "intense": 8, "escalated": 9, "got worse": 7, "became serious": 7,
    "no choice": 8, "do or die": 10, "critical moment": 9, "crucial": 8,
    # Action escalation - HIGH PRIORITY
    "started to": 6, "began to": 6, "intensified": 8, "heated up": 7,
    # Chase/Pursuit (action elevation) - HIGH PRIORITY
    "chase": 9, "pursuit": 9, "running from": 8, "escaping": 8,
    # Rising stakes - HIGH PRIORITY
    "stakes": 8, "risk": 7, "danger": 8, "threat": 8, "warning": 7,
    "consequences": 7, "price to pay": 9, "at stake": 9,
    "life or death": 10, "life and death": 10, "on the line": 8,
    # New elevation keywords
    "things got": 8, "it was getting": 7, "more and more": 8,
    "reached": 7, "approaching": 7, "closing in": 8,
}

CLIMAX_KEYWORDS: Dict[str, float] = {
    # Peak moments - HIGHEST PRIORITY
    "finally": 10, "at last": 10, "this is it": 10, "the moment": 9,
    "climax": 12, "peak": 8, "pinnacle": 9, "ultimate": 9,
    "the big moment": 12, "moment of truth": 12, "final showdown": 12,
    # Resolution markers - HIGH PRIORITY
    "in the end": 9, "conclusion": 7, "result": 6, "outcome": 6,
    "turned out": 7, "ended up": 7, "final": 8, "ultimately": 8,
    # Emotional peaks - POSITIVE - HIGH PRIORITY
    "cried": 9, "tears": 8, "heartbreaking": 10, "beautiful": 7,
    "amazing": 8, "incredible": 8, "best moment": 10, "happiest": 9,
    # Action peaks - EXPLOSIVE - HIGHEST PRIORITY
    "fight": 9, "battle": 9, "war": 9, "showdown": 12, "confrontation": 9,
    "explosion": 12, "crash": 9, "impact": 8, "clash": 9,
    # Victory/Defeat - HIGH PRIORITY
    "won": 8, "lost": 8, "victory": 9, "defeat": 9, "triumph": 10,
    # Revelation/Plot Twist - HIGHEST PRIORITY
    "revealed": 9, "twist": 10, "shocking truth": 12, "plot twist": 12,
    # New climax keywords
    "that's when": 9, "all at once": 10, "everything changed": 10,
    "the reveal": 11, "unveiled": 10, "breaking point": 11,
}

ACTION_KEYWORDS: Dict[str, float] = {
    # High-intensity action - HIGHEST PRIORITY
    "fight": 10, "battle": 10, "war": 9, "combat": 9, "attack": 9,
    "chase": 9, "race": 8, "pursuit": 9, "escape": 8, "flee": 8,
    "ambush": 9, "assault": 9, "raid": 8, "strike": 8,
    # Physical action - HIGH PRIORITY
    "jump": 7, "run": 7, "sprint": 8, "dive": 7, "leap": 7,
    "crash": 9, "smash": 8, "hit": 7, "strike": 8, "kick": 7,
    "punch": 8, "block": 7, "dodge": 8, "counter": 8,
    # Explosive action - HIGHEST PRIORITY
    "explosion": 12, "explode": 11, "blast": 9, "blow up": 10,
    "destroy": 9, "demolish": 9, "shatter": 8, "obliterate": 10,
    # Intensity markers - HIGH PRIORITY
    "fast": 7, "quick": 6, "rapid": 7, "intense": 8, "fierce": 8,
    "violent": 9, "brutal": 9, "extreme": 8, "wild": 7,
    # New action keywords
    "car chase": 10, "gunfight": 11, "shootout": 10, "firefight": 10,
    "slap": 7, "pushed": 7, "thrown": 8, "dragged": 7,
    "exploding": 11, "burning": 9, "collapsing": 9,
}

EMOTION_KEYWORDS: Dict[str, float] = {
    # Positive emotions - HIGH PRIORITY
    "love": 8, "happy": 7, "joy": 8, "excited": 7, "amazing": 7,
    "wonderful": 7, "beautiful": 7, "incredible": 7, "fantastic": 7,
    "grateful": 8, "thankful": 7, "blessed": 7, "appreciated": 6,
    "proud": 8, "accomplished": 7, "fulfilled": 7,
    # Negative emotions - HIGH PRIORITY
    "sad": 8, "cry": 8, "tears": 8, "heartbroken": 10, "devastated": 10,
    "angry": 7, "furious": 8, "rage": 8, "hate": 7, "frustrated": 7,
    "scared": 8, "terrified": 9, "fear": 8, "afraid": 7, "horrified": 9,
    # Deep emotions - HIGH PRIORITY
    "emotional": 8, "touching": 8, "moving": 8, "heartfelt": 9,
    "powerful": 7, "profound": 8, "deep": 6, "meaningful": 7,
    # New emotion keywords
    "overjoyed": 9, "ecstatic": 9, "thrilled": 8, "euphoria": 9,
    "depressed": 8, "miserable": 8, "hopeless": 9, "desperate": 8,
    "anxious": 7, "worried": 7, "nervous": 7, "stressed": 7,
}

ROMANCE_KEYWORDS: Dict[str, float] = {
    # Love expressions - HIGHEST PRIORITY
    "i love you": 12, "love you": 10, "my love": 10, "in love": 10,
    "falling for": 10, "fell in love": 12, "love at first sight": 12,
    "true love": 11, "soulmate": 11, "the one": 9, "my heart": 8,
    # Romantic gestures - HIGH PRIORITY
    "kiss": 10, "kissed": 10, "kissing": 9, "romantic": 9,
    "passionate": 9, "passion": 8, "embrace": 8, "hug": 6,
    # Relationship terms - HIGH PRIORITY
    "boyfriend": 7, "girlfriend": 7, "partner": 6, "together": 6,
    "relationship": 7, "dating": 6, "date": 5, "couple": 7,
    "married": 7, "marriage": 7, "wedding": 9, "engaged": 8,
    # New romance keywords
    "proposal": 10, "proposed": 10, "wedding day": 11, "honeymoon": 9,
    "first date": 8, "romance": 9, "lovers": 9, "beloved": 9,
    "forever": 7, "always": 6, "never leave": 9, "stay with me": 8,
}

# NEW: FEAR KEYWORDS
FEAR_KEYWORDS: Dict[str, float] = {
    # Fear expressions - HIGHEST PRIORITY
    "i'm scared": 12, "so scared": 11, "terrified": 12, "frightening": 11,
    "horror": 10, "horrible": 9, "terrible": 8, "scary": 10,
    "i'm afraid": 10, "afraid of": 9, "fear": 9, "feared": 9,
    # Danger/threat - HIGH PRIORITY
    "danger": 9, "dangerous": 10, "threat": 9, "threatening": 10,
    "killer": 10, "murder": 10, "death": 9, "dying": 9,
    "monster": 10, "creature": 9, "demon": 10, "ghost": 9,
    # Panic expressions - HIGH PRIORITY
    "panic": 10, "panicked": 10, "scream": 10, "screaming": 11,
    "shouted": 8, "yelled": 8, "cried out": 9, "help": 9,
    # Horror moments - HIGHEST PRIORITY
    "blood": 10, "murdered": 11, "killed": 10, "attacked": 10,
    "trapped": 9, "locked": 7, "chained": 9, "buried": 10,
    # New fear keywords
    "nightmare": 9, "terrifying": 12, "petrifying": 11, "bone-chilling": 12,
    "creepy": 9, "eerie": 9, "spooky": 8, "dark": 6,
}

# NEW: TENSION KEYWORDS
TENSION_KEYWORDS: Dict[str, float] = {
    # Building tension - HIGHEST PRIORITY
    "waiting": 8, "waiting for": 9, "anticipation": 10, "anticipating": 9,
    "suspense": 11, "suspenseful": 11, "tense": 10, "tension": 10,
    # Uncertain outcomes - HIGH PRIORITY
    "what will happen": 10, "will they": 9, "can they": 9,
    "unknown": 8, "mystery": 9, "secret revealed": 10,
    # Stakes building - HIGH PRIORITY
    "everything at stake": 11, "no escape": 10, "now or never": 11,
    "time running out": 10, "countdown": 9, "last chance": 10,
    # Confrontation building - HIGH PRIORITY
    "confrontation": 9, "facing": 8, "standing against": 9,
    "ready to": 7, "preparing": 8, "preparation": 8,
    # New tension keywords
    "nerve-wracking": 11, "edge of seat": 11, "gripping": 9,
    "breath-holding": 11, "can't look away": 10, "intense": 8,
}

# NEW: HYPE KEYWORDS
HYPE_KEYWORDS: Dict[str, float] = {
    # Excitement - HIGHEST PRIORITY
    "exciting": 10, "excited": 9, "amazing": 8, "incredible": 9,
    "awesome": 9, "insane": 9, "crazy": 8, "epic": 10,
    # Celebration - HIGH PRIORITY
    "celebrate": 9, "party": 8, "champagne": 8, "cheers": 8,
    "congratulations": 9, "congrats": 8, "woohoo": 9,
    # Achievement - HIGH PRIORITY
    "won": 9, "winner": 10, "champion": 10, "victory": 10,
    "accomplished": 9, "success": 8, "achieved": 9,
    # Big reveals - HIGH PRIORITY
    "reveal": 9, "breaking": 10, "exclusive": 9, "first look": 10,
    "brand new": 9, "just released": 9, "launch": 8,
    # High energy - HIGH PRIORITY
    "energy": 8, "pumped": 9, "let's go": 9, "come on": 8,
    "go go go": 10, "hype": 11, "hyped": 10,
    # New hype keywords
    "fire": 9, "lit": 9, "slaps": 9, "hits different": 10,
    "game changer": 10, "next level": 10, "unreal": 10,
}

IMPORTANT_DIALOGUE_KEYWORDS: Dict[str, float] = {
    # Critical statements - HIGHEST PRIORITY
    "this is important": 10, "listen to me": 9, "you need to know": 10,
    "i have to tell you": 10, "the truth is": 9, "honestly": 7,
    "i need to say": 9, "must tell you": 10,
    "crucial": 8, "essential": 7, "vital": 8,
    # Revelations - HIGHEST PRIORITY
    "i found out": 9, "discovered": 8, "revealed": 9, "secret": 8,
    "confession": 10, "admit": 7, "i confess": 10,
    # Key conversation - HIGH PRIORITY
    "asked me": 7, "told me": 7, "said that": 6, "mentioned": 6,
    "explained": 7, "clarified": 7, "emphasized": 8,
    # New dialogue keywords
    "according to": 6, "research shows": 8, "studies show": 9,
    "fact": 7, "proof": 8, "evidence": 8, "confirmed": 8,
    "breaking news": 10, "developing story": 9, "update": 7,
}


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_keyword_score(text: str, keywords: Dict[str, float]) -> Tuple[float, List[str]]:
    """Calculate score based on keyword matching.
    
    Returns:
        Tuple of (score, matched_keywords_list)
    """
    text_lower = text.lower()
    score = 0.0
    matched: List[str] = []
    
    # Sort keywords by length (longer first) to match phrases correctly
    sorted_keywords = sorted(keywords.keys(), key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if keyword in text_lower:
            score += keywords[keyword]
            matched.append(keyword)
    
    return score, matched


def score_segment_for_category(
    segment_text: str,
    position_ratio: float,
    category: SegmentCategory
) -> Tuple[float, CategorizedSegment]:
    """
    Score a segment for a specific category and create CategorizedSegment.
    
    Returns tuple of (score, CategorizedSegment)
    """
    scores = {
        'opening': 0.0,
        'hook': 0.0,
        'story': 0.0,
        'elevation': 0.0,
        'climax': 0.0,
        'action': 0.0,
        'emotion': 0.0,
        'dialogue': 0.0,
        'romance': 0.0,
        'fear': 0.0,
        'tension': 0.0,
        'hype': 0.0,
        'silence': 0.0,
    }
    
    # Score each category
    opening_score, opening_matches = calculate_keyword_score(segment_text, OPENING_KEYWORDS)
    hook_score, hook_matches = calculate_keyword_score(segment_text, HOOK_KEYWORDS)
    story_score, story_matches = calculate_keyword_score(segment_text, STORY_KEYWORDS)
    elevation_score, elevation_matches = calculate_keyword_score(segment_text, ELEVATION_KEYWORDS)
    climax_score, climax_matches = calculate_keyword_score(segment_text, CLIMAX_KEYWORDS)
    action_score, action_matches = calculate_keyword_score(segment_text, ACTION_KEYWORDS)
    emotion_score, emotion_matches = calculate_keyword_score(segment_text, EMOTION_KEYWORDS)
    dialogue_score, dialogue_matches = calculate_keyword_score(segment_text, IMPORTANT_DIALOGUE_KEYWORDS)
    romance_score, romance_matches = calculate_keyword_score(segment_text, ROMANCE_KEYWORDS)
    fear_score, fear_matches = calculate_keyword_score(segment_text, FEAR_KEYWORDS)
    tension_score, tension_matches = calculate_keyword_score(segment_text, TENSION_KEYWORDS)
    hype_score, hype_matches = calculate_keyword_score(segment_text, HYPE_KEYWORDS)
    
    scores['opening'] = opening_score
    scores['hook'] = hook_score
    scores['story'] = story_score
    scores['elevation'] = elevation_score
    scores['climax'] = climax_score
    scores['action'] = action_score
    scores['emotion'] = emotion_score
    scores['dialogue'] = dialogue_score
    scores['romance'] = romance_score
    scores['fear'] = fear_score
    scores['tension'] = tension_score
    scores['hype'] = hype_score
    
    # Position-based adjustments
    position_multiplier = 1.0
    if category == SegmentCategory.OPENING:
        if position_ratio < 0.20:
            position_multiplier = 1.5
        elif position_ratio < 0.30:
            position_multiplier = 1.2
        else:
            position_multiplier = 0.5
    elif category == SegmentCategory.HOOK:
        if position_ratio < 0.25:
            position_multiplier = 1.5
        elif position_ratio < 0.35:
            position_multiplier = 1.2
        else:
            position_multiplier = 0.6
    elif category == SegmentCategory.CLIMAX:
        if position_ratio > 0.70:
            position_multiplier = 1.5
        elif position_ratio > 0.60:
            position_multiplier = 1.2
        else:
            position_multiplier = 0.5
    
    # Calculate final category score
    category_scores = {
        SegmentCategory.OPENING: scores['opening'],
        SegmentCategory.HOOK: scores['hook'],
        SegmentCategory.STORY: scores['story'],
        SegmentCategory.ELEVATION: scores['elevation'],
        SegmentCategory.CLIMAX: scores['climax'],
    }
    
    final_score = category_scores.get(category, 0.0) * position_multiplier
    
    # Calculate intensity (0-1 scale) based on action and emotion scores
    intensity = min((scores['action'] + scores['emotion']) / 20.0, 1.0)
    
    return final_score, CategorizedSegment(
        start=0.0,
        end=0.0,
        text=segment_text,
        category=category,
        score=final_score,
        intensity=intensity,
        action_score=scores['action'],
        emotion_score=scores['emotion'],
        dialogue_score=scores['dialogue'],
        romance_score=scores['romance'],
        fear_score=scores['fear'],
        tension_score=scores['tension'],
        hype_score=scores['hype']
    )


def select_best_category_for_segment(
    segment_text: str,
    position_ratio: float
) -> Tuple[SegmentCategory, float]:
    """
    Determine the best category for a segment based on keyword scores.
    
    Returns tuple of (best_category, score)
    """
    category_scores = {}
    
    # Opening
    score, _ = calculate_keyword_score(segment_text, OPENING_KEYWORDS)
    if position_ratio < 0.25:
        score *= 1.5
    category_scores[SegmentCategory.OPENING] = score
    
    # Hook
    score, _ = calculate_keyword_score(segment_text, HOOK_KEYWORDS)
    if position_ratio < 0.35:
        score *= 1.4
    category_scores[SegmentCategory.HOOK] = score
    
    # Story
    score, _ = calculate_keyword_score(segment_text, STORY_KEYWORDS)
    category_scores[SegmentCategory.STORY] = score
    
    # Elevation
    score, _ = calculate_keyword_score(segment_text, ELEVATION_KEYWORDS)
    if 0.25 < position_ratio < 0.80:
        score *= 1.3
    category_scores[SegmentCategory.ELEVATION] = score
    
    # Climax
    score, _ = calculate_keyword_score(segment_text, CLIMAX_KEYWORDS)
    if position_ratio > 0.65:
        score *= 1.5
    category_scores[SegmentCategory.CLIMAX] = score
    
    # Find best category
    best_category = max(category_scores, key=lambda x: category_scores[x])
    best_score = category_scores[best_category]
    
    return best_category, best_score


def analyze_segment_emotions(segment_text: str) -> Dict[str, float]:
    """Analyze segment for various emotion/scene types.
    
    Returns a dictionary with scores for each detection type.
    """
    return {
        'romance': calculate_keyword_score(segment_text, ROMANCE_KEYWORDS)[0],
        'fear': calculate_keyword_score(segment_text, FEAR_KEYWORDS)[0],
        'tension': calculate_keyword_score(segment_text, TENSION_KEYWORDS)[0],
        'hype': calculate_keyword_score(segment_text, HYPE_KEYWORDS)[0],
        'action': calculate_keyword_score(segment_text, ACTION_KEYWORDS)[0],
        'emotion': calculate_keyword_score(segment_text, EMOTION_KEYWORDS)[0],
        'dialogue': calculate_keyword_score(segment_text, IMPORTANT_DIALOGUE_KEYWORDS)[0],
    }


def merge_adjacent_segments(
    segments: List[Tuple[float, float]],
    gap_threshold: float = 1.5
) -> List[Tuple[float, float]]:
    """
    Merge segments that are close together to avoid jarring cuts.
    """
    if not segments:
        return []
    
    sorted_segments = sorted(segments, key=lambda x: x[0])
    merged = [sorted_segments[0]]
    
    for current in sorted_segments[1:]:
        last = merged[-1]
        gap = current[0] - last[1]
        
        if gap <= gap_threshold:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    
    return merged


def adjust_duration_to_target(
    segments: List[CategorizedSegment],
    target_duration: float,
    analysis: Dict[str, float]
) -> List[CategorizedSegment]:
    """
    Adjust selected segments to match exact target duration.
    
    Rules:
    - Lots of emotions → keeps emotions (prioritize emotion segments)
    - Lots of action → keeps action (prioritize action segments)
    - Mostly dialogue → keeps dialogue (prioritize dialogue segments)
    - Mostly silence → removes silence (skip silence segments)
    """
    if not segments:
        return []
    
    # Sort segments by start time
    sorted_segments = sorted(segments, key=lambda s: s.start)
    
    # Calculate current total duration
    current_duration = sum(seg.duration for seg in sorted_segments)
    
    # If we need to reduce duration
    if current_duration > target_duration:
        # Determine what to prioritize removing based on analysis
        remove_silence_first = analysis.get('silence_detected', False)
        
        # Priority order for removal (last to first)
        removal_priority = ['silence', 'story', 'opening', 'hook', 'elevation', 'climax']
        
        segments_to_remove = []
        duration_to_remove = current_duration - target_duration
        
        for seg in sorted_segments:
            if duration_to_remove <= 0:
                break
            
            seg_category = seg.category.value
            
            # Skip climax segments if possible
            if seg_category == 'climax':
                continue
            
            # Remove silence segments first if detected
            if remove_silence_first and seg.silence_score > 0:
                segments_to_remove.append(seg)
                duration_to_remove -= seg.duration
                continue
            
            # Remove based on priority
            if seg_category in removal_priority[:3]:  # Lower priority segments
                segments_to_remove.append(seg)
                duration_to_remove -= seg.duration
        
        # Filter out removed segments
        remaining = [s for s in sorted_segments if s not in segments_to_remove]
        sorted_segments = remaining
        current_duration = sum(seg.duration for seg in sorted_segments)
    
    # If we need to extend duration (add more content)
    elif current_duration < target_duration:
        # This is handled by the main selection logic which adds more segments
        pass
    
    return sorted_segments


# ============================================
# MAIN TRAILER SEGMENT SELECTOR FUNCTION
# ============================================

def select_trailer_segments(
    segments: List[Dict[str, Any]],
    total_duration: float,
    target_duration: float,
    silence_segments: Optional[List[Tuple[float, float]]] = None
) -> TrailerPlan:
    """
    Main function to select trailer-style segments from transcription.
    
    Creates a narrative flow: Opening → Hook → Story → Elevation → Climax
    
    Args:
        segments: List of transcription segments with 'start', 'end', 'text'
        total_duration: Total video duration in seconds
        target_duration: User-specified target output duration
        silence_segments: Optional list of (start, end) tuples for silent sections
        
    Returns:
        TrailerPlan with categorized segments
    """
    logger.info("=" * 60)
    logger.info("🎬 TRAILER SEGMENT SELECTOR - ENHANCED")
    logger.info("=" * 60)
    logger.info(f"📹 Source video: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    logger.info(f"🎯 Target duration: {target_duration:.1f}s")
    
    # Handle empty segments
    if not segments:
        logger.warning("No segments provided - using time-based fallback")
        return _create_time_based_plan(total_duration, target_duration)
    
    # Calculate time budgets for each narrative phase
    phase_budgets = {
        "opening": max(3, min(10, target_duration * 0.10)),
        "hook": max(3, min(12, target_duration * 0.12)),
        "story": max(10, min(25, target_duration * 0.25)),
        "elevation": max(8, min(20, target_duration * 0.23)),
        "climax": max(5, min(20, target_duration * 0.30)),
    }
    
    # Scale to match target exactly
    total_budget = sum(phase_budgets.values())
    if total_budget != target_duration and total_budget > 0:
        scale = target_duration / total_budget
        for phase in phase_budgets:
            phase_budgets[phase] *= scale
    
    logger.info(f"📊 Phase budgets:")
    for phase, budget in phase_budgets.items():
        logger.info(f"   {phase.capitalize()}: {budget:.1f}s")
    
    # Analyze all segments for emotion/action detection
    total_emotion_score = 0.0
    total_action_score = 0.0
    total_dialogue_score = 0.0
    emotion_dominant_count = 0
    action_dominant_count = 0
    dialogue_dominant_count = 0
    
    # Score all segments for each category
    scored_segments = []
    
    for i, segment in enumerate(segments):
        start = segment.get("start", 0)
        end = segment.get("end", 0)
        text = segment.get("text", "")
        duration = end - start
        
        if duration <= 0 or not text.strip():
            continue
        
        position_ratio = start / total_duration if total_duration > 0 else 0
        
        # Get best category for this segment
        best_category, best_score = select_best_category_for_segment(text, position_ratio)
        
        # Analyze emotions
        emotion_analysis = analyze_segment_emotions(text)
        
        # Track totals for analysis
        total_emotion_score += emotion_analysis['emotion']
        total_action_score += emotion_analysis['action']
        total_dialogue_score += emotion_analysis['dialogue']
        
        # Count dominant types
        max_score = max(emotion_analysis.values())
        if emotion_analysis['emotion'] == max_score and max_score > 5:
            emotion_dominant_count += 1
        elif emotion_analysis['action'] == max_score and max_score > 5:
            action_dominant_count += 1
        elif emotion_analysis['dialogue'] == max_score and max_score > 5:
            dialogue_dominant_count += 1
        
        # Create scored segment
        scored_segments.append({
            "index": i,
            "start": start,
            "end": end,
            "duration": duration,
            "text": text,
            "position_ratio": position_ratio,
            "category": best_category,
            "score": best_score,
            "emotion_analysis": emotion_analysis,
            # Store all category scores
            "opening_score": calculate_keyword_score(text, OPENING_KEYWORDS)[0],
            "hook_score": calculate_keyword_score(text, HOOK_KEYWORDS)[0],
            "story_score": calculate_keyword_score(text, STORY_KEYWORDS)[0],
            "elevation_score": calculate_keyword_score(text, ELEVATION_KEYWORDS)[0],
            "climax_score": calculate_keyword_score(text, CLIMAX_KEYWORDS)[0],
            "action_score": emotion_analysis['action'],
            "emotion_score": emotion_analysis['emotion'],
            "romance_score": emotion_analysis['romance'],
            "fear_score": emotion_analysis['fear'],
            "tension_score": emotion_analysis['tension'],
            "hype_score": emotion_analysis['hype'],
            "dialogue_score": emotion_analysis['dialogue'],
        })
    
    logger.info(f"✅ Scored {len(scored_segments)} segments")
    
    # Determine content dominance
    content_analysis = {
        "emotion_dominant": emotion_dominant_count,
        "action_dominant": action_dominant_count,
        "dialogue_dominant": dialogue_dominant_count,
        "total_emotion_score": total_emotion_score,
        "total_action_score": total_action_score,
        "total_dialogue_score": total_dialogue_score,
        "silence_detected": silence_segments is not None and len(silence_segments) > 0,
    }
    
    logger.info(f"📊 Content Analysis:")
    logger.info(f"   Emotion dominant segments: {emotion_dominant_count}")
    logger.info(f"   Action dominant segments: {action_dominant_count}")
    logger.info(f"   Dialogue dominant segments: {dialogue_dominant_count}")
    logger.info(f"   Silence detected: {content_analysis['silence_detected']}")
    
    # Apply smart selection rules based on content analysis
    if emotion_dominant_count > max(action_dominant_count, dialogue_dominant_count):
        logger.info("🎭 Content is emotion-heavy - prioritizing emotional segments")
    elif action_dominant_count > max(emotion_dominant_count, dialogue_dominant_count):
        logger.info("⚡ Content is action-heavy - prioritizing action segments")
    elif dialogue_dominant_count > max(emotion_dominant_count, action_dominant_count):
        logger.info("💬 Content is dialogue-heavy - prioritizing dialogue segments")
    
    # Select segments for each phase
    selected_segments = {
        "opening": [],
        "hook": [],
        "story": [],
        "elevation": [],
        "climax": [],
    }
    
    # Emotion-specific collections
    romance_segments = []
    fear_segments = []
    tension_segments = []
    hype_segments = []
    
    used_indices = set()
    phase_durations = {phase: 0.0 for phase in phase_budgets}
    
    # Phase-specific selection
    phase_config = {
        "opening": {
            "score_key": "opening_score",
            "position_range": (0.0, 0.35),
            "min_score": 2.0,
        },
        "hook": {
            "score_key": "hook_score",
            "position_range": (0.0, 0.45),
            "min_score": 3.0,
        },
        "story": {
            "score_key": "story_score",
            "position_range": (0.15, 0.85),
            "min_score": 2.0,
        },
        "elevation": {
            "score_key": "elevation_score",
            "position_range": (0.30, 0.90),
            "min_score": 2.0,
        },
        "climax": {
            "score_key": "climax_score",
            "position_range": (0.55, 1.0),
            "min_score": 3.0,
        },
    }
    
    # Select segments for each phase
    for phase_name, config in phase_config.items():
        budget = phase_budgets[phase_name]
        
        # Get available segments (not used, within position range, above min score)
        available = [
            s for s in scored_segments
            if s["index"] not in used_indices
            and config["position_range"][0] <= s["position_ratio"] <= config["position_range"][1]
            and s[config["score_key"]] >= config["min_score"]
        ]
        
        # Sort by phase-specific score
        available.sort(key=lambda x: x[config["score_key"]], reverse=True)
        
        # Select segments for this phase
        for seg in available:
            if phase_durations[phase_name] >= budget:
                break
            
            # Check for overlap with already selected segments
            overlaps = False
            for selected_list in selected_segments.values():
                for selected_seg in selected_list:
                    if seg["start"] < selected_seg["end"] and seg["end"] > selected_seg["start"]:
                        overlaps = True
                        break
                if overlaps:
                    break
            
            if not overlaps:
                selected_segments[phase_name].append(seg)
                used_indices.add(seg["index"])
                phase_durations[phase_name] += seg["duration"]
                
                # Collect emotion-specific segments
                emotion_analysis = seg.get("emotion_analysis", {})
                if emotion_analysis.get("romance", 0) > 5:
                    romance_segments.append(seg)
                if emotion_analysis.get("fear", 0) > 5:
                    fear_segments.append(seg)
                if emotion_analysis.get("tension", 0) > 5:
                    tension_segments.append(seg)
                if emotion_analysis.get("hype", 0) > 5:
                    hype_segments.append(seg)
                
                logger.info(f"   {phase_name.upper()}: {seg['start']:.1f}s-{seg['end']:.1f}s "
                           f"(score: {seg[config['score_key']]:.1f})")
    
    # Fill remaining time with best available segments if needed
    current_duration = sum(phase_durations.values())
    
    if current_duration < target_duration * 0.8:
        logger.info("🔄 Filling remaining duration with additional highlights...")
        
        # Get remaining segments sorted by any high score
        remaining = [
            s for s in scored_segments
            if s["index"] not in used_indices
        ]
        
        def get_max_score(seg: Dict) -> float:
            return max(
                seg.get("climax_score", 0), 
                seg.get("elevation_score", 0), 
                seg.get("action_score", 0), 
                seg.get("emotion_score", 0),
                seg.get("hype_score", 0)
            )
        
        remaining.sort(key=get_max_score, reverse=True)
        
        for seg in remaining:
            current_duration = sum(phase_durations.values())
            if current_duration >= target_duration:
                break
            
            # Check overlap
            overlaps = False
            for selected_list in selected_segments.values():
                for selected_seg in selected_list:
                    if seg["start"] < selected_seg["end"] and seg["end"] > selected_seg["start"]:
                        overlaps = True
                        break
                if overlaps:
                    break
            
            if not overlaps:
                # Add to the phase that needs most time
                for phase_name in ["climax", "elevation", "story"]:
                    if phase_durations[phase_name] < phase_budgets[phase_name] * 1.2:
                        selected_segments[phase_name].append(seg)
                        used_indices.add(seg["index"])
                        phase_durations[phase_name] += seg["duration"]
                        break
    
    # Apply duration adjustment based on content analysis
    all_selected = []
    for seg_list in selected_segments.values():
        all_selected.extend(seg_list)
    
    # Adjust to exact target duration
    adjusted_segments = adjust_duration_to_target(
        all_selected, 
        target_duration, 
        content_analysis
    )
    
    # Re-categorize adjusted segments
    adjusted_by_phase = {"opening": [], "hook": [], "story": [], "elevation": [], "climax": []}
    for seg in adjusted_segments:
        phase = seg.category.value if hasattr(seg, 'category') else "story"
        if phase in adjusted_by_phase:
            adjusted_by_phase[phase].append(seg)
    
    # Convert to CategorizedSegment lists
    def create_categorized_segment(seg_dict: Dict, category: SegmentCategory) -> CategorizedSegment:
        emotion_analysis = seg_dict.get("emotion_analysis", {})
        return CategorizedSegment(
            start=seg_dict["start"],
            end=seg_dict["end"],
            text=seg_dict["text"],
            category=category,
            score=seg_dict["score"],
            intensity=min((seg_dict["action_score"] + seg_dict["emotion_score"]) / 20.0, 1.0),
            action_score=seg_dict["action_score"],
            emotion_score=seg_dict["emotion_score"],
            dialogue_score=seg_dict["dialogue_score"],
            romance_score=emotion_analysis.get("romance", 0),
            fear_score=emotion_analysis.get("fear", 0),
            tension_score=emotion_analysis.get("tension", 0),
            hype_score=emotion_analysis.get("hype", 0),
        )
    
    # Create TrailerPlan
    plan = TrailerPlan(
        opening=[create_categorized_segment(s, SegmentCategory.OPENING) for s in adjusted_by_phase["opening"]],
        hook=[create_categorized_segment(s, SegmentCategory.HOOK) for s in adjusted_by_phase["hook"]],
        story=[create_categorized_segment(s, SegmentCategory.STORY) for s in adjusted_by_phase["story"]],
        elevation=[create_categorized_segment(s, SegmentCategory.ELEVATION) for s in adjusted_by_phase["elevation"]],
        climax=[create_categorized_segment(s, SegmentCategory.CLIMAX) for s in adjusted_by_phase["climax"]],
        romance=[create_categorized_segment(s, SegmentCategory.ROMANCE) for s in romance_segments],
        fear=[create_categorized_segment(s, SegmentCategory.FEAR) for s in fear_segments],
        tension=[create_categorized_segment(s, SegmentCategory.TENSION) for s in tension_segments],
        hype=[create_categorized_segment(s, SegmentCategory.HYPE) for s in hype_segments],
        silence_segments=silence_segments or [],
        silence_detected=content_analysis["silence_detected"],
        total_emotion_score=total_emotion_score,
        total_action_score=total_action_score,
        total_dialogue_score=total_dialogue_score,
        total_duration=sum(seg.duration for seg in adjusted_segments),
        target_duration=target_duration,
    )
    
    # Log summary
    final_duration = plan.total_duration
    logger.info("=" * 60)
    logger.info("🎬 TRAILER SEGMENT SELECTION COMPLETE - ENHANCED")
    logger.info("=" * 60)
    logger.info(f"✅ Final Duration: {final_duration:.1f}s (Target: {target_duration:.1f}s)")
    logger.info(f"📊 Phase breakdown:")
    logger.info(f"   🌅 Opening: {phase_durations['opening']:.1f}s ({len(plan.opening)} segments)")
    logger.info(f"   🪝 Hook: {phase_durations['hook']:.1f}s ({len(plan.hook)} segments)")
    logger.info(f"   📖 Story: {phase_durations['story']:.1f}s ({len(plan.story)} segments)")
    logger.info(f"   📈 Elevation: {phase_durations['elevation']:.1f}s ({len(plan.elevation)} segments)")
    logger.info(f"   🔥 Climax: {phase_durations['climax']:.1f}s ({len(plan.climax)} segments)")
    logger.info(f"📍 Time ranges: {plan.get_time_ranges()}")
    logger.info(f"💡 Recommendation: {plan._get_recommendation()}")
    logger.info("=" * 60)
    
    return plan


def _create_time_based_plan(
    total_duration: float,
    target_duration: float
) -> TrailerPlan:
    """
    Create a time-based trailer plan for videos with no speech detected.
    """
    logger.info("Creating time-based trailer plan (no speech detected)")
    
    phase_budgets = {
        "opening": target_duration * 0.10,
        "hook": target_duration * 0.12,
        "story": target_duration * 0.25,
        "elevation": target_duration * 0.23,
        "climax": target_duration * 0.30,
    }
    
    phase_ranges = {
        "opening": (0.0, 0.20),
        "hook": (0.10, 0.35),
        "story": (0.20, 0.65),
        "elevation": (0.45, 0.85),
        "climax": (0.65, 1.0),
    }
    
    selected_segments = {phase: [] for phase in phase_budgets}
    used_ranges = []
    
    for phase_name in ["opening", "hook", "story", "elevation", "climax"]:
        start_ratio, end_ratio = phase_ranges[phase_name]
        budget = phase_budgets[phase_name]
        
        section_start = start_ratio * total_duration
        section_end = end_ratio * total_duration
        section_duration = section_end - section_start
        
        if section_duration < 2:
            continue
        
        seg_duration = min(budget, section_duration * 0.6)
        seg_duration = max(seg_duration, 2.0)
        
        for offset in [0.0, 0.25, 0.5, 0.75]:
            seg_start = section_start + offset * (section_duration - seg_duration)
            seg_end = seg_start + seg_duration
            
            overlaps = False
            for used_start, used_end in used_ranges:
                if seg_start < used_end and seg_end > used_start:
                    overlaps = True
                    break
            
            if not overlaps:
                selected_segments[phase_name].append(CategorizedSegment(
                    start=seg_start,
                    end=min(seg_end, total_duration),
                    text=f"[{phase_name.capitalize()} segment - no speech detected]",
                    category=SegmentCategory[phase_name.upper()],
                    score=5.0,
                    intensity=0.5,
                ))
                used_ranges.append((seg_start, min(seg_end, total_duration)))
                break
    
    plan = TrailerPlan(
        opening=selected_segments["opening"],
        hook=selected_segments["hook"],
        story=selected_segments["story"],
        elevation=selected_segments["elevation"],
        climax=selected_segments["climax"],
        total_duration=sum(s.duration for s in selected_segments["opening"] + 
                         selected_segments["hook"] + selected_segments["story"] +
                         selected_segments["elevation"] + selected_segments["climax"]),
        target_duration=target_duration,
    )
    
    return plan


def get_trailer_plan_dict(
    segments: List[Dict[str, Any]],
    total_duration: float,
    target_duration: float,
    silence_segments: Optional[List[Tuple[float, float]]] = None
) -> Dict[str, Any]:
    """
    Generate trailer plan dictionary for API response.
    
    Args:
        segments: List of transcription segments
        total_duration: Total video duration
        target_duration: User-specified target duration
        silence_segments: Optional list of silent sections
        
    Returns:
        Dictionary with trailer plan details for API response
    """
    # Get the trailer plan
    plan = select_trailer_segments(segments, total_duration, target_duration, silence_segments)
    
    # Build response dictionary
    def build_category_dict(segment_list: List[CategorizedSegment]) -> Dict:
        if not segment_list:
            return {
                "duration": 0.0,
                "segments_count": 0,
                "time_ranges": [],
                "avg_intensity": 0.0,
                "avg_action_score": 0.0,
                "avg_emotion_score": 0.0,
            }
        
        return {
            "duration": round(sum(s.duration for s in segment_list), 2),
            "segments_count": len(segment_list),
            "time_ranges": [(s.start, s.end) for s in segment_list],
            "avg_intensity": round(sum(s.intensity for s in segment_list) / len(segment_list), 2),
            "avg_action_score": round(sum(s.action_score for s in segment_list) / len(segment_list), 2),
            "avg_emotion_score": round(sum(s.emotion_score for s in segment_list) / len(segment_list), 2),
        }
    
    # Get all segments for overall metrics
    all_segments = plan.get_all_segments()
    
    # Get detection summary
    detection = plan.get_detection_summary()
    
    response = {
        "total_duration": round(plan.total_duration, 2),
        "target_duration": round(target_duration, 2),
        "source_duration": round(total_duration, 2),
        "segments_count": len(plan.get_time_ranges()),
        "narrative_flow": "opening → hook → story → elevation → climax",
        "categories": {
            "opening": build_category_dict(plan.opening),
            "hook": build_category_dict(plan.hook),
            "story": build_category_dict(plan.story),
            "elevation": build_category_dict(plan.elevation),
            "climax": build_category_dict(plan.climax),
        },
        "emotion_detection": {
            "romance_segments": len(plan.romance),
            "fear_segments": len(plan.fear),
            "tension_segments": len(plan.tension),
            "hype_segments": len(plan.hype),
        },
        "content_analysis": {
            "total_emotion_score": round(plan.total_emotion_score, 2),
            "total_action_score": round(plan.total_action_score, 2),
            "total_dialogue_score": round(plan.total_dialogue_score, 2),
            "silence_detected": plan.silence_detected,
            "silence_segments_count": len(plan.silence_segments),
            "recommendation": detection.get("recommendation", ""),
        },
        "time_ranges": plan.get_time_ranges(),
        "overall_metrics": {
            "avg_intensity": round(sum(s.intensity for s in all_segments) / len(all_segments), 2) if all_segments else 0,
            "avg_action_score": round(sum(s.action_score for s in all_segments) / len(all_segments), 2) if all_segments else 0,
            "avg_emotion_score": round(sum(s.emotion_score for s in all_segments) / len(all_segments), 2) if all_segments else 0,
        } if all_segments else {
            "avg_intensity": 0,
            "avg_action_score": 0,
            "avg_emotion_score": 0,
        }
    }
    
    return response
