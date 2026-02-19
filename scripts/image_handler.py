"""
Image Handler - Sources hero images or generates DALL-E prompts.
Strategy: Try Unsplash first, fall back to prompt generation.
"""

import os
import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class ImageHandler:
    """Handle hero image sourcing or prompt generation."""

    def __init__(self):
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")

    def get_hero_image(self, topic: str, keywords: List[str]) -> Dict:
        """
        Try to source a hero image. Returns dict with:
        - type: "unsplash" | "dalle_prompt"
        - url: image URL (if unsplash)
        - prompt: DALL-E prompt (if dalle_prompt)
        - attribution: credit text
        """
        if self.unsplash_key:
            try:
                result = self._fetch_unsplash(topic, keywords)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Unsplash failed: {e}")

        return self._generate_dalle_prompt(topic, keywords)

    def _fetch_unsplash(self, topic: str, keywords: List[str]) -> Dict | None:
        """Search Unsplash for a relevant image."""
        query = f"{topic} technology"
        if keywords:
            query = f"{keywords[0]} technology AI"

        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query": query,
                "per_page": 3,
                "orientation": "landscape",
            },
            headers={"Authorization": f"Client-ID {self.unsplash_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            logger.info("No Unsplash results found")
            return None

        img = results[0]
        result = {
            "type": "unsplash",
            "url": img["urls"]["regular"],
            "download_url": img["urls"]["full"],
            "attribution": f"Photo by {img['user']['name']} on Unsplash",
            "prompt": None,
        }
        logger.info(f"Unsplash image found: {result['attribution']}")
        return result

    def _generate_dalle_prompt(self, topic: str, keywords: List[str]) -> Dict:
        """Generate a DALL-E / Midjourney prompt for the topic."""
        kw_text = ", ".join(keywords[:3]) if keywords else "AI, technology"

        prompt = (
            f"A photorealistic wide-angle hero image for a technology blog post about {topic}. "
            f"Keywords: {kw_text}. "
            "Style: Modern, clean, professional with subtle blue and purple gradient tones. "
            "The image should convey innovation and technology without being cliché. "
            "No text overlay, no watermarks. "
            "Composition: Rule of thirds, shallow depth of field on key element. "
            "Lighting: Soft, diffused studio lighting with tech-inspired ambient glow. "
            "Aspect ratio: 16:9, high resolution, publication-ready."
        )

        logger.info("Generated DALL-E image prompt")
        return {
            "type": "dalle_prompt",
            "url": None,
            "download_url": None,
            "attribution": "AI-generated image prompt (manual generation required)",
            "prompt": prompt,
        }
