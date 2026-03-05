import numpy as np
from typing import List, Dict


class HighlightDetector:

    STRONG_KEYWORDS = [
        "secret", "mistake", "biggest", "truth", "shocking",
        "important", "never", "always", "why", "how",
        "crazy", "insane", "amazing", "warning"
    ]

    def __init__(self):
        pass

    # ------------------------------------------------
    # Segment Scoring (Energy Detection)
    # ------------------------------------------------

    def _score_segment(self, segment: Dict) -> float:
        text = segment["text"].lower()
        duration = segment["end"] - segment["start"]

        score = 0.0

        # Keyword boost
        for keyword in self.STRONG_KEYWORDS:
            if keyword in text:
                score += 2

        # Question boost
        if "?" in text:
            score += 3

        # Speech speed
        words = len(text.split())
        if duration > 0:
            wps = words / duration
            score += min(wps, 3)

        # Ideal segment length bonus
        if 8 <= duration <= 40:
            score += 2

        return score

    # ------------------------------------------------
    # Dynamic Merge Gap Calculation
    # ------------------------------------------------

    def _calculate_dynamic_gap(self, segments: List[Dict]) -> float:

        durations = []
        word_speeds = []
        scores = []

        for s in segments:
            duration = s["end"] - s["start"]
            durations.append(duration)

            words = len(s["text"].split())
            if duration > 0:
                word_speeds.append(words / duration)

            scores.append(self._score_segment(s))

        avg_duration = np.mean(durations)
        avg_speed = np.mean(word_speeds) if word_speeds else 1
        avg_score = np.mean(scores)

        # AI logic

        # Fast speech → smaller gap
        if avg_speed > 2.5:
            gap = 1.5

        # Emotional / energetic → tighter merge
        elif avg_score > 6:
            gap = 2

        # Slow storytelling → allow larger merge
        elif avg_speed < 1.2:
            gap = 5

        else:
            gap = 3

        return gap

    # ------------------------------------------------
    # Hook & Climax Aware Merge
    # ------------------------------------------------

    def merge_segments(
        self,
        segments: List[Dict],
        target_duration: int = 30,
        top_k: int = 1
    ) -> List[Dict]:

        if not segments:
            return []

        dynamic_gap = self._calculate_dynamic_gap(segments)

        # Score segments
        for s in segments:
            s["score"] = self._score_segment(s)

        segments_sorted = sorted(
            segments,
            key=lambda x: x["score"],
            reverse=True
        )

        highlights = []

        for base_segment in segments_sorted[:top_k]:

            start = base_segment["start"]
            end = base_segment["end"]
            merged_segments = [base_segment]

            for s in segments:

                if s["start"] > end:
                    gap = s["start"] - end

                    if gap <= dynamic_gap:

                        # Momentum check (climax detection)
                        if s["score"] >= base_segment["score"] * 0.6:

                            new_duration = s["end"] - start

                            if new_duration <= target_duration:
                                merged_segments.append(s)
                                end = s["end"]
                            else:
                                break

            highlights.append({
                "start": start,
                "end": end,
                "duration": end - start,
                "segments": merged_segments,
                "dynamic_gap_used": dynamic_gap
            })

        return highlights


highlight_detector = HighlightDetector()