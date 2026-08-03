"""Evidence Engine — central evidence accumulation system.

The Evidence Engine collects evidence from all other engines.
It NEVER predicts. It accumulates evidence and feeds downstream engines.
"""

from app.engines.evidence_engine.engine import EvidenceEngine
from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem

__all__ = ["EvidenceEngine", "EvidenceBundle", "EvidenceItem"]
