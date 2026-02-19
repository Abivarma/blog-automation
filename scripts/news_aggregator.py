"""
News Aggregator - Fetches and ranks AI news from multiple sources.
Each source is independent; failures are logged and skipped.
"""

import os
import json
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from pathlib import Path

import requests
import feedparser

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    summary: str = ""
    engagement_score: float = 0.0
    published_at: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    raw_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

class TwitterFetcher:
    """Fetch trending AI tweets via Twitter API v2."""

    def __init__(self, config: Dict):
        self.config = config
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")

    def fetch(self) -> List[NewsItem]:
        if not self.bearer_token:
            logger.warning("[Twitter] TWITTER_BEARER_TOKEN not set, skipping")
            return []

        try:
            import tweepy
        except ImportError:
            logger.warning("[Twitter] tweepy not installed, skipping")
            return []

        client = tweepy.Client(bearer_token=self.bearer_token)
        query = " OR ".join(self.config["hashtags"]) + " -is:retweet lang:en"
        max_results = min(self.config.get("max_results", 50), 100)

        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics", "text"],
                sort_order="relevancy",
            )
        except Exception as e:
            logger.error(f"[Twitter] API call failed: {e}")
            return []

        if not response.data:
            logger.info("[Twitter] No tweets found")
            return []

        items: List[NewsItem] = []
        max_engagement = 1.0

        for tweet in response.data:
            metrics = tweet.public_metrics or {}
            eng = (
                metrics.get("retweet_count", 0) * 2
                + metrics.get("like_count", 0)
                + metrics.get("reply_count", 0) * 3
            )
            max_engagement = max(max_engagement, eng)

            items.append(
                NewsItem(
                    title=tweet.text[:120],
                    url=f"https://twitter.com/i/web/status/{tweet.id}",
                    source="twitter",
                    summary=tweet.text,
                    engagement_score=eng,
                    published_at=tweet.created_at.isoformat() if tweet.created_at else None,
                )
            )

        for item in items:
            item.engagement_score /= max_engagement

        logger.info(f"[Twitter] Fetched {len(items)} tweets")
        return items


class HackerNewsFetcher:
    """Fetch top AI stories from Hacker News (no auth required)."""

    def __init__(self, config: Dict):
        self.config = config
        self.base_url = config.get("base_url", "https://hacker-news.firebaseio.com/v0")
        self.keywords = [kw.lower() for kw in config.get("ai_keywords", [])]
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def fetch(self) -> List[NewsItem]:
        try:
            resp = self.session.get(f"{self.base_url}/topstories.json", timeout=10)
            resp.raise_for_status()
            story_ids = resp.json()[: self.config.get("max_stories", 30)]
        except Exception as e:
            logger.error(f"[HackerNews] Failed to fetch top stories: {e}")
            return []

        items: List[NewsItem] = []
        max_score = 1.0

        for story_id in story_ids:
            try:
                resp = self.session.get(f"{self.base_url}/item/{story_id}.json", timeout=10)
                resp.raise_for_status()
                story = resp.json()
            except Exception:
                continue

            if not story or story.get("type") != "story":
                continue

            title = story.get("title", "")
            title_lower = title.lower()

            if not any(kw in title_lower for kw in self.keywords):
                continue

            score = story.get("score", 0)
            max_score = max(max_score, score)

            pub_time = None
            if story.get("time"):
                pub_time = datetime.fromtimestamp(story["time"], tz=timezone.utc).isoformat()

            items.append(
                NewsItem(
                    title=title,
                    url=story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    source="hackernews",
                    summary=title,
                    engagement_score=score,
                    published_at=pub_time,
                    raw_data={"hn_id": story_id, "comments": story.get("descendants", 0)},
                )
            )
            time.sleep(0.2)  # Be nice to HN API

        for item in items:
            item.engagement_score /= max_score

        logger.info(f"[HackerNews] Fetched {len(items)} AI-related stories")
        return items


