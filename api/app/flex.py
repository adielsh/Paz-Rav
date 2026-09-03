"""IBKR Flex Web Service integration — REAL account statement data (trades + NAV).

This is the supported way to pull real historical account data programmatically from IBKR.
Setup (done once by the user in Account Management):
  1. Reporting → Settings → Flex Web Service: enable it, generate a TOKEN.
  2. Reporting → Flex Queries → Activity Flex Query: include the sections
     "Trades" and "Change in NAV"; set a wide period (e.g. Last 365 Days). Note the QUERY ID.
  3. Enter the token and query ID in Settings — they are stored per user, encrypted.

Flow: SendRequest -> ReferenceCode -> GetStatement (retry while generating) -> parse XML.
Results are cached (Flex is rate-limited) and never block the app when unconfigured.
"""
from __future__ import annotations

import os
import json
import time
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import create_engine, text

log = logging.getLogger("flex")

BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
CACHE_TTL = 1800           # seconds; Flex is rate-limited, don't hammer it

# Users currently being refreshed in the background, so overlapping page loads don't fire
# several statement requests at once — IBKR throttles that hard, and a throttled fetch
# takes minutes instead of seconds.
_refreshing: set[int] = set()


# Durable cache in Postgres so the big statement survives api restarts (and Flex is rarely hit).
_engine = create_engine(os.getenv("DB_DSN", "postgresql+psycopg://condor:condor@postgres:5432/condor"),
                        future=True, pool_pre_ping=True)


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "condor-bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _fetch(token: str, query_id: str) -> dict:
    """Run the two-step Flex flow and parse. Returns a structured dict.

    Credentials are passed in rather than read from the environment: each user holds their
    own Flex token, so the statement fetched here belongs to whoever is signed in.
    """
    send = f"{BASE}/SendRequest?" + urllib.parse.urlencode({"t": token, "q": query_id, "v": "3"})
    root = ET.fromstring(_get(send))
    status = (root.findtext("Status") or "").strip()
    if status != "Success":
        msg = root.findtext("ErrorMessage") or "SendRequest failed"
        return {"configured": True, "ok": False, "error": msg}
    ref = root.findtext("ReferenceCode")
    base_url = root.findtext("Url") or f"{BASE}/GetStatement"

    # Poll GetStatement — a wide (e.g. 365-day) statement can take a while to generate.
    stmt_xml = None
    for _ in range(20):
        got = f"{base_url}?" + urllib.parse.urlencode({"t": token, "q": ref, "v": "3"})
        text = _get(got)
        if "<FlexQueryResponse" in text:
            stmt_xml = text
            break
        if "Statement generation in progress" in text or "<Status>Warn" in text:
            time.sleep(5)
            continue
        # explicit error
        try:
            er = ET.fromstring(text)
            return {"configured": True, "ok": False, "error": er.findtext("ErrorMessage") or text[:200]}
        except ET.ParseError:
            time.sleep(4)
    if stmt_xml is None:
        return {"configured": True, "ok": False, "error": "statement not ready (try again shortly)"}

    return _parse(stmt_xml)


def _parse(xml: str) -> dict:
    root = ET.fromstring(xml)
    statements = root.findall(".//FlexStatement")
    if not statements:
        return {"configured": True, "ok": False, "error": "no FlexStatement in response"}

    # A wide query can return MANY statement blocks (e.g. one per day) — collect trades from ALL.
    all_rows = root.findall(".//Trade")
    # Flex emits the same fill at several "levels of detail" (ORDER / EXECUTION / CLOSED_LOT),
    # which multi-counts trades. Keep exactly one level: prefer EXECUTION (the real fills).
    levels = {r.attrib.get("levelOfDetail", "") for r in all_rows}
    prefer = "EXECUTION" if "EXECUTION" in levels else ("ORDER" if "ORDER" in levels else None)

    trades = []
    seen: set = set()
    for tr in all_rows:
        a = tr.attrib
        if prefer and a.get("levelOfDetail", "") != prefer:
            continue
        key = (a.get("ibExecID") or a.get("tradeID")
               or f"{a.get('dateTime')}|{a.get('symbol')}|{a.get('tradePrice')}|{a.get('quantity')}")
        if key in seen:
            continue
        seen.add(key)
        trades.append({
            "level": a.get("levelOfDetail", ""),
            "orderId": a.get("ibOrderID") or a.get("orderID") or "",
            "orderRef": a.get("orderReference", ""),
            "openClose": a.get("openCloseIndicator", ""),   # O = opening, C = closing
            "date": a.get("tradeDate") or (a.get("dateTime", "")[:8]),
            "dateTime": a.get("dateTime", ""),
            "symbol": a.get("symbol", ""), "underlying": a.get("underlyingSymbol", ""),
            "assetCategory": a.get("assetCategory", ""), "putCall": a.get("putCall", ""),
            "strike": _f(a.get("strike")), "expiry": a.get("expiry", ""),
            "buySell": a.get("buySell", ""), "quantity": _f(a.get("quantity")),
            "price": _f(a.get("tradePrice")), "proceeds": _f(a.get("proceeds")),
            "commission": _f(a.get("ibCommission")), "realized": _f(a.get("fifoPnlRealized")),
            "description": a.get("description", ""),
        })

    # Per-day NAV. IBKR emits one ChangeInNAV block per trading day, so this is a real
    # equity curve — and the only way to measure a TRUE period return, which needs the NAV
    # at the start of the window rather than lifetime deposits as the denominator.
    nav_days = []
    for c in root.findall(".//ChangeInNAV"):
        a = c.attrib
        day = a.get("toDate") or a.get("fromDate") or ""
        start_v, end_v = _f(a.get("startingValue")), _f(a.get("endingValue"))
        if not day or start_v is None or end_v is None:
            continue
        nav_days.append({
            "date": day, "start": start_v, "end": end_v,
            "deposits": _f(a.get("depositsWithdrawals")) or 0.0,
            "mtm": _f(a.get("mtm")) or 0.0,
            "commissions": _f(a.get("commissions")) or 0.0,
        })
    nav_days.sort(key=lambda d: d["date"])

    # Aggregate NAV across all ChangeInNAV blocks: earliest start, latest end, summed mtm.
    nav = None
    cns = root.findall(".//ChangeInNAV")
    if cns:
        starts = [_f(c.attrib.get("startingValue")) for c in cns if _f(c.attrib.get("startingValue")) is not None]
        ends = [_f(c.attrib.get("endingValue")) for c in cns if _f(c.attrib.get("endingValue")) is not None]
        nav = {
            "start": starts[0] if starts else None, "end": ends[-1] if ends else None,
            "realized": _sum(c.attrib.get("realizedPnl") for c in cns),
            "mtm": _sum(c.attrib.get("mtm") for c in cns),
            "deposits": _sum(c.attrib.get("depositsWithdrawals") for c in cns),
            "commissions": _sum(c.attrib.get("commissions") for c in cns),
        }

    # Overall period from the statement date attributes.
    froms = sorted(s.get("fromDate", "") for s in statements if s.get("fromDate"))
    tos = sorted(s.get("toDate", "") for s in statements if s.get("toDate"))
    return {
        "configured": True, "ok": True,
        "account": statements[0].get("accountId", ""),
        "from": froms[0] if froms else "", "to": tos[-1] if tos else "",
        "nav": nav, "navDays": nav_days, "trades": trades,
    }


