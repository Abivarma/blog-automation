"""
Telegram Notifier - Sends formatted blog draft notifications.
Uses raw requests (no python-telegram-bot dependency needed).
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
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

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

        text = (
            "🚨 *Blog Generator Error*\n\n"
            f"`{error_msg[:500]}`\n\n"
            "Check GitHub Actions logs for details."
        )
        return self._send_message(text)

    def _format_message(self, draft: Dict, topics: Dict) -> str:
        """Format the Telegram notification message."""
        meta = draft.get("metadata", {})
        title = meta.get("title", "Untitled")
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
            backup_text += f"\n  {i}️⃣ {b.title[:60]}"

        # Reading time estimate
        reading_time = max(1, word_count // 200)

        message = (
            f"📰 *AI News Daily Blog \\- Ready for Review*\n\n"
            f"📅 *Date:* {date}\n\n"
            f"🎯 *Title:*\n{self._escape_md(title)}\n\n"
            f"📊 *Stats:*\n"
            f"  • Words: {word_count:,}\n"
            f"  • Reading time: ~{reading_time} min\n"
            f"  • SEO Score: {seo_score}/100\n"
            f"  • Keywords: {self._escape_md(keywords)}\n"
            f"  • Cost: ${cost:.4f}\n\n"
            f"🖼️ *Image:* {image_status}\n\n"
        )

        if backup_text:
            message += f"📝 *Backup Topics:*{backup_text}\n\n"

        message += (
            "💡 *Actions:*\n"
            "To switch topic, trigger workflow\\_dispatch\n"
            "with `topic\\_index` input \\(2\\-5\\) in GitHub Actions\\.\n\n"
            "✅ Review the draft in the repo's `drafts/` folder\\."
        )

        return message

    def _escape_md(self, text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        special_chars = r"_*[]()~`>#+-=|{}.!"
        escaped = ""
        for char in text:
            if char in special_chars:
                escaped += f"\\{char}"
            else:
                escaped += char
        return escaped

    def _send_message(self, text: str) -> bool:
        """Send a message via Telegram Bot API."""
        try:
            resp = requests.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "MarkdownV2",
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Telegram notification sent successfully")
            return True
        except requests.exceptions.HTTPError as e:
            # If MarkdownV2 fails, try plain text
            logger.warning(f"MarkdownV2 failed ({e}), trying plain text")
            return self._send_plain_text(text)
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False

    def _send_plain_text(self, text: str) -> bool:
        """Fallback: send as plain text without formatting."""
        import re
        # Strip markdown formatting
        plain = re.sub(r"\\(.)", r"\1", text)
        plain = re.sub(r"[*_`]", "", plain)

        try:
            resp = requests.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": plain,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Telegram plain text notification sent")
            return True
        except Exception as e:
            logger.error(f"Telegram plain text also failed: {e}")
            return False
