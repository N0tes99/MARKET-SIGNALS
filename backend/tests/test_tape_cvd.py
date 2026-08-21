"""Public-trade tape CVD scoring."""

from datetime import UTC, datetime

from app.cortex.specialists import collect_cvd_opinion
from app.engines.buyer_seller_engine.engine import OrderFlowResult
from app.market_data.tape import TapeCvd, TapeTrade, compute_tape_cvd


class _Cvd:
    def analyze(self, symbol: str, timeframe: str = "1h") -> OrderFlowResult:
        del timeframe
        return OrderFlowResult(
            symbol=symbol,
            buyer_strength=70.0,
            seller_strength=30.0,
            absorption=80.0,
            momentum=55.0,
            volume_ratio=1.4,
            description=f"{symbol}: buyers",
        )


def _trades(buy: int, sell: int) -> list[TapeTrade]:
    now = datetime(2026, 8, 21, tzinfo=UTC)
    out: list[TapeTrade] = []
    for _ in range(buy):
        out.append(TapeTrade(price=100.0, volume=1.0, ts=now, side="buy"))
    for _ in range(sell):
        out.append(TapeTrade(price=100.0, volume=1.0, ts=now, side="sell"))
    return out


def test_compute_tape_cvd_buy_pressure() -> None:
    cvd = compute_tape_cvd(_trades(80, 20), symbol="BTC", source="kraken_tape")
    assert cvd is not None
    assert cvd.trade_count == 100
    assert cvd.score > 60
    assert cvd.direction == "up"
    assert cvd.source == "kraken_tape"


def test_compute_tape_cvd_requires_prints() -> None:
    assert compute_tape_cvd(_trades(5, 5), symbol="ETH", source="kraken_tape") is None


def test_cvd_opinion_uses_tape_when_present(monkeypatch) -> None:
    tape = TapeCvd(
        symbol="BTC",
        source="kraken_tape",
        buy_volume=200,
        sell_volume=50,
        delta=150,
        score=72.0,
        trade_count=80,
        as_of=datetime(2026, 8, 21, tzinfo=UTC),
    )
    monkeypatch.setattr("app.market_data.tape.fetch_tape_cvd", lambda symbol: tape)
    op = collect_cvd_opinion(_Cvd(), "BTC")  # type: ignore[arg-type]
    assert op.metadata["proxy"] is False
    assert op.metadata["source"] == "kraken_tape"
    assert op.score == 72.0
