"""Risk Engine — position sizing and risk assessment evidence."""

from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceItem
from app.indicators.atr import calculate_atr
from app.market_data.service import MarketDataService
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score


@dataclass
class RiskAssessment:
    """Risk parameters for a potential trade."""

    symbol: str
    position_size: float
    stop_loss: float
    take_profit: float
    max_drawdown: float
    risk_percent: float
    risk_reward_ratio: float
    score: float
    description: str


class RiskEngine:
    """Calculates risk parameters and risk-category evidence."""

    def __init__(
        self,
        market_data: MarketDataService | None = None,
        default_risk_percent: float = 1.0,
    ) -> None:
        """Initialize with optional market data service."""
        self._market_data = market_data or MarketDataService()
        self._default_risk_percent = default_risk_percent

    def assess(
        self,
        symbol: str,
        account_balance: float = 10_000.0,
        timeframe: str = "1h",
    ) -> RiskAssessment | None:
        """Calculate risk parameters for a trade on the given asset."""
        df = self._market_data.safe_get_ohlcv(symbol, timeframe)
        if df is None:
            return None

        price = float(df["close"].iloc[-1])
        atr = float(calculate_atr(df["high"], df["low"], df["close"]).iloc[-1])
        stop_loss = price - (2 * atr)
        take_profit = price + (3 * atr)
        risk_per_unit = price - stop_loss
        reward_per_unit = take_profit - price
        risk_reward = reward_per_unit / risk_per_unit if risk_per_unit > 0 else 0.0

        risk_amount = account_balance * (self._default_risk_percent / 100)
        position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0

        score = clamp_score(min(risk_reward / 3 * 100, 100)) if risk_reward > 0 else 0.0
        description = (
            f"{symbol}: Stop {stop_loss:.2f}, target {take_profit:.2f}, "
            f"R:R {risk_reward:.1f}:1, ATR {atr:.2f}"
        )

        return RiskAssessment(
            symbol=symbol.upper(),
            position_size=round(position_size, 6),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            max_drawdown=round(risk_amount, 2),
            risk_percent=self._default_risk_percent,
            risk_reward_ratio=round(risk_reward, 2),
            score=score,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return risk-category evidence item."""
        result = self.assess(symbol, timeframe=timeframe)
        if result is None:
            return [
                EvidenceItem(
                    source="risk_engine",
                    category=ScoringCategory.RISK.value,
                    score=0.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.RISK],
                    description=f"{symbol}: Risk assessment unavailable",
                ),
            ]

        return [
            EvidenceItem(
                source="risk_engine",
                category=ScoringCategory.RISK.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.RISK],
                description=result.description,
            ),
        ]
