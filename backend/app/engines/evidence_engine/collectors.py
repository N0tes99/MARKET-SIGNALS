"""Evidence collectors wired to analysis engines."""

from app.engines.buyer_seller_engine import BuyerSellerEngine
from app.engines.correlation_engine import CorrelationEngine
from app.engines.derivatives_engine import DerivativesEngine
from app.engines.event_engine import EventEngine
from app.engines.evidence_engine.protocol import EvidenceContributor
from app.engines.evidence_engine.types import EvidenceItem
from app.engines.macro_engine import MacroEngine
from app.engines.onchain_engine import OnChainEngine
from app.engines.risk_engine import RiskEngine
from app.engines.sector_rs_engine import SectorRSEngine
from app.engines.sentiment_engine import SentimentEngine
from app.engines.trend_engine import TrendEngine
from app.engines.volatility_engine import VolatilityEngine
from app.market_data.service import MarketDataService


class TrendEvidenceCollector:
    """Collects trend and structure evidence from the Trend Engine."""

    def __init__(self, engine: TrendEngine | None = None) -> None:
        self._engine = engine or TrendEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return trend and structure evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class BuyerSellerEvidenceCollector:
    """Collects momentum and volume evidence."""

    def __init__(self, engine: BuyerSellerEngine | None = None) -> None:
        self._engine = engine or BuyerSellerEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return momentum and volume evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class DerivativesEvidenceCollector:
    """Collects derivatives market evidence."""

    def __init__(self, engine: DerivativesEngine | None = None) -> None:
        self._engine = engine or DerivativesEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return derivatives evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class MacroEvidenceCollector:
    """Collects macroeconomic context evidence."""

    def __init__(self, engine: MacroEngine | None = None) -> None:
        self._engine = engine or MacroEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return macro evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class RiskEvidenceCollector:
    """Collects risk assessment evidence."""

    def __init__(self, engine: RiskEngine | None = None) -> None:
        self._engine = engine or RiskEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return risk evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class CorrelationEvidenceCollector:
    """Collects cross-asset correlation evidence."""

    def __init__(self, engine: CorrelationEngine | None = None) -> None:
        self._engine = engine or CorrelationEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return correlation evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class VolatilityEvidenceCollector:
    """Collects VIX volatility regime evidence."""

    def __init__(self, engine: VolatilityEngine | None = None) -> None:
        self._engine = engine or VolatilityEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return volatility evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class EventEvidenceCollector:
    """Collects event calendar / catalyst timing evidence."""

    def __init__(self, engine: EventEngine | None = None) -> None:
        self._engine = engine or EventEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return event calendar evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class SectorRSEvidenceCollector:
    """Collects sector / benchmark relative-strength evidence."""

    def __init__(self, engine: SectorRSEngine | None = None) -> None:
        self._engine = engine or SectorRSEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return relative-strength evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class OnChainEvidenceCollector:
    """Collects on-chain / activity evidence."""

    def __init__(self, engine: OnChainEngine | None = None) -> None:
        self._engine = engine or OnChainEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return on-chain evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


class SentimentEvidenceCollector:
    """Collects Fear & Greed sentiment evidence."""

    def __init__(self, engine: SentimentEngine | None = None) -> None:
        self._engine = engine or SentimentEngine()

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return sentiment evidence."""
        return self._engine.contribute_evidence(symbol, timeframe)


def build_collectors(market_data: MarketDataService | None = None) -> list[EvidenceContributor]:
    """Build evidence collectors sharing a market data service."""
    md = market_data or MarketDataService()
    return [
        TrendEvidenceCollector(TrendEngine(md)),
        BuyerSellerEvidenceCollector(BuyerSellerEngine(md)),
        DerivativesEvidenceCollector(DerivativesEngine(md)),
        MacroEvidenceCollector(MacroEngine()),
        RiskEvidenceCollector(RiskEngine(md)),
        CorrelationEvidenceCollector(CorrelationEngine(md)),
        VolatilityEvidenceCollector(VolatilityEngine(md)),
        EventEvidenceCollector(EventEngine()),
        SectorRSEvidenceCollector(SectorRSEngine(md)),
        OnChainEvidenceCollector(OnChainEngine()),
        SentimentEvidenceCollector(SentimentEngine()),
    ]


DEFAULT_COLLECTORS: list[EvidenceContributor] = build_collectors()
