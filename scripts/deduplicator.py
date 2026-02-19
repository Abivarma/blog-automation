"""
Topic Deduplicator - Prevents repeat topics by tracking recent drafts.
"""

import os
import logging
from typing import List, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TopicDeduplicator:
    """Prevent the same topic from being generated on consecutive days."""

    def __init__(self, drafts_dir: str = "drafts", lookback_days: int = 7):
        self.drafts_dir = drafts_dir
        self.lookback_days = lookback_days

    def get_recent_topics(self) -> Set[str]:
        """Extract keywords from recent draft filenames."""
        recent_keywords: Set[str] = set()
        cutoff = datetime.now() - timedelta(days=self.lookback_days)

        if not os.path.isdir(self.drafts_dir):
            return recent_keywords

        for filename in os.listdir(self.drafts_dir):
            if not filename.endswith(".md") or filename == ".gitkeep":
                continue

            # Parse date from filename: 2026-02-19-slug.md
            parts = filename.split("-")
            if len(parts) < 4:
                continue

            try:
                date_str = "-".join(parts[:3])
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date >= cutoff:
                    # Extract keywords from slug portion
                    slug = "-".join(parts[3:]).replace(".md", "")
                    words = slug.split("-")
                    # Filter out short/common words
                    recent_keywords.update(
                        w for w in words if len(w) > 3
                    )
            except (ValueError, IndexError):
                continue

        if recent_keywords:
            logger.info(f"Recent topic keywords ({self.lookback_days}d): {recent_keywords}")

        return recent_keywords

    def filter_topics(self, topics: List, recent_keywords: Set[str]) -> List:
        """Penalize topics that overlap heavily with recent drafts."""
        if not recent_keywords:
            return topics

        for topic in topics:
            title_words = set(topic.title.lower().split())
            # Normalize
            title_words = {w.strip(".,!?;:'\"()-") for w in title_words if len(w) > 3}
            overlap = title_words & recent_keywords

            if len(overlap) > 2:
                old_score = topic.engagement_score
                topic.engagement_score *= 0.3  # Heavy penalty
                logger.info(
                    f"Dedup penalty: '{topic.title}' "
                    f"(overlap: {overlap}, score: {old_score:.3f} → {topic.engagement_score:.3f})"
                )

        return topics
