"""Factory registry — build a strategy by name, no if/else chains.

    strat = make_strategy("iron_condor")

New structures self-register with the ``@register`` decorator, so adding one never
touches the builder or the scheduler.
"""

from __future__ import annotations

from paz_rav.strategies.base import OptionStrategy
from paz_rav.strategies.iron_condor import IronCondor

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Class decorator that registers a strategy under its ``name``."""
    name = getattr(cls, "name", None)
    if not name:
        raise ValueError(f"{cls.__name__} must define a 'name' attribute")
    if name in _REGISTRY:
        raise ValueError(f"strategy {name!r} already registered")
    _REGISTRY[name] = cls
    return cls


def make_strategy(name: str) -> OptionStrategy:
    """Return a fresh instance of the strategy registered under ``name``."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"unknown strategy {name!r}; registered: {known}") from None
    return cls()


def list_strategies() -> list[str]:
    return sorted(_REGISTRY)


# Built-in strategies. Diagonal / double-diagonal land here as they are implemented.
register(IronCondor)
