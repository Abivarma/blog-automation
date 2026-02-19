"""
SEO Analyzer - Analyzes blog content for SEO quality metrics.
Uses pure Python for readability scoring (no heavy external dependencies).
"""

import re
import json
import logging
import math
from typing import Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


class SEOAnalyzer:
    """Analyze blog content for SEO optimization."""

    def __init__(self, config_path: str | None = None):
        cfg_file = Path(config_path) if config_path else CONFIG_DIR / "seo_config.json"
        with open(cfg_file) as f:
            self.config = json.load(f)

    def analyze(self, content: str, keywords: List[str]) -> Dict:
        """Run full SEO analysis and return a report with overall score."""
        word_count_score = self._score_word_count(content)
        readability_score = self._score_readability(content)
        keyword_score = self._score_keywords(content, keywords)
        structure_score = self._score_structure(content)
        meta_score = self._score_meta_quality(content)
        depth_score = self._score_content_depth(content)

        weights = self.config["scoring_weights"]
        overall = (
            weights["word_count"] * word_count_score
            + weights["readability"] * readability_score
            + weights["keyword_density"] * keyword_score
            + weights["structure"] * structure_score
            + weights["meta_quality"] * meta_score
            + weights["content_depth"] * depth_score
        )

        report = {
            "overall_score": round(overall),
            "word_count": len(content.split()),
            "word_count_score": round(word_count_score),
            "readability_score": round(readability_score),
            "keyword_score": round(keyword_score),
            "structure_score": round(structure_score),
            "meta_score": round(meta_score),
            "depth_score": round(depth_score),
            "flesch_reading_ease": self._flesch_reading_ease(content),
            "flesch_kincaid_grade": self._flesch_kincaid_grade(content),
        }

        logger.info(f"SEO Analysis: {json.dumps(report, indent=2)}")
        return report

    # ------------------------------------------------------------------
    # Scoring methods (each returns 0-100)
    # ------------------------------------------------------------------

    def _score_word_count(self, content: str) -> float:
        word_count = len(content.split())
        cfg = self.config["target_word_count"]
        if cfg["min"] <= word_count <= cfg["max"]:
            return 100.0
        if word_count < cfg["min"]:
            return max(0, 100 * word_count / cfg["min"])
        # Over max is slightly penalized but not terrible
        return max(70, 100 - (word_count - cfg["max"]) / 10)

    def _score_readability(self, content: str) -> float:
        fre = self._flesch_reading_ease(content)
        cfg = self.config["readability"]
        if cfg["flesch_reading_ease_min"] <= fre <= cfg["flesch_reading_ease_max"]:
            return 100.0
        if fre < cfg["flesch_reading_ease_min"]:
            diff = cfg["flesch_reading_ease_min"] - fre
            return max(0, 100 - diff * 2)
        diff = fre - cfg["flesch_reading_ease_max"]
        return max(50, 100 - diff * 1.5)

    def _score_keywords(self, content: str, keywords: List[str]) -> float:
        if not keywords:
            return 50.0  # Neutral if no keywords provided

        content_lower = content.lower()
        word_count = len(content.split())
        cfg = self.config["keyword_density"]

        scores = []
        for kw in keywords[:3]:  # Check top 3 keywords
            count = content_lower.count(kw.lower())
            density = (count / max(word_count, 1)) * 100
            if cfg["min"] <= density <= cfg["max"]:
                scores.append(100.0)
            elif density < cfg["min"]:
                scores.append(max(0, density / cfg["min"] * 100))
            else:
                scores.append(max(30, 100 - (density - cfg["max"]) * 20))

        return sum(scores) / len(scores) if scores else 50.0

    def _score_structure(self, content: str) -> float:
        cfg = self.config["structure"]
        h2_count = len(re.findall(r"^## ", content, re.MULTILINE))
        h3_count = len(re.findall(r"^### ", content, re.MULTILINE))
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        list_items = len(re.findall(r"^[\s]*[-*] ", content, re.MULTILINE))

        score = 0.0
        # H2 headings
        if h2_count >= cfg["min_h2_headings"]:
            score += 30
        else:
            score += 30 * h2_count / cfg["min_h2_headings"]

        # H3 headings
        if h3_count >= cfg["min_h3_headings"]:
            score += 25
        else:
            score += 25 * h3_count / cfg["min_h3_headings"]

        # Paragraphs
        if len(paragraphs) >= cfg["min_paragraphs"]:
            score += 25
        else:
            score += 25 * len(paragraphs) / cfg["min_paragraphs"]

        # Lists
        if list_items >= cfg["min_list_items"]:
            score += 20
        else:
            score += 20 * list_items / cfg["min_list_items"]

        return min(100, score)

    def _score_meta_quality(self, content: str) -> float:
        """Score based on presence of key meta elements in content."""
        score = 0.0

        # Has a clear H1 title
        if re.search(r"^# ", content, re.MULTILINE):
            score += 25

        # Has bold/emphasis for key terms
        if len(re.findall(r"\*\*[^*]+\*\*", content)) >= 3:
            score += 25

        # Has links
        if len(re.findall(r"\[.+?\]\(.+?\)", content)) >= 1:
            score += 25

        # Has a conclusion or takeaways section
        if re.search(r"(?i)(conclusion|takeaway|summary|tl;dr)", content):
            score += 25

        return score

    def _score_content_depth(self, content: str) -> float:
        """Score based on content depth indicators."""
        score = 0.0
        word_count = len(content.split())

        # Code blocks
        code_blocks = len(re.findall(r"```", content)) // 2
        if code_blocks >= 1:
            score += 20

        # Numbered lists
        if re.search(r"^\d+\.", content, re.MULTILINE):
            score += 20

        # Questions / rhetorical elements
        question_count = content.count("?")
        if question_count >= 3:
            score += 20

        # Statistics / numbers in content
        numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", content)
        if len(numbers) >= 5:
            score += 20

        # Variety of sections
        sections = len(re.findall(r"^#{1,3} ", content, re.MULTILINE))
        if sections >= 8:
            score += 20

        return min(100, score)

    # ------------------------------------------------------------------
    # Readability metrics (pure Python implementation)
    # ------------------------------------------------------------------

    def _count_syllables(self, word: str) -> int:
        """Estimate syllable count for a word."""
        word = word.lower().strip(".,!?;:\"'()-")
        if not word:
            return 0
        if len(word) <= 3:
            return 1

        vowels = "aeiouy"
        count = 0
        prev_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel

        # Adjust for silent e
        if word.endswith("e") and count > 1:
            count -= 1
        # Adjust for -le ending
        if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
            count += 1

        return max(1, count)

    def _get_text_stats(self, content: str) -> Dict:
        """Get basic text statistics."""
        # Strip markdown formatting
        text = re.sub(r"```[\s\S]*?```", "", content)  # Remove code blocks
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # Remove headers
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # Remove links
        text = re.sub(r"[*_~`]", "", text)  # Remove formatting

        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        words = text.split()
        words = [w.strip(".,!?;:\"'()-") for w in words if w.strip(".,!?;:\"'()-")]

        total_syllables = sum(self._count_syllables(w) for w in words)

        return {
            "total_sentences": max(1, len(sentences)),
            "total_words": max(1, len(words)),
            "total_syllables": total_syllables,
        }

    def _flesch_reading_ease(self, content: str) -> float:
        """Calculate Flesch Reading Ease score (0-100, higher = easier)."""
        stats = self._get_text_stats(content)
        score = (
            206.835
            - 1.015 * (stats["total_words"] / stats["total_sentences"])
            - 84.6 * (stats["total_syllables"] / stats["total_words"])
        )
        return round(max(0, min(100, score)), 1)

    def _flesch_kincaid_grade(self, content: str) -> float:
        """Calculate Flesch-Kincaid Grade Level."""
        stats = self._get_text_stats(content)
        grade = (
            0.39 * (stats["total_words"] / stats["total_sentences"])
            + 11.8 * (stats["total_syllables"] / stats["total_words"])
            - 15.59
        )
        return round(max(0, grade), 1)
