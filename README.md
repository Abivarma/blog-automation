# AI News Blog Automation

Automated daily AI news blog generator powered by GitHub Actions. Discovers trending AI topics, generates SEO-optimized 3,500+ word blog posts via GPT-4, and notifies you via Telegram for review.

## Architecture

```
6 AM UTC (cron) ──► GitHub Actions
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    News Sources    Content Gen    Notifications
    ├─ Twitter      ├─ GPT-4       ├─ Telegram
    ├─ HackerNews   ├─ SEO         └─ Dashboard
    ├─ Reddit       └─ Images
    ├─ ArXiv
    └─ NewsAPI
          │
          ▼
    GitHub Repo (drafts/) ──► GitHub Pages Dashboard
```

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Abivarma/blog-automation.git
cd blog-automation
uv sync
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Service | Where to get it | Required? |
|---------|----------------|-----------|
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Yes |
| **Telegram** | Message [@BotFather](https://t.me/BotFather) on Telegram | Yes |
| **Twitter** | [developer.twitter.com](https://developer.twitter.com) | No |
| **Reddit** | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) | No |
| **NewsAPI** | [newsapi.org](https://newsapi.org) | No |
| **Unsplash** | [unsplash.com/developers](https://unsplash.com/developers) | No |

**Minimum setup**: Only OpenAI + Telegram are required. HackerNews and ArXiv work without any API keys.

#### Telegram Bot Setup

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, follow instructions, copy the bot token
3. Send a message to your new bot
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` to find your `chat_id`
5. Add both to your `.env` file

### 3. Add GitHub Secrets

Go to your repo **Settings > Secrets and variables > Actions** and add:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- Any other API keys you have

### 4. Test Locally

```bash
# Dry run (no GPT-4 calls, no cost)
uv run python scripts/main.py --dry-run

# Full run (generates a blog post)
uv run python scripts/main.py
```

### 5. Enable GitHub Pages

1. Go to repo **Settings > Pages**
2. Set Source to **GitHub Actions**
3. Dashboard will be available at `https://abivarma.github.io/blog-automation/`

## Usage

### Daily Automation

The pipeline runs automatically at **6 AM UTC** via GitHub Actions. After each run:

1. Blog draft is saved to `drafts/`
2. Telegram notification is sent with stats
3. Dashboard is updated at GitHub Pages

### Manual Trigger

Go to **Actions > Daily AI Blog Generator > Run workflow**:

- Leave inputs empty for a normal run
- Set `topic_index` (1-4) to use a backup topic
- Check `dry_run` to test without GPT-4 calls

### Dashboard

The GitHub Pages dashboard lets you:

- **View** all generated drafts with SEO scores
- **Read** full posts rendered from Markdown
- **Copy** markdown to clipboard for Medium/LinkedIn
- **Trigger** workflows (generate, switch topic, cleanup)
- **Change** the cron schedule
- **Toggle** news sources on/off

To use dashboard actions, save a GitHub PAT (with `repo` + `workflow` scopes) in the Settings page.

### CLI Options

```bash
# Normal run
uv run python scripts/main.py

# Use backup topic #2
uv run python scripts/main.py --topic-index 2

# Dry run (aggregation only)
uv run python scripts/main.py --dry-run
```

## Project Structure

```
├── .github/workflows/
│   ├── daily-blog-generator.yml    # Daily cron at 6 AM UTC
│   ├── weekly-cleanup.yml          # Monday 7 AM UTC cleanup
│   └── deploy-pages.yml            # GitHub Pages deployment
├── scripts/
│   ├── main.py                     # Pipeline orchestrator
│   ├── news_aggregator.py          # 5-source news fetcher + ranker
│   ├── content_generator.py        # GPT-4 blog generation
│   ├── seo_analyzer.py             # SEO scoring & validation
│   ├── image_handler.py            # Unsplash / DALL-E prompts
│   ├── telegram_notifier.py        # Telegram notifications
│   ├── git_handler.py              # CI git operations
│   ├── build_dashboard.py          # Static dashboard data builder
│   ├── retry_utils.py              # Exponential backoff decorator
│   └── deduplicator.py             # Prevent repeat topics
├── config/
│   ├── sources.json                # News source configuration
│   ├── prompts.json                # GPT-4 prompt templates
│   └── seo_config.json             # SEO thresholds & weights
├── docs/                           # GitHub Pages dashboard
│   ├── index.html                  # Dashboard home
│   ├── archive.html                # Post archive
│   ├── post.html                   # Post reader
│   ├── settings.html               # Settings & actions
│   ├── css/style.css
│   └── js/{app,actions}.js
├── drafts/                         # Generated blog posts
├── logs/                           # Execution logs
├── .env.example                    # Environment variable template
└── pyproject.toml                  # Project config (uv)
```

## News Sources

| Source | Auth Required | What it fetches |
|--------|:---:|---|
| HackerNews | No | Top stories filtered for AI keywords |
| ArXiv | No | Recent papers in cs.AI, cs.LG, cs.CL, cs.SE |
| Twitter | Yes | Tweets with #AI, #MachineLearning, etc. |
| Reddit | Yes | Top posts from r/MachineLearning, r/LocalLLaMA, etc. |
| NewsAPI | Yes | Headlines about AI/ML from news outlets |

Each source can be toggled independently in `config/sources.json`. The pipeline continues with whatever sources are available.

## Cost

- **OpenAI GPT-4**: ~$0.05-0.15 per blog post
- **Everything else**: Free (GitHub Actions, HN, ArXiv, Telegram)
- **Estimated monthly**: ~$3-5 for daily generation

## Troubleshooting

**Pipeline fails with "No topics found"**
- Check that at least HackerNews is reachable (no API key needed)
- Run `--dry-run` to test aggregation

**Blog is under 3,500 words**
- The generator auto-expands short content
- Try switching to `gpt-4-turbo` via `OPENAI_MODEL` env var

**Telegram notification not received**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Make sure you've messaged your bot at least once

**Dashboard shows no data**
- Run `uv run python scripts/build_dashboard.py` after generating a post
- Check that `docs/data/posts.json` exists