class RedditFetcher:
    """Fetch top AI posts from Reddit via PRAW."""

    def __init__(self, config: Dict):
        self.config = config

    def fetch(self) -> List[NewsItem]:
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "AINewsBlogBot/1.0")

        if not client_id or not client_secret:
            logger.warning("[Reddit] REDDIT_CLIENT_ID/SECRET not set, skipping")
            return []

        try:
            import praw
        except ImportError:
            logger.warning("[Reddit] praw not installed, skipping")
            return []

        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.error(f"[Reddit] Failed to initialize: {e}")
            return []

        items: List[NewsItem] = []
        max_engagement = 1.0
        limit = self.config.get("limit", 25)
        time_filter = self.config.get("time_filter", "day")

        for sub_name in self.config.get("subreddits", []):
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.top(time_filter=time_filter, limit=limit):
                    eng = post.score + post.num_comments * 2
                    max_engagement = max(max_engagement, eng)

                    items.append(
                        NewsItem(
                            title=post.title,
                            url=f"https://reddit.com{post.permalink}",
                            source="reddit",
                            summary=post.selftext[:300] if post.selftext else post.title,
                            engagement_score=eng,
                            published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
                            raw_data={"subreddit": sub_name, "upvotes": post.score},
                        )
                    )
            except Exception as e:
                logger.error(f"[Reddit] Failed to fetch r/{sub_name}: {e}")
                continue

        for item in items:
            item.engagement_score /= max_engagement

        logger.info(f"[Reddit] Fetched {len(items)} posts")
        return items


class ArxivFetcher:
    """Fetch recent AI papers from ArXiv (no auth required)."""

    def __init__(self, config: Dict):
        self.config = config
        self.base_url = config.get("base_url", "http://export.arxiv.org/api/query")

    def fetch(self) -> List[NewsItem]:
        categories = self.config.get("categories", ["cs.AI", "cs.LG"])
        max_results = self.config.get("max_results", 20)
        cat_query = " OR ".join(f"cat:{cat}" for cat in categories)

        try:
            # ArXiv API requires the query string to be passed directly (not URL-encoded by requests)
            url = f"{self.base_url}?search_query={cat_query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[ArXiv] API call failed: {e}")
            return []

        feed = feedparser.parse(resp.text)
        items: List[NewsItem] = []

        for entry in feed.entries:
            pub_date = entry.get("published", "")
            items.append(
                NewsItem(
                    title=entry.get("title", "").replace("\n", " ").strip(),
                    url=entry.get("link", ""),
                    source="arxiv",
                    summary=entry.get("summary", "").replace("\n", " ").strip()[:500],
                    engagement_score=0.5,  # No engagement metrics for ArXiv
                    published_at=pub_date,
                    keywords=[tag.get("term", "") for tag in entry.get("tags", [])],
                )
            )

        logger.info(f"[ArXiv] Fetched {len(items)} papers")
        return items


