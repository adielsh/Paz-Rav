# Product Requirements Document (PRD): SPX Adaptive Iron Condor Bot
### v6.1 — "The Balanced Fortress" (reviewed)

> **Review status:** Reviewed 2026-07-26. Confirmed build decisions and open reconciliation
> items are called out in **Reviewer notes** callouts. The strategy name "Hit & Run / ultra-short
> theta" is retained for continuity, but note the actual structure is a 35–45 DTE premium-selling
> condor (~10–20 day holds), not a 0DTE strategy.

## 1. Project Philosophy & Core Logic
Develop an automated, cloud-deployed algorithmic options trading bot using the Interactive Brokers API
(`ib_async`). The system operates as an adaptive "insurance seller" on the SPX, capturing short-term
Theta decay using VIX-adjusted Deltas, capital-preservation limits, and mechanical failsafes against
exchange/liquidity anomalies.

## 2. Technical Stack & Architecture
* **Language:** Python 3.10+
* **Dependencies:** `uv` package manager, `ib_async`, `pandas_market_calendars`, `pytz`.
* **Timezone/Scheduling:** Persistent daemon with an internal scheduler executing exclusively in
  `America/New_York` timezone.
* **Cloud Operations:** Dockerized deployment with an **IBC (IB Controller)** container for headless
  24/7 API session regeneration.

> **Reviewer notes (§2):**
> - **Library:** Built on `ib_async` (maintained fork of the now-unmaintained `ib_insync`; drop-in API).
> - **Run model:** Persistent daemon (not one-shot cron). Internal scheduler fires the 14:30 ET flow;
>   GTC take-profit orders live server-side at IB and survive restarts.
> - **Docker image:** Verify the IB-gateway image path before deploy — the widely-used, IBC-bundled
>   image is `ghcr.io/gnzsnz/ib-gateway-docker` (the earlier `ghcr.io/extt/...` reference is unverified).

## 3. Asset Specification & Execution Integrity
* **Symbol:** SPX | **Exchange:** SMART | **Trading Class:** `SPXW` (PM-Settled ONLY).
* **Multiplier:** 100
* **Position size:** **Fixed 1 lot** (1 combo contract) per trade.
* **Guaranteed Execution:** Combo (`BAG`) MUST route with `NonGuaranteed=0` (in
  `smartComboRoutingParams`) to prevent naked short exposure.
* **Tick Size Compliance:** Dynamically round to nearest CBOE valid tick ($0.05 for < $3.00;
  $0.10 for >= $3.00).

## 4. Adaptive Market-Entry Router
Execution time is strictly **14:30 America/New_York** on valid US trading days
(use `pandas_market_calendars` schedule — skip holidays **and** early-close/half-days).

### Market Data Validation
* Fetch the 5-minute historical average for `VIX` to bypass API zero-glitches.
* **Halt Guardrail (Circuit Breaker):** Check `TickType.HALTED` for the SPX index and all 4 option legs.
  If any component is halted, ABORT execution for the day.

### VIX-Based Delta State Machine
* **VIX < 14:** Target Deltas → Short Put 0.15 / Short Call 0.15.
* **14 <= VIX <= 22:** Target Deltas → Short Put 0.30 / Short Call 0.20. *(Intentional put-skew:
  short put sits closer to the money than the short call.)*
* **VIX > 22:** Suspend new trade execution. Log "Systemic Volatility Alert".

### Structuring the Condor
* **DTE Window:** 35 to 45 Days to Expiration. Select expiry with tightest Bid/Ask.
* **Wing Width:** 50 points.
* **Zero-Bid Guardrail:** Ensure ALL 4 legs have a `Bid > 0.00`. If a long wing has $0.00 bid, shift the
  wing strike by 5 points until a valid bid exists.

> **Reviewer note (§4 — open item):** The fixed 50-point wing width and the zero-bid wing-shift rule
> conflict — shifting a long leg changes wing width, max risk, and margin. **Reconcile during build:**
> preferred approach is to shift the *entire spread* (keep 50-pt width) rather than one leg; if variable
> width is allowed, re-run the margin and risk gates after any shift.

