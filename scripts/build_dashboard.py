"""
Dashboard Builder - Generates static data files for GitHub Pages dashboard.
Scans drafts and logs to build JSON data consumed by the frontend.
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
DRAFTS_DIR = ROOT_DIR / "drafts"
LOGS_DIR = ROOT_DIR / "logs"
DOCS_DIR = ROOT_DIR / "docs"
DATA_DIR = DOCS_DIR / "data"
POSTS_DIR = DATA_DIR / "posts"
WORKFLOWS_DIR = ROOT_DIR / ".github" / "workflows"


class DashboardBuilder:
    """Build static dashboard data from drafts and logs."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        POSTS_DIR.mkdir(parents=True, exist_ok=True)

    def build(self):
        """Run the full dashboard build."""
        posts = self._scan_drafts()
        stats = self._compute_stats(posts)
        config = self._get_config()

        # Write data files
        self._write_json(DATA_DIR / "posts.json", posts)
        self._write_json(DATA_DIR / "stats.json", stats)
        self._write_json(DATA_DIR / "config.json", config)

        logger.info(f"Dashboard built: {len(posts)} posts indexed")

    def _scan_drafts(self) -> List[Dict]:
        """Scan drafts directory and extract metadata."""
        posts = []

        if not DRAFTS_DIR.is_dir():
            return posts

        for filepath in sorted(DRAFTS_DIR.glob("*.md"), reverse=True):
            if filepath.name == ".gitkeep":
                continue

            content = filepath.read_text(encoding="utf-8")
            metadata = self._parse_front_matter(content)
            body = self._strip_front_matter(content)

            # Extract date from filename
            parts = filepath.stem.split("-")
            date_str = "-".join(parts[:3]) if len(parts) >= 3 else ""

            post = {
                "filename": filepath.name,
                "date": metadata.get("date", date_str),
                "title": metadata.get("title", filepath.stem),
                "slug": metadata.get("slug", filepath.stem),
                "word_count": int(metadata.get("word_count", len(body.split()))),
                "seo_score": int(metadata.get("seo_score", 0)),
                "status": metadata.get("status", "draft"),
                "keywords": metadata.get("keywords", []),
                "meta_description": metadata.get("meta_description", ""),
            }
            posts.append(post)

            # Copy markdown body to posts dir for client-side rendering
            post_file = POSTS_DIR / filepath.name
            post_file.write_text(body, encoding="utf-8")

        return posts

    def _parse_front_matter(self, content: str) -> Dict:
        """Parse YAML-like front matter from markdown."""
        metadata = {}
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return metadata

        for line in match.group(1).split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("-"):
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                # Handle lists (simple single-level)
                if key in metadata and isinstance(metadata[key], list):
                    continue
                metadata[key] = value
            elif line.startswith("- ") and metadata:
                # Append to last key as list
                last_key = list(metadata.keys())[-1]
                if not isinstance(metadata[last_key], list):
                    metadata[last_key] = []
                metadata[last_key].append(line[2:].strip())

        return metadata

    def _strip_front_matter(self, content: str) -> str:
        """Remove YAML front matter from content."""
        return re.sub(r"^---\n.*?\n---\n*", "", content, count=1, flags=re.DOTALL)

    def _compute_stats(self, posts: List[Dict]) -> Dict:
        """Compute aggregate statistics."""
        if not posts:
            return {
                "total_posts": 0,
                "avg_word_count": 0,
                "avg_seo_score": 0,
                "last_generated": None,
                "posts_this_week": 0,
                "posts_this_month": 0,
            }

        now = datetime.now()
        week_ago = now.strftime("%Y-%m-%d")  # Simplified
        word_counts = [p["word_count"] for p in posts]
        seo_scores = [p["seo_score"] for p in posts if p["seo_score"] > 0]

        return {
            "total_posts": len(posts),
            "avg_word_count": round(sum(word_counts) / len(word_counts)) if word_counts else 0,
            "avg_seo_score": round(sum(seo_scores) / len(seo_scores)) if seo_scores else 0,
            "last_generated": posts[0]["date"] if posts else None,
            "posts_this_week": sum(1 for p in posts if p["date"] >= (now.strftime("%Y-%m-%d"))),
            "posts_this_month": sum(
                1 for p in posts if p["date"][:7] == now.strftime("%Y-%m")
            ),
            "updated_at": now.isoformat(),
        }

    def _get_config(self) -> Dict:
        """Get current pipeline configuration."""
        config = {
            "schedule": "0 6 * * *",
            "sources": {},
            "repo": "Abivarma/blog-automation",
        }

        # Read cron from workflow
        workflow_path = WORKFLOWS_DIR / "daily-blog-generator.yml"
        if workflow_path.exists():
            content = workflow_path.read_text()
            cron_match = re.search(r"cron:\s*'([^']+)'", content)
            if cron_match:
                config["schedule"] = cron_match.group(1)

        # Read source config
        sources_path = ROOT_DIR / "config" / "sources.json"
        if sources_path.exists():
            with open(sources_path) as f:
                sources = json.load(f)
                config["sources"] = {
                    name: {"enabled": src.get("enabled", False)}
                    for name, src in sources.items()
                }

        return config

    def _write_json(self, path: Path, data) -> None:
        """Write JSON data to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    builder = DashboardBuilder()
    builder.build()