class GoogleNewsFetcher:
    """Fetch AI news via NewsAPI (newsapi.org)."""

    def __init__(self, config: Dict):
        self.config = config
        self.api_key = os.getenv("NEWSAPI_KEY")
        self.base_url = config.get("base_url", "https://newsapi.org/v2")

    def fetch(self) -> List[NewsItem]:
        if not self.api_key:
            logger.warning("[GoogleNews] NEWSAPI_KEY not set, skipping")
            return []

        items: List[NewsItem] = []
        queries = self.config.get("queries", ["artificial intelligence"])
        page_size = self.config.get("page_size", 20)

        for query in queries:
            try:
                resp = requests.get(
                    f"{self.base_url}/top-headlines",
                    params={
                        "q": query,
                        "language": "en",
                        "pageSize": page_size,
                        "apiKey": self.api_key,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

                for article in data.get("articles", []):
                    items.append(
                        NewsItem(
                            title=article.get("title", ""),
                            url=article.get("url", ""),
                            source="googlenews",
                            summary=article.get("description", "") or "",
                            engagement_score=0.5,
                            published_at=article.get("publishedAt"),
                            raw_data={"source_name": article.get("source", {}).get("name", "")},
                        )
                    )
            except Exception as e:
                logger.error(f"[GoogleNews] Failed for query '{query}': {e}")
                continue

        logger.info(f"[GoogleNews] Fetched {len(items)} articles")
        return items


# ---------------------------------------------------------------------------
# Topic Ranker
# ---------------------------------------------------------------------------

class TopicRanker:
    """
    Ranks news items using weighted scoring.
    score = 0.4*engagement + 0.2*recency + 0.25*keyword_relevance + 0.15*source_authority
    """

    SOURCE_AUTHORITY: Dict[str, float] = {
        "arxiv": 0.95,
        "hackernews": 0.85,
        "googlenews": 0.75,
        "reddit": 0.70,
        "twitter": 0.65,
    }

    AI_KEYWORDS: List[str] = [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "llm", "gpt", "transformer", "diffusion",
        "reinforcement learning", "computer vision", "nlp",
        "generative ai", "foundation model", "fine-tuning", "rag",
        "large language model", "reasoning", "agent", "multimodal",
        "open source", "benchmark", "training", "inference",
    ]

    WEIGHTS = {
        "engagement": 0.4,
        "recency": 0.2,
        "keyword_relevance": 0.25,
        "source_authority": 0.15,
    }

    def rank(self, items: List[NewsItem]) -> List[NewsItem]:
        if not items:
            return []

        for item in items:
            item.engagement_score = self._compute_score(item)

        # Deduplicate by similar titles
        items = self._deduplicate(items)

        items.sort(key=lambda x: x.engagement_score, reverse=True)
        return items

    def _compute_score(self, item: NewsItem) -> float:
        engagement = item.engagement_score  # Already normalized 0-1

        recency = self._recency_score(item.published_at)

        text = f"{item.title} {item.summary}".lower()
        keyword_hits = sum(1 for kw in self.AI_KEYWORDS if kw in text)
        keyword_relevance = min(keyword_hits / 5.0, 1.0)

        authority = self.SOURCE_AUTHORITY.get(item.source, 0.5)

        score = (
            self.WEIGHTS["engagement"] * engagement
            + self.WEIGHTS["recency"] * recency
            + self.WEIGHTS["keyword_relevance"] * keyword_relevance
            + self.WEIGHTS["source_authority"] * authority
        )
        return round(score, 4)

    def _recency_score(self, published_at: Optional[str]) -> float:
        if not published_at:
            return 0.5  # Unknown = neutral

        try:
            pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            hours_ago = (now - pub_dt).total_seconds() / 3600
            return max(0.0, 1.0 - hours_ago / 48.0)
        except (ValueError, TypeError):
            return 0.5

    def _deduplicate(self, items: List[NewsItem]) -> List[NewsItem]:
        """Remove items with very similar titles."""
        seen_titles: List[str] = []
        unique: List[NewsItem] = []

        for item in items:
            title_words = set(item.title.lower().split())
            is_dup = False
            for seen in seen_titles:
                seen_words = set(seen.split())
                if len(title_words & seen_words) / max(len(title_words | seen_words), 1) > 0.6:
                    is_dup = True
                    break
            if not is_dup:
                seen_titles.append(item.title.lower())
                unique.append(item)

        if len(items) != len(unique):
            logger.info(f"[Ranker] Deduplicated {len(items)} → {len(unique)} items")

        return unique


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class NewsAggregator:
    """Orchestrates fetching from all sources and ranking."""

    FETCHER_MAP = {
        "twitter": TwitterFetcher,
        "hackernews": HackerNewsFetcher,
        "reddit": RedditFetcher,
        "arxiv": ArxivFetcher,
        "googlenews": GoogleNewsFetcher,
    }

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(CONFIG_DIR / "sources.json")

        with open(config_path) as f:
            self.config = json.load(f)

        self.fetchers: Dict[str, object] = {}
        for name, fetcher_cls in self.FETCHER_MAP.items():
            source_config = self.config.get(name, {})
            if source_config.get("enabled", False):
                self.fetchers[name] = fetcher_cls(source_config)
            else:
                logger.info(f"[{name}] Disabled in config, skipping")

        self.ranker = TopicRanker()

    def fetch_all(self) -> List[NewsItem]:
        """Fetch from all enabled sources. Each source fails independently."""
        all_items: List[NewsItem] = []

        for name, fetcher in self.fetchers.items():
            try:
                items = fetcher.fetch()
                logger.info(f"[{name}] Fetched {len(items)} items")
                all_items.extend(items)
            except Exception as e:
                logger.error(f"[{name}] Failed: {e}")
                continue

        logger.info(f"Total items fetched: {len(all_items)}")
        return all_items

    def get_ranked_topics(self, top_n: int = 5) -> Dict:
        """Returns primary topic + backup topics."""
        items = self.fetch_all()
        ranked = self.ranker.rank(items)

        result = {
            "primary": ranked[0] if ranked else None,
            "backups": ranked[1:top_n] if len(ranked) > 1 else [],
            "all_ranked": ranked[:top_n],
            "total_fetched": len(items),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if result["primary"]:
            logger.info(
                f"Primary topic: {result['primary'].title} "
                f"(score: {result['primary'].engagement_score})"
            )

        return result
