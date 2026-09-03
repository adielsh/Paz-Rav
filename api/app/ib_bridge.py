"""Read-only live view of the IBKR paper account (executions, orders, positions, account).

Strictly read-only: this module NEVER places, modifies, or cancels orders — it only calls IB's
request/query methods. That preserves the safety property that the api service cannot affect trading.
The connection uses a distinct clientId (12) so it never collides with the trading-core daemon (11).

If the gateway is unavailable, endpoints degrade gracefully: they return {"connected": false, ...}
with HTTP 200 so the UI can render an "offline" state instead of erroring.
"""
from __future__ import annotations

import asyncio
import os
import logging

from fastapi import APIRouter
from ib_async import IB, ExecutionFilter

log = logging.getLogger("ib_bridge")
router = APIRouter(prefix="/ib", tags=["ib"])

IB_HOST = os.getenv("IB_HOST", "ib-gateway")
IB_PORT = int(os.getenv("IB_PORT", "4004"))
# Pool of client IDs. On reconnect we rotate: a stale session at the gateway (left by a previous
# api container) makes a repeat clientId hang the API handshake, so we pick a fresh one instead.
_CLIENT_IDS = list(range(12, 24))
_ci = 0

_ib: IB = IB()
_lock = asyncio.Lock()


async def _ensure() -> bool:
    """Ensure a live connection; return True if connected. Best-effort, never raises or hangs.

    Uses a FRESH IB() instance and a ROTATING clientId on every (re)connect, and double-bounds the
    connect with wait_for so a stuck API handshake can't wedge the endpoint.
    """
    global _ib, _ci
    if _ib.isConnected():
        return True
    try:
        _ib.disconnect()
    except Exception:
        pass
    _ib = IB()
    cid = _CLIENT_IDS[_ci % len(_CLIENT_IDS)]
    _ci += 1
    try:
        await asyncio.wait_for(
            _ib.connectAsync(IB_HOST, IB_PORT, clientId=cid, timeout=8), timeout=10)
        log.info("ib_bridge connected", extra={"account": _ib.managedAccounts(), "clientId": cid})
        return True
    except Exception as e:
        log.warning("ib_bridge connect failed", extra={"error": str(e), "clientId": cid})
        return False


async def startup() -> None:
    async with _lock:
        await _ensure()


async def shutdown() -> None:
    if _ib.isConnected():
        _ib.disconnect()


def _acct() -> str:
    accts = _ib.managedAccounts()
    return accts[0] if accts else ""


async def current_nav_pnl() -> dict:
    """Real NAV + live daily P&L for the account (reqPnL). Time-bounded so it never hangs the app."""
    try:
        return await asyncio.wait_for(_current_nav_pnl(), timeout=14)
    except (asyncio.TimeoutError, Exception) as e:      # noqa: BLE001 - degrade gracefully
        log.warning("current_nav_pnl failed", extra={"error": str(e)})
        return {"connected": False}


async def _current_nav_pnl() -> dict:
    async with _lock:
        if not await _ensure():
            return {"connected": False}
        acct = _acct()
        rows = await _ib.accountSummaryAsync(acct)
        net_liq = _num(next((r.value for r in rows if r.tag == "NetLiquidation"), None))
        pnl = _ib.reqPnL(acct)
        for _ in range(6):                        # wait up to 3s for the first PnL update
            await asyncio.sleep(0.5)
            if pnl.dailyPnL == pnl.dailyPnL:      # not NaN
                break
        out = {"connected": True, "net_liq": net_liq,
               "daily": _nan(pnl.dailyPnL), "unrealized": _nan(pnl.unrealizedPnL),
               "realized": _nan(pnl.realizedPnL), "account": acct}
        try:
            _ib.cancelPnL(acct)
        except Exception:
            pass
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _nan(x):
    return None if x is None or x != x else float(x)


