"""Analytics module — the accuracy core. Turns ticks into truth (deterministic).

Consumes normalized chains, produces the :class:`~paz_rav.contracts.Feature` that the
builder and (later) the committee reason over. No AI here — every number is computed.
"""

from paz_rav.analytics.features import AnalyticsResult, analyze
from paz_rav.analytics.iv import atm_iv, contract_iv, iv_percentile, iv_rank, skew
from paz_rav.analytics.regime import classify, condor_friendly

__all__ = [
    "analyze",
    "AnalyticsResult",
    "atm_iv",
    "contract_iv",
    "iv_rank",
    "iv_percentile",
    "skew",
    "classify",
    "condor_friendly",
]
