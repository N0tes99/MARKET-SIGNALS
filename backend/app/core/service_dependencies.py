"""FastAPI dependency providers for services."""

from functools import lru_cache

from app.backtesting import BacktestRunner
from app.engines.evidence_engine import EvidenceEngine
from app.engines.learning_engine import LearningEngine
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.scoring.optimizer import WeightOptimizer
from app.services.decision_pipeline import DecisionPipelineService
from app.services.evidence_service import EvidenceService


@lru_cache
def get_market_data_service() -> MarketDataService:
    """Return a singleton market data service (Binance → Kraken fallback)."""
    return MarketDataService()


def get_evidence_engine() -> EvidenceEngine:
    """Return an Evidence Engine wired to the default market data service."""
    md = get_market_data_service()
    return EvidenceEngine(market_data=md)


def get_evidence_service() -> EvidenceService:
    """Return an Evidence Service wired to the default engine."""
    return EvidenceService(engine=get_evidence_engine())


@lru_cache
def get_decision_pipeline() -> DecisionPipelineService:
    """Return the full decision pipeline with live market data."""
    md = get_market_data_service()
    return DecisionPipelineService(
        market_data=md,
        learning_engine=get_learning_engine(),
    )


def get_test_market_data_service() -> MarketDataService:
    """Return market data service with mock provider for tests."""
    return MarketDataService(provider=MockMarketDataProvider())


def get_test_evidence_service() -> EvidenceService:
    """Return an Evidence Service with mock market data for tests."""
    md = get_test_market_data_service()
    engine = EvidenceEngine(market_data=md)
    return EvidenceService(engine=engine)


def get_test_decision_pipeline() -> DecisionPipelineService:
    """Return decision pipeline with mock market data for tests."""
    md = get_test_market_data_service()
    return DecisionPipelineService(
        market_data=md,
        learning_engine=get_test_learning_engine(),
    )


def get_ai_analyst():
    """Return an AI Analyst instance."""
    from app.engines.ai_engine import AIAnalyst

    return AIAnalyst()


@lru_cache
def get_learning_engine() -> LearningEngine:
    """Singleton learning engine (Postgres when available, else memory)."""
    from app.engines.learning_engine.factory import build_signal_store

    return LearningEngine(store=build_signal_store())


@lru_cache
def get_backtest_runner() -> BacktestRunner:
    """Singleton backtest runner sharing market data cache."""
    return BacktestRunner(market_data=get_market_data_service())


def get_test_learning_engine() -> LearningEngine:
    """Fresh learning engine for tests (always in-memory)."""
    from app.engines.learning_engine.store import InMemorySignalStore

    return LearningEngine(store=InMemorySignalStore())


def get_test_backtest_runner() -> BacktestRunner:
    """Backtest runner with mock market data for tests."""
    return BacktestRunner(market_data=get_test_market_data_service())


@lru_cache
def get_alert_service():
    """Singleton alert dispatcher."""
    from app.services.alert_service import AlertService

    return AlertService()


@lru_cache
def get_setup_scanner():
    """Singleton setup scanner (opportunity ideas — separate from ranking)."""
    from app.engines.opportunity_engine.scanner import SetupScanner

    return SetupScanner(market_data=get_market_data_service())


@lru_cache
def get_equity_options_scanner():
    """Singleton Layer 3 equity-options scanner."""
    from app.engines.opportunity_engine.equity_options.scanner import EquityOptionsScanner

    return EquityOptionsScanner(market_data=get_market_data_service())


@lru_cache
def get_runner_scanner():
    """Singleton Surface 4 Runner Detection scanner."""
    from app.engines.runner_engine import RunnerScanner

    return RunnerScanner(market_data=get_market_data_service())


@lru_cache
def get_options_tape_scanner():
    """Singleton aggressive options tape scanner."""
    from app.engines.options_tape import OptionsTapeScanner

    return OptionsTapeScanner(market_data=get_market_data_service())


@lru_cache
def get_paper_agent():
    """Singleton public paper-trading agent (Postgres-backed when available)."""
    from app.engines.paper_agent import PaperAgent
    from app.engines.paper_agent.factory import build_paper_store

    return PaperAgent(
        market_data=get_market_data_service(),
        crypto_scanner=get_setup_scanner(),
        equity_scanner=get_equity_options_scanner(),
        store=build_paper_store(),
        learning=get_learning_engine(),
        pipeline=get_decision_pipeline(),
        alerts=get_alert_service(),
    )


@lru_cache
def get_weight_optimizer() -> WeightOptimizer:
    """Singleton weight optimizer sharing market data cache."""
    return WeightOptimizer(market_data=get_market_data_service())


def get_test_weight_optimizer() -> WeightOptimizer:
    """Weight optimizer with mock market data for tests."""
    from app.scoring.weight_config import WeightConfig

    return WeightOptimizer(
        market_data=get_test_market_data_service(),
        weight_config=WeightConfig(),
    )
