"""Named expansion score weights — live policy, then normalized."""

from __future__ import annotations

from dataclasses import dataclass

from app.engines.expansion_engine.config import ExpansionConfig, default_expansion_config

WEIGHT_NAMES = (
    "compression",
    "squeeze",
    "trigger",
    "momentum",
    "derivatives",
)


@dataclass(frozen=True)
class ExpansionWeights:
    """Relative shares; composer normalizes so they sum to 1.0."""

    compression: float
    squeeze: float
    trigger: float
    momentum: float
    derivatives: float
    source: str = "file"
    version: int = 0
    normalized: bool = False

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in WEIGHT_NAMES}

    def normalize(self) -> ExpansionWeights:
        total = sum(self.as_dict().values())
        if total <= 0:
            return ExpansionWeights(
                compression=0.25,
                squeeze=0.25,
                trigger=0.20,
                momentum=0.15,
                derivatives=0.15,
                source=self.source,
                version=self.version,
                normalized=True,
            )
        scale = 1.0 / total
        return ExpansionWeights(
            compression=self.compression * scale,
            squeeze=self.squeeze * scale,
            trigger=self.trigger * scale,
            momentum=self.momentum * scale,
            derivatives=self.derivatives * scale,
            source=self.source,
            version=self.version,
            normalized=True,
        )


def weights_from_config(cfg: ExpansionConfig | None = None) -> ExpansionWeights:
    """Read knobs from live expansion policy (Postgres overlay or file)."""
    live = cfg or default_expansion_config()
    source = "file"
    version = 0
    try:
        from app.memory.procedural.config_store import policy_meta

        meta = policy_meta()
        source = str(meta.get("source") or "file")
        version = int(meta.get("version") or 0)
    except Exception:
        pass
    raw = ExpansionWeights(
        compression=float(live.weight_compression),
        squeeze=float(live.weight_squeeze),
        trigger=float(live.weight_trigger),
        momentum=float(live.weight_momentum),
        derivatives=float(live.weight_derivatives),
        source=source,
        version=version,
    )
    return raw.normalize()
