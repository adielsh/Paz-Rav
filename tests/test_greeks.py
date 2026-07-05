"""Greeks + pricing invariants. Pure stdlib — no extra installs needed."""

import math

import pytest

from paz_rav.quant import black_scholes, greeks
from paz_rav.quant.pop import expected_move, prob_between, prob_of_profit

S, K, T, R, SIG = 100.0, 100.0, 1.0, 0.01, 0.20


def test_put_call_parity():
    call = black_scholes(S, K, T, R, SIG, "call")
    put = black_scholes(S, K, T, R, SIG, "put")
    # C - P = S - K e^{-rT}   (no dividends)
    assert call - put == pytest.approx(S - K * math.exp(-R * T), abs=1e-9)


def test_atm_call_price_reference():
    # Independently known: ~8.43 for these inputs.
    assert black_scholes(S, K, T, R, SIG, "call") == pytest.approx(8.43, abs=0.05)


def test_greek_signs_and_bounds():
    g_call = greeks(S, K, T, R, SIG, "call")
    g_put = greeks(S, K, T, R, SIG, "put")

    assert 0.0 < g_call.delta < 1.0
    assert -1.0 < g_put.delta < 0.0
    assert g_call.gamma > 0.0
    assert g_call.vega > 0.0
    assert g_call.theta < 0.0  # long option bleeds time value
    # call & put share gamma and vega
    assert g_call.gamma == pytest.approx(g_put.gamma, abs=1e-12)
    assert g_call.vega == pytest.approx(g_put.vega, abs=1e-12)


def test_delta_call_put_relationship():
    # delta_call - delta_put = e^{-qT} = 1 for q=0
    g_call = greeks(S, K, T, R, SIG, "call")
    g_put = greeks(S, K, T, R, SIG, "put")
    assert g_call.delta - g_put.delta == pytest.approx(1.0, abs=1e-9)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        black_scholes(S, K, 0.0, R, SIG, "call")
    with pytest.raises(ValueError):
        greeks(-1.0, K, T, R, SIG, "call")


def test_expected_move_and_pop():
    em = expected_move(S, SIG, T)
    assert em == pytest.approx(20.0, abs=1e-9)  # 100 * 0.20 * 1

    p = prob_between(S, 90.0, 110.0, SIG, T)
    assert 0.0 < p < 1.0

    # profit region "between" and "outside" are complements
    pin = prob_of_profit(S, (94.0, 106.0), SIG, T, profit_region="between")
    pout = prob_of_profit(S, (94.0, 106.0), SIG, T, profit_region="outside")
    assert pin + pout == pytest.approx(1.0, abs=1e-9)
