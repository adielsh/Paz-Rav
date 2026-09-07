"""The IBKR market-data adapter, driven against a fake gateway.

`ib_async` is an optional extra and a real gateway is not available in a test run, so a
minimal fake stands in. That is enough to pin the behaviour that actually matters here,
none of which is about IBKR's wire protocol:

- **lines are never leaked.** IBKR caps concurrent market-data lines and the console's
  trading daemon shares that cap. Exceeding it returns nothing silently rather than
  raising, so a leak would degrade live trading to serve a ranking engine. The adapter
  must cancel every subscription it opens, including on timeout, and must never hold more
  than `max_lines` at once.
- **the strike window is bounded by count**, not by a percentage band, so a name with a
  fine strike ladder cannot blow the budget.
- **broken quotes are dropped, not invented** — the project's standing rule.

Async methods are driven with asyncio.run, matching tests/test_store.py.
"""

import asyncio
import sys
import types
from datetime import date

import pytest


# --------------------------------------------------------------------- the fake --

class FakeTicker:
    def __init__(self, bid=1.0, ask=1.2, last=1.1, close=1.1, iv=0.2, oi=100):
        self.bid, self.ask, self.last, self.close = bid, ask, last, close
        self.callOpenInterest = oi
        self.putOpenInterest = oi
        self.modelGreeks = types.SimpleNamespace(impliedVol=iv) if iv is not None else None

    def marketPrice(self):
        return self.last


class FakeContract:
    def __init__(self, symbol="SPY", strike=0.0, right="", expiry="20261120",
                 trading_class="SPY"):
        self.symbol = symbol
        self.strike = strike
        self.right = right
        self.lastTradeDateOrContractMonth = expiry
        self.tradingClass = trading_class
        self.conId = 0
        self.exchange = "SMART"


class FakeChainParams:
    def __init__(self, expirations, strikes, trading_class, exchange="SMART"):
        self.expirations = expirations
        self.strikes = strikes
        self.tradingClass = trading_class
        self.exchange = exchange


class FakeIB:
    """Tracks open market-data lines so the tests can assert the budget is respected."""

    #: Spot for the underlying. Kept mid-ladder so the strike window really straddles it.
    SPOT = 100.0

    def __init__(self, *, strikes=None, expirations=("20261120",), quote=None,
                 unqualified=()):
        self.open_lines = 0
        self.peak_lines = 0
        self.requested = []
        self.cancelled = []
        self.strikes = list(strikes if strikes is not None else [float(k) for k in range(1, 401)])
        self.expirations = list(expirations)
        # `quote` covers OPTION contracts only; the underlying answers separately so a
        # test can blank the chain without also blanking spot.
        self.quote = quote or (lambda c: FakeTicker())
        self.underlying_quote = lambda c: FakeTicker(bid=self.SPOT - 0.05, ask=self.SPOT + 0.05,
                                                     last=self.SPOT, close=self.SPOT, iv=None)
        self.unqualified = set(unqualified)
        self._connected = False

    def option_requests(self):
        """Only the option lines — excludes the underlying's own quote."""
        return [c for c in self.requested if getattr(c, "right", "") in ("P", "C")]

    def isConnected(self):
        return self._connected

    async def connectAsync(self, host, port, clientId, timeout):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def reqMarketDataType(self, t):
        self.market_data_type = t

    async def qualifyContractsAsync(self, *contracts):
        for c in contracts:
            if getattr(c, "strike", 0.0) in self.unqualified:
                c.conId = 0
            else:
                c.conId = int(abs(hash((c.symbol, getattr(c, "strike", 0),
                                        getattr(c, "right", "")))) % 10**8) or 1
        return list(contracts)

    async def reqSecDefOptParamsAsync(self, symbol, exch, sec_type, con_id):
        return [FakeChainParams(self.expirations, self.strikes, symbol)]

    def reqMktData(self, contract, generic, snapshot, regulatory):
        self.open_lines += 1
        self.peak_lines = max(self.peak_lines, self.open_lines)
        self.requested.append(contract)
        if getattr(contract, "right", "") in ("P", "C"):
            return self.quote(contract)
        return self.underlying_quote(contract)

    def cancelMktData(self, contract):
        self.open_lines -= 1
        self.cancelled.append(contract)


def _install_fake_ib_async(ib: FakeIB):
    """Register a stand-in `ib_async` module; the adapter imports it lazily."""
    mod = types.ModuleType("ib_async")
    mod.IB = lambda: ib

    def _index(sym, exch):
        return FakeContract(symbol=sym)

    def _stock(sym, exch, cur):
        return FakeContract(symbol=sym)

    def _option(sym, expiry, strike, right, exch, tradingClass=""):
        return FakeContract(symbol=sym, strike=strike, right=right, expiry=expiry,
                            trading_class=tradingClass)

    mod.Index, mod.Stock, mod.Option, mod.Contract = _index, _stock, _option, FakeContract
    sys.modules["ib_async"] = mod
    return mod


