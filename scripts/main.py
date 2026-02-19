#!/usr/bin/env python3
"""
AI News Blog Generator - Main Orchestrator

Runs the full pipeline:
  1. Aggregate news from multiple sources
  2. Rank and select top topic
  3. Generate SEO-optimized blog post
  4. Handle hero image (source or prompt)
  5. Save draft to drafts/
  6. Commit to git (CI only)
  7. Send Telegram notification
  8. Build dashboard data
"""

import os
import sys
import json
import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env for local development
load_dotenv()

# Project root
ROOT_DIR = Path(__file__).parent.parent
DRAFTS_DIR = ROOT_DIR / "drafts"
LOGS_DIR = ROOT_DIR / "logs"

# Ensure directories exist
DRAFTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Configure logging
log_filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / log_filename),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")

# Add scripts dir to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from news_aggregator import NewsAggregator
from content_generator import ContentGenerator
from seo_analyzer import SEOAnalyzer
from image_handler import ImageHandler
from telegram_notifier import TelegramNotifier
from git_handler import GitHandler
from deduplicator import TopicDeduplicator


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].rstrip("-")


def save_draft(content: str, metadata: dict, date_str: str) -> Path:
    """Save blog draft as markdown with YAML front matter."""
    slug = metadata.get("slug", "untitled")
    draft_path = DRAFTS_DIR / f"{date_str}-{slug}.md"

    # Build YAML front matter
    front_matter = "---\n"
    for key, value in metadata.items():
        if isinstance(value, list):
            front_matter += f"{key}:\n"
            for item in value:
                front_matter += f"  - {item}\n"
        else:
            front_matter += f"{key}: {json.dumps(value) if isinstance(value, (dict, bool)) else value}\n"
    front_matter += "---\n\n"

    draft_path.write_text(front_matter + content, encoding="utf-8")
    logger.info(f"Draft saved: {draft_path}")
    return draft_path


def save_backup_topics(topics: dict, date_str: str) -> Path:
    """Save backup topics as JSON."""
    backup_path = DRAFTS_DIR / f"{date_str}-backup-topics.json"
    backup_data = {
        "date": date_str,
        "primary": topics["primary"].to_dict() if topics["primary"] else None,
        "backups": [t.to_dict() for t in topics.get("backups", [])],
        "total_fetched": topics.get("total_fetched", 0),
        "timestamp": topics.get("timestamp", ""),
    }
    backup_path.write_text(json.dumps(backup_data, indent=2), encoding="utf-8")
    logger.info(f"Backup topics saved: {backup_path}")
    return backup_path


