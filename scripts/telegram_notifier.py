"""
Telegram Notifier - Sends formatted blog draft notifications.
Uses raw requests with HTML parse mode (more reliable than MarkdownV2).
"""

import os
import logging
from typing import Dict

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send one-way Telegram notifications for blog drafts."""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id_str = os.getenv("TELEGRAM_CHAT_ID", "")
        self.chat_id = int(chat_id_str) if chat_id_str.strip() else None

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_draft_notification(self, draft: Dict, topics: Dict) -> bool:
        """Send a formatted notification about the generated draft."""
        if not self.is_configured:
            logger.warning("Telegram credentials not set, skipping notification")
            return False

        message = self._format_message(draft, topics)
        return self._send_message(message)

    def send_error_notification(self, error_msg: str) -> bool:
        """Send error alert via Telegram."""
        if not self.is_configured:
            logger.warning("Telegram credentials not set, skipping error notification")
            return False

        # Keep error messages plain text to avoid formatting issues
        text = f"🚨 Blog Generator Error\n\n{error_msg[:500]}\n\nCheck GitHub Actions logs for details."
        return self._send_message(text, use_html=False)

    def _format_message(self, draft: Dict, topics: Dict) -> str:
        """Format the Telegram notification message using HTML."""
        meta = draft.get("metadata", {})
        title = self._escape_html(meta.get("title", "Untitled"))
        word_count = meta.get("word_count", 0)
        seo_score = meta.get("seo_score", 0)
        keywords = ", ".join(meta.get("keywords", [])[:5])
        date = meta.get("date", "today")
        cost = meta.get("estimated_cost_usd", 0)

        # Image status
        image_info = meta.get("hero_image", {})
        image_type = image_info.get("type", "none")
        if image_type == "unsplash":
            image_status = "✅ Unsplash image found"
        elif image_type == "dalle_prompt":
            image_status = "📝 DALL-E prompt generated"
        else:
            image_status = "⚠️ No image"

        # Backup topics
        backups = topics.get("backups", [])
        backup_text = ""
        for i, b in enumerate(backups[:4], 2):
            backup_text += f"\n  {i}. {self._escape_html(b.title[:60])}"

        # Reading time estimate
        reading_time = max(1, word_count // 200)

        message = (
            f"📰 <b>AI News Daily Blog - Ready for Review</b>\n\n"
            f"📅 <b>Date:</b> {date}\n\n"
            f"🎯 <b>Title:</b>\n{title}\n\n"
            f"📊 <b>Stats:</b>\n"
            f"  • Words: {word_count:,}\n"
            f"  • Reading time: ~{reading_time} min\n"
            f"  • SEO Score: {seo_score}/100\n"
            f"  • Keywords: {self._escape_html(keywords)}\n"
            f"  • Cost: ${cost:.4f}\n\n"
            f"🖼️ <b>Image:</b> {image_status}\n\n"
        )

        if backup_text:
            message += f"📝 <b>Backup Topics:</b>{backup_text}\n\n"

        message += (
            "💡 <b>Actions:</b>\n"
            "To switch topic, trigger workflow_dispatch\n"
            "with topic_index input (2-5) in GitHub Actions.\n\n"
            "✅ Review the draft in the repo's drafts/ folder."
        )

        return message

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters for Telegram."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _send_message(self, text: str, use_html: bool = True) -> bool:
        """Send a message via Telegram Bot API."""
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        }
        if use_html:
            payload["parse_mode"] = "HTML"

        try:
            resp = requests.post(
                f"{self._base_url}/sendMessage",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Telegram notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            # Last resort: try plain text
            if use_html:
                return self._send_message(text, use_html=False)
            return False
