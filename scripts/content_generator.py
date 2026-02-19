"""
Content Generator - Generates SEO-optimized blog posts using OpenAI GPT-4.
"""

import os
import json
import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


class ContentGenerator:
    """Generates blog content through a multi-step pipeline."""

    def __init__(self, config_dir: Optional[str] = None):
        config_path = Path(config_dir) if config_dir else CONFIG_DIR

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        with open(config_path / "prompts.json") as f:
            self.prompts = json.load(f)

        with open(config_path / "seo_config.json") as f:
            self.seo_config = json.load(f)

        self.total_tokens_used = 0
        self.total_cost = 0.0

    def generate_blog(self, topics: Dict) -> Tuple[str, Dict]:
        """
        Full pipeline: topic synthesis -> title -> blog -> metadata.

        Returns:
            Tuple of (blog_content_markdown, metadata_dict)
        """
        primary = topics["primary"]
        backups = topics.get("backups", [])

        # Step 1: Synthesize a focused topic from the news items
        logger.info("Step 1: Synthesizing topic...")
        topic_brief = self._synthesize_topic(primary, backups[:2])

        # Step 2: Generate title
        logger.info("Step 2: Generating title...")
        title = self._generate_title(topic_brief)

        # Step 3: Generate the full blog post
        logger.info("Step 3: Generating blog content...")
        blog_content = self._generate_blog_content(title, topic_brief, primary)

        # Step 4: Validate word count and expand if needed
        word_count = len(blog_content.split())
        min_words = self.seo_config["target_word_count"]["min"]
        if word_count < min_words:
            logger.info(f"Word count {word_count} < {min_words}, expanding...")
            blog_content = self._expand_content(blog_content, min_words)

        # Step 5: Generate meta description
        logger.info("Step 4: Generating meta description...")
        meta_desc = self._generate_meta_description(title, topic_brief)

        # Build metadata
        metadata = {
            "title": title,
            "keywords": topic_brief.get("target_keywords", []),
            "meta_description": meta_desc,
            "topic_angle": topic_brief.get("angle", ""),
            "sources_used": [primary.source] + [b.source for b in backups[:2]],
            "model_used": self.model,
            "tokens_used": self.total_tokens_used,
            "estimated_cost_usd": round(self.total_cost, 4),
        }

        logger.info(f"Content generation complete. Tokens: {self.total_tokens_used}, Cost: ${self.total_cost:.4f}")
        return blog_content, metadata

    def _synthesize_topic(self, primary, related: list) -> Dict:
        """Synthesize a focused blog topic from news items."""
        news_text = f"Primary: {primary.title}\n{primary.summary}\n\n"
        for item in related:
            news_text += f"Related: {item.title}\n{item.summary}\n\n"

        prompt = self.prompts["topic_summary"].replace("{topics}", news_text)
        response_text = self._call_openai(prompt, max_tokens=500, temperature=0.6)

        try:
            return json.loads(self._extract_json(response_text))
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse topic synthesis, using fallback")
            return {
                "topic_title": primary.title,
                "angle": "Comprehensive analysis of this trending topic",
                "target_keywords": primary.title.lower().split()[:5],
                "key_points": [primary.title, primary.summary[:200]],
                "why_trending": "This topic is gaining significant attention in the AI community.",
            }

    def _generate_title(self, topic_brief: Dict) -> str:
        """Generate an SEO-optimized title."""
        topic = topic_brief.get("topic_title", "AI Technology")
        keyword = topic_brief.get("target_keywords", ["AI"])[0]

        prompt = self.prompts["title_generation"].replace("{topic}", topic).replace("{keyword}", keyword)
        response_text = self._call_openai(prompt, max_tokens=300, temperature=0.8)

        try:
            titles = json.loads(self._extract_json(response_text))
            if isinstance(titles, list) and titles:
                # Pick the title closest to ideal length (50-65 chars)
                best = min(titles, key=lambda t: abs(len(t) - 57))
                return best
        except (json.JSONDecodeError, ValueError):
            pass

        return topic_brief.get("topic_title", "Understanding the Latest AI Breakthrough")

    def _generate_blog_content(self, title: str, topic_brief: Dict, primary) -> str:
        """Generate the full blog post."""
        keyword = topic_brief.get("target_keywords", ["AI"])[0]
        angle = topic_brief.get("angle", "")

        source_summaries = f"Title: {primary.title}\nSummary: {primary.summary}\nSource: {primary.source}\n"
        if primary.url:
            source_summaries += f"URL: {primary.url}\n"

        key_points = topic_brief.get("key_points", [])
        if key_points:
            source_summaries += "\nKey points to cover:\n"
            for point in key_points:
                source_summaries += f"- {point}\n"

        prompt = (
            self.prompts["blog_generation"]
            .replace("{topic_title}", title)
            .replace("{angle}", angle)
            .replace("{keyword}", keyword)
            .replace("{source_summaries}", source_summaries)
        )

        return self._call_openai(prompt, max_tokens=16000, temperature=0.7)

    def _expand_content(self, content: str, target_words: int) -> str:
        """Expand content iteratively until target word count is reached."""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            current_words = len(content.split())
            words_needed = target_words - current_words
            if words_needed <= 0:
                break

            logger.info(f"Expansion attempt {attempt}/{max_attempts}: need {words_needed} more words")

            prompt = (
                f"You are expanding an existing blog post. The current version has {current_words} words "
                f"but the target is {target_words} words minimum.\n\n"
                f"CRITICAL: You MUST write at least {target_words} words total. This is non-negotiable.\n\n"
                f"Expand the following sections significantly:\n"
                f"- Technical Deep Dive: Add 2-3 more detailed subsections with code examples\n"
                f"- Practical Applications: Add 3 detailed real-world use cases with specific examples\n"
                f"- Background & Context: Add more historical context and industry evolution\n"
                f"- Challenges: Add more specific technical limitations and edge cases\n\n"
                f"Return the COMPLETE expanded blog post in Markdown format. "
                f"Do NOT summarize or shorten any existing sections.\n\n"
                f"---CURRENT POST---\n{content}\n---END POST---"
            )
            expanded = self._call_openai(prompt, max_tokens=16000, temperature=0.7)
            if len(expanded.split()) > current_words:
                content = expanded
            else:
                logger.warning(f"Expansion attempt {attempt} did not increase word count")
                break

        return content

    def _generate_meta_description(self, title: str, topic_brief: Dict) -> str:
        """Generate SEO meta description."""
        topic = topic_brief.get("topic_title", title)
        keyword = topic_brief.get("target_keywords", ["AI"])[0]

        prompt = (
            self.prompts["meta_description"]
            .replace("{title}", title)
            .replace("{topic}", topic)
            .replace("{keyword}", keyword)
        )

        desc = self._call_openai(prompt, max_tokens=100, temperature=0.6)
        # Ensure proper length
        desc = desc.strip().strip('"').strip("'")
        if len(desc) > 160:
            desc = desc[:157] + "..."
        return desc

    def _call_openai(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.7) -> str:
        """Make an OpenAI API call with cost tracking."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Track usage
        usage = response.usage
        if usage:
            self.total_tokens_used += usage.total_tokens
            # Approximate cost (GPT-4 pricing)
            input_cost = usage.prompt_tokens * 0.03 / 1000
            output_cost = usage.completion_tokens * 0.06 / 1000
            self.total_cost += input_cost + output_cost

        return response.choices[0].message.content or ""

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that might have markdown formatting."""
        # Try to find JSON block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            return json_match.group(1).strip()

        # Try to find raw JSON (object or array)
        for pattern in [r"(\{[\s\S]*\})", r"(\[[\s\S]*\])"]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return text.strip()