@router.get("/status")
async def status() -> dict:
    async with _lock:
        ok = await _ensure()
    return {"connected": ok, "account": _acct() if ok else None,
            "host": IB_HOST, "port": IB_PORT}


@router.get("/pnl")
async def pnl() -> dict:
    return await current_nav_pnl()


@router.get("/account")
async def account() -> dict:
    async with _lock:
        if not await _ensure():
            return {"connected": False, "summary": {}}
        rows = await _ib.accountSummaryAsync(_acct())
    keep = {"NetLiquidation", "AvailableFunds", "BuyingPower", "InitMarginReq",
            "MaintMarginReq", "ExcessLiquidity", "GrossPositionValue"}
    summary = {r.tag: r.value for r in rows if r.tag in keep}
    return {"connected": True, "account": _acct(), "summary": summary}


@router.get("/positions")
async def positions() -> dict:
    async with _lock:
        if not await _ensure():
            return {"connected": False, "items": []}
        rows = await _ib.reqPositionsAsync()
    items = [{
        "account": p.account, "symbol": p.contract.symbol, "secType": p.contract.secType,
        "right": getattr(p.contract, "right", ""), "strike": getattr(p.contract, "strike", None),
        "expiry": getattr(p.contract, "lastTradeDateOrContractMonth", ""),
        "tradingClass": getattr(p.contract, "tradingClass", ""),
        "position": p.position, "avgCost": p.avgCost,
    } for p in rows]
    return {"connected": True, "items": items}


@router.get("/executions")
async def executions() -> dict:
    """Recent fills on the account (IB returns roughly the last trading day)."""
    async with _lock:
        if not await _ensure():
            return {"connected": False, "items": []}
        fills = await _ib.reqExecutionsAsync(ExecutionFilter())
    items = []
    for f in fills:
        e, c, cr = f.execution, f.contract, f.commissionReport
        items.append({
            "time": e.time.isoformat() if e.time else None,
            "symbol": c.symbol, "secType": c.secType, "right": getattr(c, "right", ""),
            "strike": getattr(c, "strike", None),
            "expiry": getattr(c, "lastTradeDateOrContractMonth", ""),
            "side": e.side, "shares": float(e.shares), "price": e.price,
            "permId": e.permId, "orderId": e.orderId,
            "commission": getattr(cr, "commission", None),
            "realizedPNL": getattr(cr, "realizedPNL", None),
        })
    items.sort(key=lambda x: x["time"] or "", reverse=True)
    return {"connected": True, "items": items}


@router.get("/orders")
async def orders() -> dict:
    """Open orders + recently completed orders.

    Time-bounded like current_nav_pnl(): these two IB requests can hang indefinitely when
    the gateway is mid re-auth, and because they hold the shared lock a single hung call
    took every other /ib/* endpoint down with it.
    """
    try:
        return await asyncio.wait_for(_orders(), timeout=14)
    except (asyncio.TimeoutError, Exception) as e:      # noqa: BLE001 - degrade gracefully
        log.warning("orders request failed: %s", e)
        return {"connected": False, "open": [], "completed": []}


async def _orders() -> dict:
    async with _lock:
        if not await _ensure():
            return {"connected": False, "open": [], "completed": []}
        open_trades = await _ib.reqAllOpenOrdersAsync()
        completed = await _ib.reqCompletedOrdersAsync(apiOnly=False)

    def _fmt(t) -> dict:
        o, c, st = t.order, t.contract, t.orderStatus
        return {
            "permId": o.permId, "action": o.action, "orderType": o.orderType, "tif": o.tif,
            "lmtPrice": o.lmtPrice, "totalQuantity": o.totalQuantity,
            "symbol": c.symbol, "secType": c.secType,
            "status": st.status, "filled": st.filled, "remaining": st.remaining,
            "avgFillPrice": st.avgFillPrice,
        }
    return {"connected": True, "open": [_fmt(t) for t in open_trades],
            "completed": [_fmt(t) for t in completed]}