@pytest.fixture
def fake_ib(monkeypatch):
    ib = FakeIB()
    _install_fake_ib_async(ib)
    yield ib
    sys.modules.pop("ib_async", None)


def _run(coro):
    return asyncio.run(coro)


def _adapter(**kw):
    from paz_rav.adapters.ibkr import IBKRMarketData
    kw.setdefault("quote_timeout", 0.5)
    return IBKRMarketData(**kw)


# ---------------------------------------------------------------------- the tests --

def test_underlying_returns_a_quote(fake_ib):
    md = _adapter()
    q = _run(md.underlying("SPY"))
    assert q.symbol == "SPY"
    assert q.price == pytest.approx(FakeIB.SPOT)


def test_list_expiries_parses_ibkr_yyyymmdd(fake_ib):
    fake_ib.expirations = ["20261120", "20261218", "BADVALUE"]
    md = _adapter()
    assert _run(md.list_expiries("SPY")) == [date(2026, 11, 20), date(2026, 12, 18)]


def test_strike_window_is_bounded_by_count_not_price(fake_ib):
    """A 400-strike ladder must still produce a small, bounded request."""
    md = _adapter(strikes_each_side=10)
    quotes = _run(md.chain("SPY", date(2026, 11, 20)))
    # 10 strikes each side x 2 rights = 40 contracts, regardless of ladder size.
    assert len(quotes) == 40
    assert len(fake_ib.option_requests()) == 40


def test_window_straddles_spot(fake_ib):
    md = _adapter(strikes_each_side=3, moneyness=0.12)
    _run(md.chain("SPY", date(2026, 11, 20)))
    strikes = sorted({c.strike for c in fake_ib.option_requests()})
    spot = FakeIB.SPOT
    assert sum(1 for k in strikes if k <= spot) == 3
    assert sum(1 for k in strikes if k > spot) == 3
    assert min(strikes) >= spot * 0.88 and max(strikes) <= spot * 1.12


def test_window_reaches_the_delta_targets_on_a_fine_ladder(fake_ib):
    """The bug a live run found: a count-based window is useless on a $1 ladder.

    18 strikes each side of a 769 spot reaches +-2.3%, but a 16-delta short strike at
    35 DTE sits far outside that — so the chain came back bounded, valid and useless.
    Thinning across a moneyness band is what fixes it.
    """
    fake_ib.strikes = [float(k) for k in range(600, 950)]   # $1 ladder, like SPY
    fake_ib.SPOT = 769.0
    fake_ib.underlying_quote = lambda c: FakeTicker(bid=768.9, ask=769.1, last=769.0,
                                                    close=769.0, iv=None)
    md = _adapter(strikes_each_side=18, moneyness=0.12)
    _run(md.chain("SPY", date(2026, 11, 20)))
    strikes = sorted({c.strike for c in fake_ib.option_requests()})
    assert len(strikes) <= 36, "must stay bounded"
    # Reach: reads out to roughly the band edges, not just a sliver around spot.
    assert min(strikes) <= 769.0 * 0.90, f"only reached down to {min(strikes)}"
    assert max(strikes) >= 769.0 * 1.10, f"only reached up to {max(strikes)}"


def test_picks_the_real_option_class_not_an_adjusted_one(fake_ib):
    """The other live bug: IBKR returns `2SPY` (sparse, 2 expiries) next to the real
    `SPY`. Choosing the first SMART entry picked `2SPY`, and every strike then came back
    'No security definition has been found' — a chain that looked empty rather than wrong.
    """
    from paz_rav.adapters.ibkr import _pick_chain
    adjusted = FakeChainParams(["20261120", "20261218"], [672.0, 682.0], "2SPY")
    real = FakeChainParams([f"2026{m:02d}20" for m in range(1, 13)],
                           [float(k) for k in range(600, 950)], "SPY")
    assert _pick_chain([adjusted, real], "SPY").tradingClass == "SPY"
    assert _pick_chain([real, adjusted], "SPY").tradingClass == "SPY"


def test_prefers_pm_settled_weeklies_for_an_index(fake_ib):
    """SPXW is what the console's daemon actually trades, so the engine must price it."""
    from paz_rav.adapters.ibkr import _pick_chain
    monthly = FakeChainParams(["20261120"], [float(k) for k in range(4000, 7000, 5)], "SPX")
    weekly = FakeChainParams(["20261120"], [float(k) for k in range(4000, 6000, 5)], "SPXW")
    assert _pick_chain([monthly, weekly], "SPX").tradingClass == "SPXW"