## 5. The Pre-Flight Failsafe Matrix
1. **Min Credit Gate:** Mid-price MUST be >= $1.20.
2. **Liquidity Canyon Gate:** Combo Ask − Combo Bid MUST be <= $1.50.
3. **"WhatIf" Margin Gate:** `WhatIf.initMargin` for the 1-lot MUST NOT exceed
   `(NetLiquidation * 0.70) − Current_InitMarginReq`. *(Pass/fail check at fixed 1-lot size.)*
4. **Pyramiding Gate:** Max ONE (1) new combo per day. NO overlapping short strikes with open
   portfolio positions.
5. **PDT Guardrail:** If `NetLiquidation` is between $25,000 and $25,500, append a condition to the `GTC`
   Take-Profit order preventing same-calendar-day execution.

> **Reviewer note (§5.5 — open item):** PDT rules apply only to **margin accounts under $25k**; cash and
> portfolio-margin accounts are exempt, and this strategy rarely round-trips same-day (entry 14:30, GTC
> exits on later days). **Confirm account type during build** — likely simplify or drop this gate.

## 6. Execution Flow & State Recovery

### 6.1 Throttled Limit Walking (Entry)
* Submit Entry Limit Order 1 tick favorable to the bot from Mid-Price.
* **Anti-Spam Throttling:** Modify by 1 valid tick every **10 seconds** (respect IBKR pacing via
  `asyncio.sleep`).
* **TTL:** Cancel order after 120 seconds if unfilled.

### 6.2 Auto Take-Profit
* Upon full/partial fill, transmit the resting `GTC` Limit child order.
* Target Price: $50 exact profit per lot ($0.50 credit differential × 100).

### 6.3 State Recovery Engine
* On boot, scan open SPXW combos. If a combo lacks a corresponding open `GTC` order, reassemble the BAG
  from its per-leg positions (match by expiry/right/strike, sum signed avg costs for the net basis),
  compute the required exit price, and re-attach a GTC order.

### 6.4 The 25 DTE Gamma Stop
* Scan all open positions daily at 14:30. If an SPXW combo reaches 25 DTE, initiate a forced mechanical
  exit using an aggressive Limit Walk starting at current Mid-Price.

> **Reviewer note (§6 — risk):** The only exits are the $50 take-profit and the 25-DTE gamma stop.
> There is **no loss-based stop** (accepted decision). Max loss per 1-lot ≈ (50 − 1.20) × 100 = **$4,880**
> against a $50 target (~1:97). The defined-risk wings are the sole backstop before 25 DTE.

## 7. Directives for the Developer
1. Strict `asyncio.sleep` delays during Limit Walking to respect IBKR message pacing limits.
2. `NonGuaranteed=0` explicitly set in `smartComboRoutingParams`.
3. Modular code: `config.py`, `utils.py`, `data_fetcher.py`, `risk_manager.py`, `execution.py`, `main.py`.
4. Standard Python `logging` records every rejected gate and every parameter change (structured).
5. **Paper account first** — full 14:30 flow end-to-end on the IBKR paper gateway before any live run.

## 8. Confirmed-correct design points (kept as-is)
- `tradingClass='SPXW'` correctly selects PM-settled weeklies (excludes AM-settled standard SPX).
- CBOE tick rules ($0.05 <$3.00, $0.10 ≥$3.00).
- `TickType.HALTED` (tick 49) halt guard on index + 4 legs.
- 10s modify throttle / 120s TTL — conservative and pacing-safe.
- VIX 5-min historical average to avoid zero-glitch reads.

## 9. Confirmed build decisions
| # | Decision | Choice |
|---|----------|--------|
| 1 | Position sizing | Fixed 1 lot |
| 2 | Loss-based stop | None — TP ($50) + 25-DTE gamma stop only |
| 3 | Run model | Persistent daemon, internal 14:30 ET scheduler |
| 4 | IBKR library | `ib_async` |

## 10. Open items to reconcile during build (non-blocking)
- 50-pt fixed wing width vs. zero-bid wing-shift rule (§4).
- IBKR account type → keep or drop the PDT gate (§5.5).
- Verify IB-gateway Docker image path before deployment (§2).
