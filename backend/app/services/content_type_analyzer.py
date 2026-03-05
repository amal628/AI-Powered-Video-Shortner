import re
import logging
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Content type categories for video classification."""
    ACTION = "action"
    DRAMA = "drama"
    COMEDY = "comedy"
    ROMANCE = "romance"
    THRILLER = "thriller"
    HORROR = "horror"
    SCI_FI = "sci-fi"
    DOCUMENTARY = "documentary"
    EDUCATIONAL = "educational"
    SPORTS = "sports"
    GAMING = "gaming"
    MUSIC = "music"
    VLOG = "vlog"
    TUTORIAL = "tutorial"
    INTERVIEW = "interview"
    TRAVEL = "travel"
    FOOD = "food"
    LIFESTYLE = "lifestyle"
    UNKNOWN = "unknown"


@dataclass
class ContentTypeAnalysis:
    """Result of content type analysis."""
    primary_type: ContentType
    confidence: float
    secondary_types: List[Tuple[ContentType, float]]
    keywords: List[str]
    emotional_indicators: Dict[str, int]
    pacing_indicators: Dict[str, int]
    genre_confidence: Dict[ContentType, float]


class ContentTypeAnalyzer:
    """Analyzes video content to determine genre and content type."""
    
    def __init__(self):
        # Content type keyword mappings
        self.content_keywords = {
            ContentType.ACTION: [
                # Action keywords
                "fight", "battle", "chase", "run", "attack", "defend", "explosion", "crash", "hit", "strike",
                "fast", "quick", "intense", "action", "combat", "danger", "risk", "speed", "power", "force",
                "weapon", "gun", "sword", "knife", "explosive", "blast", "impact", "crash", "collision",
                "adrenaline", "thrill", "excitement", "rush", "dangerous", "violent", "aggressive", "fierce",
                "battle", "war", "conflict", "struggle", "confrontation", "attack", "defend", "protect", "save",
                # Sports action
                "game", "match", "competition", "tournament", "championship", "win", "lose", "score", "goal",
                "point", "victory", "defeat", "team", "player", "coach", "training", "practice", "skill", "talent"
            ],
            ContentType.DRAMA: [
                # Drama keywords
                "love", "hate", "family", "friend", "relationship", "emotion", "feeling", "heart", "soul", "life",
                "death", "loss", "grief", "sadness", "tears", "cry", "pain", "suffering", "struggle", "problem",
                "issue", "conflict", "argument", "fight", "disagreement", "misunderstanding", "betrayal", "trust",
                "faith", "hope", "dream", "wish", "desire", "want", "need", "must", "should", "could", "would",
                # Family drama
                "mother", "father", "son", "daughter", "brother", "sister", "grandmother", "grandfather", "parent",
                "child", "kid", "baby", "family", "home", "house", "room", "school", "work", "job", "career", "life"
            ],
            ContentType.COMEDY: [
                # Comedy keywords
                "funny", "hilarious", "joke", "laugh", "humor", "ridiculous", "silly", "stupid", "dumb", "crazy",
                "weird", "strange", "odd", "fun", "entertainment", "show", "performance", "act", "actor", "actress",
                "comedian", "comedy", "laugh", "giggle", "chuckle", "smile", "happy", "joy", "pleasure", "enjoyment",
                "amusing", "entertaining", "witty", "clever", "smart", "brilliant", "genius", "talented", "gifted",
                # Situational comedy
                "mistake", "error", "fail", "oops", "whoops", "accident", "incident", "problem", "issue", "difficulty"
            ],
            ContentType.ROMANCE: [
                # Romance keywords
                "love", "romance", "relationship", "dating", "marriage", "wedding", "proposal", "kiss", "hug", "touch",
                "heart", "soul", "emotion", "feeling", "passion", "desire", "attraction", "chemistry", "connection",
                "bond", "link", "tie", "relationship", "couple", "pair", "team", "together", "united", "combined",
                # Romantic situations
                "date", "dinner", "movie", "walk", "talk", "conversation", "discussion", "chat", "message", "text"
            ],
            ContentType.THRILLER: [
                # Thriller keywords
                "mystery", "secret", "hidden", "unknown", "secretive", "mysterious", "suspicious", "suspense", "tension",
                "anxiety", "fear", "scared", "afraid", "nervous", "worried", "concerned", "uneasy", "uncomfortable",
                "danger", "dangerous", "threat", "threatening", "menacing", "scary", "frightening", "terrifying",
                "horrifying", "shocking", "surprising", "unexpected", "sudden", "abrupt", "quick", "fast", "rapid"
            ],
            ContentType.HORROR: [
                # Horror keywords
                "scary", "terrifying", "frightening", "horrifying", "nightmare", "ghost", "monster", "vampire", "zombie",
                "demon", "devil", "evil", "dark", "shadow", "blood", "death", "kill", "murder", "violence", "terror",
                "panic", "fear", "afraid", "scared", "horrified", "shocked", "surprised", "startled", "jump", "scream"
            ],
            ContentType.SCI_FI: [
                # Sci-fi keywords
                "future", "past", "time", "space", "alien", "robot", "android", "cyborg", "machine", "technology",
                "science", "scientific", "experiment", "lab", "laboratory", "research", "study", "investigation",
                "discovery", "invention", "innovation", "creation", "design", "build", "construct", "create", "make",
                "artificial", "virtual", "digital", "computer", "program", "software", "hardware", "system", "network"
            ],
            ContentType.DOCUMENTARY: [
                # Documentary keywords
                "documentary", "document", "record", "history", "past", "story", "true", "real", "fact", "truth",
                "information", "knowledge", "education", "learn", "study", "research", "investigate", "explore", "discover",
                "understand", "comprehend", "analyze", "examine", "review", "assess", "evaluate", "judge", "decide"
            ],
            ContentType.EDUCATIONAL: [
                # Educational keywords
                "learn", "teach", "education", "school", "college", "university", "study", "research", "knowledge",
                "information", "fact", "truth", "science", "math", "history", "geography", "language", "art", "music",
                "sports", "physical", "health", "biology", "chemistry", "physics", "astronomy", "geology", "psychology"
            ],
            ContentType.SPORTS: [
                # Sports keywords
                "sports", "sport", "game", "match", "competition", "tournament", "championship", "win", "lose", "score",
                "goal", "point", "victory", "defeat", "team", "player", "coach", "training", "practice", "skill", "talent",
                "ability", "strength", "power", "speed", "agility", "endurance", "stamina", "fitness", "condition"
            ],
            ContentType.GAMING: [
                # Gaming keywords
                "game", "gaming", "video game", "console", "controller", "play", "player", "level", "score", "win",
                "lose", "defeat", "victory", "achievement", "unlock", "collect", "build", "create", "design", "develop",
                "code", "program", "software", "app", "application", "mobile", "phone", "tablet", "computer", "PC"
            ],
            ContentType.MUSIC: [
                # Music keywords
                "music", "song", "singer", "band", "guitar", "piano", "drum", "bass", "vocal", "voice", "sing", "play",
                "perform", "performance", "concert", "show", "stage", "audience", "crowd", "fan", "follower", "supporter",
                "melody", "harmony", "rhythm", "beat", "tempo", "pitch", "tone", "sound", "audio", "instrument"
            ],
            ContentType.VLOG: [
                # Vlog keywords
                "vlog", "video blog", "daily", "day", "life", "lifestyle", "personal", "story", "experience", "journey",
                "adventure", "trip", "travel", "visit", "see", "watch", "look", "observe", "notice", "discover", "find",
                "meet", "talk", "speak", "communicate", "share", "tell", "explain", "describe", "show", "demonstrate"
            ],
            ContentType.TUTORIAL: [
                # Tutorial keywords
                "tutorial", "how to", "guide", "instruction", "lesson", "teach", "learn", "education", "study", "research",
                "knowledge", "information", "fact", "truth", "science", "math", "history", "geography", "language", "art",
                "music", "sports", "physical", "health", "biology", "chemistry", "physics", "astronomy", "geology"
            ],
            ContentType.INTERVIEW: [
                # Interview keywords
                "interview", "question", "answer", "ask", "tell", "speak", "talk", "conversation", "discussion", "chat",
                "message", "text", "email", "call", "phone", "video", "live", "stream", "broadcast", "show", "program",
                "host", "guest", "participant", "speaker", "presenter", "moderator", "panel", "discussion", "debate"
            ],
            ContentType.TRAVEL: [
                # Travel keywords
                "travel", "trip", "journey", "adventure", "visit", "see", "watch", "look", "observe", "notice", "discover",
                "find", "explore", "expedition", "tour", "tourist", "vacation", "holiday", "break", "rest", "relax",
                "destination", "location", "place", "city", "country", "world", "globe", "map", "route", "path", "way"
            ],
            ContentType.FOOD: [
                # Food keywords
                "food", "eat", "drink", "cooking", "recipe", "ingredient", "meal", "dish", "restaurant", "chef",
                "taste", "flavor", "smell", "aroma", "delicious", "tasty", "yummy", "good", "great", "amazing", "incredible",
                "wonderful", "fantastic", "awesome", "perfect", "excellent", "superb", "outstanding", "exceptional"
            ],
            ContentType.LIFESTYLE: [
                # Lifestyle keywords
                "lifestyle", "life", "daily", "day", "routine", "habit", "practice", "custom", "tradition", "culture",
                "society", "community", "family", "home", "house", "room", "bedroom", "kitchen", "bathroom", "living room",
                "garden", "yard", "outdoor", "indoor", "inside", "outside", "public", "private", "personal", "individual"
            ]
        }
        
        # Emotional indicators
        self.emotional_indicators = {
            "positive": ["happy", "joy", "love", "like", "good", "great", "amazing", "wonderful", "fantastic", "excellent"],
            "negative": ["sad", "angry", "hate", "bad", "terrible", "awful", "horrible", "disgusting", "annoying", "frustrating"],
            "excited": ["excited", "thrilled", "amazed", "surprised", "shocked", "incredible", "unbelievable", "wow", "amazing"],
            "calm": ["calm", "peaceful", "relaxed", "chill", "easy", "simple", "basic", "normal", "regular", "standard"],
            "intense": ["intense", "dramatic", "serious", "urgent", "critical", "important", "essential", "vital", "crucial"]
        }
        
        # Pacing indicators
        self.pacing_indicators = {
            "fast": ["quick", "fast", "rapid", "speed", "hurry", "rush", "immediate", "instant", "sudden", "abrupt"],
            "slow": ["slow", "gradual", "steady", "calm", "relaxed", "easy", "gentle", "soft", "quiet", "peaceful"],
            "medium": ["normal", "regular", "standard", "average", "typical", "common", "usual", "ordinary", "everyday"]
        }
    
    def analyze_content_type(self, transcript_segments: List[Dict]) -> ContentTypeAnalysis:
        """
        Analyze video content to determine the most likely content type.
        
        Args:
            transcript_segments: List of transcript segments with text
            
        Returns:
            ContentTypeAnalysis with detailed results
        """
        try:
            # Combine all text from segments
            full_text = " ".join([seg.get("text", "") for seg in transcript_segments]).lower()
            
            # Analyze content
            keyword_counts = self._count_content_keywords(full_text)
            emotional_counts = self._count_emotional_indicators(full_text)
            pacing_counts = self._count_pacing_indicators(full_text)
            
            # Calculate genre confidence scores
            genre_scores = self._calculate_genre_scores(keyword_counts, emotional_counts, pacing_counts)
            
            # Get primary and secondary types
            sorted_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)
            primary_type = sorted_genres[0][0] if sorted_genres else ContentType.UNKNOWN
            confidence = sorted_genres[0][1] if sorted_genres else 0.0
            
            # Get top 3 secondary types
            secondary_types = sorted_genres[1:4] if len(sorted_genres) > 1 else []
            
            # Get most relevant keywords
            relevant_keywords = self._get_relevant_keywords(full_text, primary_type)
            
            return ContentTypeAnalysis(
                primary_type=primary_type,
                confidence=confidence,
                secondary_types=secondary_types,
                keywords=relevant_keywords,
                emotional_indicators=emotional_counts,
                pacing_indicators=pacing_counts,
                genre_confidence=genre_scores
            )
            
        except Exception as e:
            logger.error(f"Error in content type analysis: {str(e)}")
            return ContentTypeAnalysis(
                primary_type=ContentType.UNKNOWN,
                confidence=0.0,
                secondary_types=[],
                keywords=[],
                emotional_indicators={},
                pacing_indicators={},
                genre_confidence={}
            )
    
    def _count_content_keywords(self, text: str) -> Dict[ContentType, int]:
        """Count content keywords for each genre type."""
        keyword_counts = {genre: 0 for genre in ContentType}
        
        for genre, keywords in self.content_keywords.items():
            for keyword in keywords:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = re.findall(pattern, text)
                keyword_counts[genre] += len(matches)
        
        return keyword_counts
    
    def _count_emotional_indicators(self, text: str) -> Dict[str, int]:
        """Count emotional indicators in the text."""
        emotional_counts = {emotion: 0 for emotion in self.emotional_indicators.keys()}
        
        for emotion, indicators in self.emotional_indicators.items():
            for indicator in indicators:
                pattern = r'\b' + re.escape(indicator) + r'\b'
                matches = re.findall(pattern, text)
                emotional_counts[emotion] += len(matches)
        
        return emotional_counts
    
    def _count_pacing_indicators(self, text: str) -> Dict[str, int]:
        """Count pacing indicators in the text."""
        pacing_counts = {pacing: 0 for pacing in self.pacing_indicators.keys()}
        
        for pacing, indicators in self.pacing_indicators.items():
            for indicator in indicators:
                pattern = r'\b' + re.escape(indicator) + r'\b'
                matches = re.findall(pattern, text)
                pacing_counts[pacing] += len(matches)
        
        return pacing_counts
    
    def _calculate_genre_scores(self, keyword_counts: Dict[ContentType, int], 
                               emotional_counts: Dict[str, int],
                               pacing_counts: Dict[str, int]) -> Dict[ContentType, float]:
        """Calculate confidence scores for each genre based on various indicators."""
        genre_scores = {}
        
        for genre in ContentType:
            if genre == ContentType.UNKNOWN:
                continue
                
            score = 0.0
            
            # Base score from keyword matches
            keyword_score = keyword_counts.get(genre, 0) * 10
            
            # Emotional context scoring
            if genre in [ContentType.COMEDY, ContentType.MUSIC, ContentType.VLOG]:
                score += emotional_counts.get("positive", 0) * 5
                score += emotional_counts.get("excited", 0) * 3
            elif genre in [ContentType.DRAMA, ContentType.ROMANCE, ContentType.THRILLER]:
                score += emotional_counts.get("intense", 0) * 5
                score += emotional_counts.get("negative", 0) * 3
            elif genre in [ContentType.HORROR, ContentType.THRILLER]:
                score += emotional_counts.get("negative", 0) * 8
                score += emotional_counts.get("intense", 0) * 6
            elif genre in [ContentType.EDUCATIONAL, ContentType.TUTORIAL, ContentType.DOCUMENTARY]:
                score += emotional_counts.get("calm", 0) * 5
                score += emotional_counts.get("positive", 0) * 3
            
            # Pacing context scoring
            if genre in [ContentType.ACTION, ContentType.SPORTS, ContentType.GAMING]:
                score += pacing_counts.get("fast", 0) * 8
                score += pacing_counts.get("excited", 0) * 5
            elif genre in [ContentType.EDUCATIONAL, ContentType.TUTORIAL, ContentType.DOCUMENTARY]:
                score += pacing_counts.get("slow", 0) * 6
                score += pacing_counts.get("calm", 0) * 4
            elif genre in [ContentType.DRAMA, ContentType.ROMANCE, ContentType.THRILLER]:
                score += pacing_counts.get("medium", 0) * 5
                score += pacing_counts.get("intense", 0) * 4
            
            # Add base keyword score
            score += keyword_score
            
            # Normalize score to 0-1 range
            normalized_score = min(score / 100.0, 1.0)
            genre_scores[genre] = normalized_score
        
        return genre_scores
    
    def _get_relevant_keywords(self, text: str, primary_type: ContentType) -> List[str]:
        """Get the most relevant keywords for the primary content type."""
        if primary_type == ContentType.UNKNOWN:
            return []
        
        keywords = self.content_keywords.get(primary_type, [])
        found_keywords = []
        
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text):
                found_keywords.append(keyword)
        
        # Return top 10 most frequent keywords
        return found_keywords[:10] if found_keywords else []
    
    def get_content_type_priority(self, content_type: ContentType) -> float:
        """Get priority score for content type in segment selection."""
        priority_map = {
            ContentType.ACTION: 1.0,
            ContentType.SPORTS: 0.95,
            ContentType.GAMING: 0.9,
            ContentType.COMEDY: 0.85,
            ContentType.MUSIC: 0.8,
            ContentType.THRILLER: 0.8,
            ContentType.DRAMA: 0.75,
            ContentType.ROMANCE: 0.7,
            ContentType.SCI_FI: 0.7,
            ContentType.VLOG: 0.65,
            ContentType.TRAVEL: 0.6,
            ContentType.FOOD: 0.6,
            ContentType.LIFESTYLE: 0.55,
            ContentType.TUTORIAL: 0.5,
            ContentType.EDUCATIONAL: 0.45,
            ContentType.DOCUMENTARY: 0.4,
            ContentType.INTERVIEW: 0.35,
            ContentType.UNKNOWN: 0.2
        }
        return priority_map.get(content_type, 0.5)
    
    def analyze_segment_content_type(self, segment_text: str) -> ContentType:
        """Analyze content type for a single segment."""
        # Create a mock segment for the analyzer
        mock_segments = [{"text": segment_text}]
        analysis = self.analyze_content_type(mock_segments)
        return analysis.primary_type


# Global instance
content_type_analyzer = ContentTypeAnalyzer()