def test_every_line_is_released(fake_ib):
    """The failure that would hurt: a held line starves the trading daemon."""
    md = _adapter(strikes_each_side=8)
    _run(md.chain("SPY", date(2026, 11, 20)))
    assert fake_ib.open_lines == 0
    assert len(fake_ib.cancelled) == len(fake_ib.requested)   # underlying line too


def test_never_exceeds_the_line_budget(fake_ib):
    md = _adapter(strikes_each_side=25, max_lines=6)
    _run(md.chain("SPY", date(2026, 11, 20)))
    assert fake_ib.peak_lines <= 6, f"opened {fake_ib.peak_lines} lines, budget was 6"


def test_line_is_released_even_when_the_quote_never_arrives(fake_ib):
    fake_ib.quote = lambda c: FakeTicker(bid=float("nan"), ask=float("nan"),
                                         last=float("nan"), close=float("nan"), iv=None)
    md = _adapter(strikes_each_side=3)
    quotes = _run(md.chain("SPY", date(2026, 11, 20)))
    assert quotes == []                      # nothing usable -> nothing invented
    assert fake_ib.open_lines == 0           # but the lines still came back


def test_unquotable_contracts_are_dropped_not_faked(fake_ib):
    """Half the chain returns nothing; the other half must still come through intact."""
    def quote(c):
        if c.strike % 2 == 0:
            return FakeTicker(bid=float("nan"), ask=float("nan"),
                              last=float("nan"), close=float("nan"), iv=None)
        return FakeTicker()
    fake_ib.quote = quote
    md = _adapter(strikes_each_side=5)
    quotes = _run(md.chain("SPY", date(2026, 11, 20)))
    assert quotes and all(q.strike % 2 == 1 for q in quotes)


def test_unqualified_strikes_are_skipped(fake_ib):
    """The ladder advertises strikes across all expiries; unlisted ones must not be requested."""
    fake_ib.unqualified = {98.0, 99.0, 100.0}
    md = _adapter(strikes_each_side=4)
    _run(md.chain("SPY", date(2026, 11, 20)))
    assert not any(c.strike in {98.0, 99.0, 100.0} for c in fake_ib.option_requests())


def test_one_sided_book_keeps_mid_honest(fake_ib):
    """Off-hours there is often no bid. We must not fabricate the other side."""
    fake_ib.quote = lambda c: FakeTicker(bid=float("nan"), ask=2.0, last=None, close=1.8)
    md = _adapter(strikes_each_side=2)
    q = _run(md.chain("SPY", date(2026, 11, 20)))[0]
    assert q.bid == 0.0 and q.ask == 2.0
    assert q.last == 1.8            # the builder falls back to this


def test_vendor_iv_and_open_interest_are_carried_through(fake_ib):
    md = _adapter(strikes_each_side=2)
    q = _run(md.chain("SPY", date(2026, 11, 20)))[0]
    assert q.implied_vol == pytest.approx(0.2)
    assert q.open_interest == 100


def test_missing_model_greeks_is_not_an_error(fake_ib):
    """IV is an optimisation — the builder solves for it when the vendor omits it."""
    fake_ib.quote = lambda c: FakeTicker(iv=None)
    md = _adapter(strikes_each_side=2)
    q = _run(md.chain("SPY", date(2026, 11, 20)))[0]
    assert q.implied_vol is None
    assert q.bid > 0


def test_chain_params_are_cached_per_day(fake_ib):
    md = _adapter(strikes_each_side=2)
    calls = []
    orig = fake_ib.reqSecDefOptParamsAsync

    async def counting(*a):
        calls.append(a)
        return await orig(*a)
    fake_ib.reqSecDefOptParamsAsync = counting

    _run(md.list_expiries("SPY"))
    _run(md.list_expiries("SPY"))
    assert len(calls) == 1, "the strike ladder must not be refetched on every scan"


def test_index_symbols_route_to_their_own_exchange(fake_ib):
    """SPX is an Index on CBOE, not a SMART-routed stock — getting this wrong yields an
    unqualified contract rather than an error."""
    from paz_rav.adapters.ibkr import _INDEX_EXCHANGE
    assert _INDEX_EXCHANGE["SPX"] == "CBOE"
    assert "SPY" not in _INDEX_EXCHANGE


def test_satisfies_the_market_data_port(fake_ib):
    from paz_rav.adapters.market_data import MarketData
    assert isinstance(_adapter(), MarketData)
