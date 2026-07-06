"""Builder module — enumerate & rank trade candidates from a chain.

On a scan request it annotates the chain with greeks and asks every registered strategy
to enumerate candidates, then returns the top-ranked set.
"""

from paz_rav.builder.core import annotate, build

__all__ = ["annotate", "build"]
