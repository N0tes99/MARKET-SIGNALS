"""Per-ticker Reddit buzz scorer — confirmation / conflict only."""

from __future__ import annotations

from dataclasses import dataclass

from app.market_data.providers.reddit_public import RedditBuzzSnapshot, get_reddit_buzz
from app.utils.scoring_helpers import clamp_score

_BULLISH = (
    "moon",
    "rally",
    "breakout",
    "bullish",
    "calls",
    "long",
    "accumulate",
    "undervalued",
    "buy the dip",
    "btfd",
    "to the moon",
    "bull run",
    "squeeze",
)
_BEARISH = (
    "crash",
    "dump",
    "bearish",
    "puts",
    "short",
    "overvalued",
    "rug",
    "scam",
    "bubble",
    "selloff",
    "sell-off",
    "bagholder",
    "rekt",
)


@dataclass(frozen=True)
class RedditSocialResult:
    score: float
    description: str
    mention_count: int
    engagement: int
    lean: float  # -1 bearish … +1 bullish
    available: bool


def _keyword_lean(text: str) -> tuple[int, int]:
    lower = text.lower()
    bull = sum(1 for w in _BULLISH if w in lower)
    bear = sum(1 for w in _BEARISH if w in lower)
    return bull, bear


def score_reddit_buzz(snap: RedditBuzzSnapshot) -> RedditSocialResult:
    """Map buzz volume + keyword lean to a confirmation-style 0–100 score.

    Quiet → near 50. Elevated fear/panic can be mildly supportive (contrarian).
    Crowded hype leans cautious (conflict with chasey longs).
    """
    if not snap.posts:
        return RedditSocialResult(
            score=50.0,
            description="Reddit: quiet / unavailable — neutral confirmation",
            mention_count=0,
            engagement=0,
            lean=0.0,
            available=False,
        )

    bull_hits = 0
    bear_hits = 0
    engagement = 0
    for post in snap.posts:
        text = f"{post.title} {post.selftext}"
        b, r = _keyword_lean(text)
        bull_hits += b
        bear_hits += r
        engagement += max(0, post.score) + max(0, post.num_comments)

    mentions = len(snap.posts)
    total_kw = bull_hits + bear_hits
    lean = 0.0
    if total_kw > 0:
        lean = (bull_hits - bear_hits) / total_kw

    # Volume intensity (soft): 0 quiet → 1 hot
    volume = min(1.0, mentions / 12.0) * 0.55 + min(1.0, engagement / 800.0) * 0.45

    # Contrarian: strong bullish lean + high volume → caution; panic → mild support
    if volume < 0.15:
        score = 50.0
        label = "quiet"
    elif lean >= 0.35 and volume >= 0.55:
        score = 38.0 - min(8.0, volume * 6.0)
        label = "crowded bullish chatter — caution"
    elif lean <= -0.35 and volume >= 0.45:
        score = 58.0 + min(8.0, volume * 6.0)
        label = "fearful chatter — contrarian support"
    elif lean >= 0.2:
        score = 46.0 - volume * 4.0
        label = "elevated bullish chatter"
    elif lean <= -0.2:
        score = 54.0 + volume * 4.0
        label = "elevated bearish chatter"
    else:
        score = 50.0 + (lean * 4.0)
        label = "mixed chatter"

    score = clamp_score(score)
    desc = (
        f"Reddit: {label} ({mentions} posts, eng {engagement}, lean {lean:+.2f})"
    )
    return RedditSocialResult(
        score=score,
        description=desc,
        mention_count=mentions,
        engagement=engagement,
        lean=lean,
        available=True,
    )


def analyze_reddit_social(symbol: str, *, allow_live: bool = False) -> RedditSocialResult:
    """Score Reddit buzz for a symbol (cache-first; live only when allowed)."""
    snap = get_reddit_buzz(symbol, allow_live=allow_live)
    return score_reddit_buzz(snap)


    # Remove unused regex helper leftover
