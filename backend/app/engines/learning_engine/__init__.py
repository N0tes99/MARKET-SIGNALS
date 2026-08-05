"""Learning Engine — signal/trade/outcome storage and similarity."""

from app.engines.learning_engine.engine import LearningEngine
from app.engines.learning_engine.factory import build_signal_store
from app.engines.learning_engine.types import SignalOutcome, SignalRecord, SimilarMatch

__all__ = [
    "LearningEngine",
    "SignalOutcome",
    "SignalRecord",
    "SimilarMatch",
    "build_signal_store",
]