def _sum(vals) -> float:
    total, any_ = 0.0, False
    for v in vals:
        f = _f(v)
        if f is not None:
            total += f; any_ = True
    return round(total, 2) if any_ else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _user_cache_read(user_id: int):
    try:
        with _engine.connect() as c:
            r = c.execute(text("SELECT extract(epoch FROM fetched_at) ts, payload "
                               "FROM flex_cache_user WHERE user_id = :u"),
                          {"u": user_id}).mappings().first()
        return (float(r["ts"]), r["payload"]) if r and r["payload"] else None
    except Exception as e:
        log.warning("flex user cache read failed", extra={"error": str(e)})
        return None


def _user_cache_write(user_id: int, payload: dict) -> None:
    try:
        with _engine.begin() as c:
            c.execute(text(
                "INSERT INTO flex_cache_user (user_id, fetched_at, payload) "
                "VALUES (:u, now(), :p) ON CONFLICT (user_id) DO UPDATE "
                "SET fetched_at = now(), payload = EXCLUDED.payload"),
                {"u": user_id, "p": json.dumps(payload)})
    except Exception as e:
        log.warning("flex user cache write failed", extra={"error": str(e)})


def _refresh_user(user_id: int, token: str, query_id: str) -> None:
    """Fetch and re-cache one user's statement. Runs after the response has been sent."""
    if user_id in _refreshing:
        return
    _refreshing.add(user_id)
    try:
        result = _fetch(token, query_id)
        if result.get("ok"):
            _user_cache_write(user_id, result)
        else:
            log.warning("Flex background refresh rejected: %s", result.get("error"))
    except Exception as e:              # noqa: BLE001 - a refresh must never break a request
        log.warning("Flex background refresh failed: %s", e)
    finally:
        _refreshing.discard(user_id)


def build_router(creds_dep):
    """Built with the credentials dependency injected, so FastAPI can resolve it at
    definition time and this module stays independent of the auth implementation."""
    router = APIRouter(prefix="/flex", tags=["flex"])

    @router.get("/status")
    def status(creds: dict = Depends(creds_dep)) -> dict:
        return {"configured": bool(creds.get("flex_token") and creds.get("flex_query_id"))}

    @router.get("/data")
    def data(bg: BackgroundTasks, refresh: bool = False,
             creds: dict = Depends(creds_dep)) -> dict:
        """Stale-while-revalidate.

        A statement is ~30 MB and takes ten seconds on a good day, far longer when IBKR
        throttles. Blocking the page on that made it look empty, so anything already
        cached is served immediately and refreshed behind the response. Only a user with
        no cached statement at all — or one who explicitly asked to refresh — waits.
        """
        token, query_id = creds.get("flex_token"), creds.get("flex_query_id")
        uid = creds["user_id"]
        if not (token and query_id):
            return {"configured": False, "ok": False,
                    "error": "Add your IBKR Flex token and query ID in Settings to see your account.",
                    "trades": []}
        now = time.time()
        if not refresh:
            cached = _user_cache_read(uid)
            if cached:
                if now - cached[0] >= CACHE_TTL:
                    bg.add_task(_refresh_user, uid, token, query_id)
                return cached[1]
        try:
            result = _fetch(token, query_id)
        except Exception as e:              # network / parse failure
            # The message itself carries the error: extra={} is invisible under the
            # default log configuration, which made this line useless to debug.
            log.warning("Flex fetch failed for user %s: %s", uid, e)
            result = {"configured": True, "ok": False, "error": str(e), "trades": []}
        if result.get("ok"):
            _user_cache_write(uid, result)
            return result
        # Fetch failed (rate-limited, network) — serve this user's last good statement.
        stale = _user_cache_read(uid)
        return stale[1] if stale else result

    return router
