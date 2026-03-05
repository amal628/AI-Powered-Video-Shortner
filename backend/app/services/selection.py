from typing import List, Dict, Any, Tuple
from math import isfinite
import re


class SelectiveSegmentSelector:
    """
    Optimized segment selector that focuses on hook / engaging segments
    with strict type safety and Pylance-clean numeric handling.
    """

    def __init__(self) -> None:
        self.phase_keywords: Dict[str, Tuple[str, ...]] = {
            "opening": (
                "welcome", "hello", "in this video", "today we",
                "let's begin", "start", "first",
            ),
            "hook": (
                "wait", "watch this", "you won't believe",
                "secret", "did you know", "here's why", "stop",
            ),
            "emotion": (
                "feel", "emotional", "heart", "cry", "love",
                "pain", "happy", "sad", "hope", "fear",
            ),
            "action": (
                "fight", "run", "chase", "attack",
                "battle", "explosion", "jump", "race", "escape",
            ),
            "dialogue": (
                "he said", "she said", "i said",
                "told me", "listen", "truth is",
                "important", "because",
            ),
            "climax": (
                "finally", "in the end", "this is it",
                "moment of truth", "final",
                "revealed", "ultimate",
            ),
        }

        self.strong_words = {
            "important", "must", "key", "secret",
            "best", "why", "how", "critical",
            "never", "always", "amazing",
            "final", "conclusion",
        }

        self.min_segment_seconds: float = 2.0
        self.ideal_segment_seconds: float = 8.0
        self.merge_gap_seconds: float = 0.6

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def _safe_float(self, value: Any) -> float:
        try:
            num = float(value)
            if isfinite(num):
                return num
        except Exception:
            pass
        return 0.0

    def _video_duration(self, duration: Any) -> float:
        return max(0.0, self._safe_float(duration))

    # ------------------------------------------------------------------ #
    # Normalization
    # ------------------------------------------------------------------ #

    def normalize_scored_segments(
        self,
        raw_segments: List[Any],
        video_duration: Any
    ) -> List[Dict[str, Any]]:

        max_end: float = self._video_duration(video_duration)
        scored: List[Dict[str, Any]] = []

        for raw in raw_segments:
            start = self._safe_float(
                raw.get("start") if isinstance(raw, dict) else getattr(raw, "start", 0)
            )
            end = self._safe_float(
                raw.get("end") if isinstance(raw, dict) else getattr(raw, "end", 0)
            )

            if max_end > 0:
                start = max(0.0, min(start, max_end))
                end = max(0.0, min(end, max_end))

            duration = end - start
            if duration < 0.05:
                continue

            text = ""
            if isinstance(raw, dict):
                text = str(raw.get("text", "") or "")
            elif hasattr(raw, "text"):
                text = str(getattr(raw, "text", "") or "")

            text_lower = text.lower()
            words = re.findall(r"\w+", text_lower)
            word_count = len(words)

            wps = word_count / duration if duration > 0 else 0.0
            keyword_hits = sum(1 for w in words if w in self.strong_words)

            punctuation_boost = 1.0 if ("?" in text or "!" in text) else 0.0

            duration_fit = max(
                0.0,
                1.0 - abs(duration - self.ideal_segment_seconds) / self.ideal_segment_seconds
            )

            position_ratio = start / max_end if max_end > 0 else 0.0

            def phase_score(phase: str) -> float:
                return float(
                    sum(1 for kw in self.phase_keywords[phase] if kw in text_lower)
                )

            opening_score = phase_score("opening") + (1.5 if position_ratio <= 0.25 else 0.0)
            hook_score = phase_score("hook") + (1.0 if position_ratio <= 0.40 else 0.0)
            emotion_score = phase_score("emotion")
            action_score = phase_score("action")
            dialogue_score = phase_score("dialogue") + min(word_count / 14.0, 2.5)
            climax_score = phase_score("climax") + (1.5 if position_ratio >= 0.60 else 0.0)

            score = (
                1.8 * duration_fit
                + 0.8 * min(wps, 3.0)
                + 0.25 * min(word_count / 12.0, 2.0)
                + 0.6 * min(keyword_hits, 3)
                + punctuation_boost
                + 0.55 * max(
                    opening_score,
                    hook_score,
                    emotion_score,
                    action_score,
                    dialogue_score,
                    climax_score,
                )
            )

            scored.append({
                "start": start,
                "end": end,
                "duration": duration,
                "text": text,
                "score": score,
                "position_ratio": position_ratio,
                "opening_score": opening_score,
                "hook_score": hook_score,
                "emotion_score": emotion_score,
                "action_score": action_score,
                "dialogue_score": dialogue_score,
                "climax_score": climax_score,
            })

        scored.sort(key=lambda s: (s["start"], s["end"]))
        return scored

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def build_runtime_segments(
        self,
        raw_segments: List[Any],
        video_duration: Any,
        target_duration: int,
    ) -> List[Tuple[float, float]]:

        max_end: float = self._video_duration(video_duration)
        target: float = float(max(0, target_duration))

        scored = self.normalize_scored_segments(raw_segments, max_end)
        if not scored:
            return []

        selected: List[Tuple[float, float]] = []
        consumed = 0.0

        scored.sort(key=lambda s: s["score"], reverse=True)

        for seg in scored:
            if consumed >= target:
                break

            start = seg["start"]
            end = seg["end"]
            seg_len = end - start

            if seg_len < self.min_segment_seconds:
                continue

            # Check for overlap with existing segments
            if self._has_overlap_with_selected(selected, start, end):
                continue

            use_len = min(seg_len, target - consumed)
            if use_len <= 0:
                continue

            selected.append((start, start + use_len))
            consumed += use_len

        return self._trim_segments_to_target(selected, target)

    # ------------------------------------------------------------------ #

    def _has_overlap_with_selected(
        self,
        selected_segments: List[Tuple[float, float]],
        new_start: float,
        new_end: float,
        overlap_threshold: float = 0.1
    ) -> bool:
        """
        Check if a new segment overlaps with any existing selected segments.
        
        Args:
            selected_segments: List of existing (start, end) tuples
            new_start: Start time of new segment
            new_end: End time of new segment
            overlap_threshold: Minimum overlap ratio to consider as overlap (default 10%)
        
        Returns:
            True if there's significant overlap, False otherwise
        """
        new_duration = new_end - new_start
        if new_duration <= 0:
            return False
            
        for existing_start, existing_end in selected_segments:
            existing_duration = existing_end - existing_start
            if existing_duration <= 0:
                continue
                
            # Calculate overlap
            overlap_start = max(new_start, existing_start)
            overlap_end = min(new_end, existing_end)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            if overlap_duration <= 0:
                continue
                
            # Calculate overlap ratios
            new_overlap_ratio = overlap_duration / new_duration
            existing_overlap_ratio = overlap_duration / existing_duration
            
            # Consider it an overlap if either segment has significant overlap
            if new_overlap_ratio >= overlap_threshold or existing_overlap_ratio >= overlap_threshold:
                return True
                
        return False

    def _trim_segments_to_target(
        self,
        segments: List[Tuple[float, float]],
        target: float
    ) -> List[Tuple[float, float]]:

        result: List[Tuple[float, float]] = []
        consumed = 0.0

        for start, end in sorted(segments, key=lambda t: t[0]):
            if consumed >= target:
                break

            seg_len = end - start
            remaining = target - consumed

            use_len = min(seg_len, remaining)
            if use_len <= 0:
                continue

            result.append((start, start + use_len))
            consumed += use_len

        return result


# Global instance
selective_segment_selector = SelectiveSegmentSelector()