def main(topic_index: int | None = None, dry_run: bool = False):
    """
    Main pipeline.

    Args:
        topic_index: If provided (1-indexed), use that backup topic instead of primary.
        dry_run: If True, run aggregation only (skip GPT-4 + git + notifications).
    """
    start_time = time.time()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notifier = TelegramNotifier()

    try:
        logger.info("=" * 60)
        logger.info("AI News Blog Generator - Pipeline Started")
        logger.info(f"Date: {date_str} | Dry run: {dry_run}")
        logger.info("=" * 60)

        # Phase 1: Aggregate news
        logger.info("\n--- Phase 1: News Aggregation ---")
        aggregator = NewsAggregator()
        topics = aggregator.get_ranked_topics(top_n=5)

        if not topics["primary"]:
            msg = "No topics found from any source. Aborting."
            logger.error(msg)
            notifier.send_error_notification(msg)
            return 1

        # Apply deduplication against recent drafts
        dedup = TopicDeduplicator(str(DRAFTS_DIR))
        recent_keywords = dedup.get_recent_topics()
        if recent_keywords:
            all_items = topics["all_ranked"]
            dedup.filter_topics(all_items, recent_keywords)
            all_items.sort(key=lambda x: x.engagement_score, reverse=True)
            topics["primary"] = all_items[0]
            topics["backups"] = all_items[1:5]

        # Handle topic switching
        if topic_index is not None and 1 <= topic_index <= len(topics.get("backups", [])):
            topics["primary"] = topics["backups"][topic_index - 1]
            logger.info(f"Switched to backup topic #{topic_index}: {topics['primary'].title}")

        logger.info(f"Primary topic: {topics['primary'].title}")
        logger.info(f"Score: {topics['primary'].engagement_score}")
        logger.info(f"Total items fetched: {topics['total_fetched']}")

        # Save backup topics
        save_backup_topics(topics, date_str)

        if dry_run:
            logger.info("\n--- DRY RUN: Skipping content generation ---")
            for i, topic in enumerate(topics.get("all_ranked", [])[:5], 1):
                logger.info(f"  #{i}: {topic.title} (score: {topic.engagement_score}, source: {topic.source})")
            elapsed = time.time() - start_time
            logger.info(f"\nDry run completed in {elapsed:.1f}s")
            return 0

        # Phase 2: Generate blog content
        logger.info("\n--- Phase 2: Content Generation ---")
        generator = ContentGenerator()
        blog_content, metadata = generator.generate_blog(topics)

        word_count = len(blog_content.split())
        logger.info(f"Blog generated: {word_count} words")

        # Phase 3: SEO Analysis
        logger.info("\n--- Phase 3: SEO Analysis ---")
        analyzer = SEOAnalyzer()
        seo_report = analyzer.analyze(blog_content, metadata.get("keywords", []))
        metadata["seo_score"] = seo_report.get("overall_score", 0)
        metadata["word_count"] = word_count
        logger.info(f"SEO Score: {metadata['seo_score']}/100")

        # Phase 4: Image handling
        logger.info("\n--- Phase 4: Image Processing ---")
        image_handler = ImageHandler()
        image_info = image_handler.get_hero_image(
            metadata.get("title", ""),
            metadata.get("keywords", []),
        )
        metadata["hero_image"] = image_info

        # Save image prompt if generated
        if image_info.get("type") == "dalle_prompt":
            prompt_path = DRAFTS_DIR / f"{date_str}-{metadata.get('slug', 'post')}-image-prompt.txt"
            prompt_path.write_text(image_info["prompt"], encoding="utf-8")
            logger.info(f"Image prompt saved: {prompt_path}")

        # Phase 5: Save draft
        logger.info("\n--- Phase 5: Saving Draft ---")
        metadata["slug"] = slugify(metadata.get("title", "untitled"))
        metadata["date"] = date_str
        metadata["status"] = "draft"
        draft_path = save_draft(blog_content, metadata, date_str)

        # Phase 6: Git commit (CI only)
        logger.info("\n--- Phase 6: Git Operations ---")
        git_handler = GitHandler()
        log_path = str(LOGS_DIR / log_filename)
        git_handler.commit_draft(str(draft_path), log_path)

        # Phase 7: Telegram notification
        logger.info("\n--- Phase 7: Telegram Notification ---")
        notifier.send_draft_notification(
            {"metadata": metadata, "content": blog_content},
            topics,
        )

        # Phase 8: Build dashboard data
        logger.info("\n--- Phase 8: Dashboard Data ---")
        try:
            from build_dashboard import DashboardBuilder
            builder = DashboardBuilder()
            builder.build()
            logger.info("Dashboard data updated")
        except Exception as e:
            logger.warning(f"Dashboard build skipped: {e}")

        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Pipeline completed successfully in {elapsed:.1f}s")
        logger.info(f"Draft: {draft_path}")
        logger.info(f"Word count: {word_count}")
        logger.info(f"SEO score: {metadata['seo_score']}/100")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        try:
            notifier.send_error_notification(str(e))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI News Blog Generator")
    parser.add_argument(
        "--topic-index",
        type=int,
        default=None,
        help="Use backup topic N instead of primary (1-indexed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run aggregation only, skip GPT-4 calls and git",
    )
    args = parser.parse_args()

    exit_code = main(topic_index=args.topic_index, dry_run=args.dry_run)
    sys.exit(exit_code)
