"""IBKR Flex Web Service integration — REAL account statement data (trades + NAV).

This is the supported way to pull real historical account data programmatically from IBKR.
Setup (done once by the user in Account Management):
  1. Reporting → Settings → Flex Web Service: enable it, generate a TOKEN.
  2. Reporting → Flex Queries → Activity Flex Query: include the sections
     "Trades" and "Change in NAV"; set a wide period (e.g. Last 365 Days). Note the QUERY ID.
  3. Put FLEX_TOKEN and FLEX_QUERY_ID in .env.

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

from fastapi import APIRouter
from sqlalchemy import create_engine, text

log = logging.getLogger("flex")
router = APIRouter(prefix="/flex", tags=["flex"])

TOKEN = os.getenv("FLEX_TOKEN", "")
QUERY_ID = os.getenv("FLEX_QUERY_ID", "")
BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
CACHE_TTL = 1800           # seconds; Flex is rate-limited, don't hammer it
_cache: dict = {"ts": 0, "data": None}

# Durable cache in Postgres so the big statement survives api restarts (and Flex is rarely hit).
_engine = create_engine(os.getenv("DB_DSN", "postgresql+psycopg://condor:condor@postgres:5432/condor"),
                        future=True, pool_pre_ping=True)


def ensure_cache_table() -> None:
    try:
        with _engine.begin() as c:
            c.execute(text("CREATE TABLE IF NOT EXISTS flex_cache "
                           "(id int PRIMARY KEY, fetched_at timestamptz DEFAULT now(), payload jsonb)"))
    except Exception as e:
        log.warning("flex_cache table init failed", extra={"error": str(e)})


def _db_read() -> tuple[float, dict] | None:
    try:
        with _engine.connect() as c:
            row = c.execute(text("SELECT extract(epoch from fetched_at) AS ts, payload "
                                 "FROM flex_cache WHERE id = 1")).mappings().first()
        if row and row["payload"]:
            return float(row["ts"]), row["payload"]
    except Exception as e:
        log.warning("flex_cache read failed", extra={"error": str(e)})
    return None


def _db_write(payload: dict) -> None:
    try:
        with _engine.begin() as c:
            c.execute(text("INSERT INTO flex_cache (id, fetched_at, payload) VALUES (1, now(), :p) "
                           "ON CONFLICT (id) DO UPDATE SET fetched_at = now(), payload = :p"),
                      {"p": json.dumps(payload)})
    except Exception as e:
        log.warning("flex_cache write failed", extra={"error": str(e)})


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "condor-bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _fetch() -> dict:
    """Run the two-step Flex flow and parse. Returns a structured dict."""
    send = f"{BASE}/SendRequest?" + urllib.parse.urlencode({"t": TOKEN, "q": QUERY_ID, "v": "3"})
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
        got = f"{base_url}?" + urllib.parse.urlencode({"t": TOKEN, "q": ref, "v": "3"})
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


@router.get("/status")
def status() -> dict:
    return {"configured": bool(TOKEN and QUERY_ID)}


@router.get("/data")
def data(refresh: bool = False) -> dict:
    if not (TOKEN and QUERY_ID):
        return {"configured": False, "ok": False,
                "error": "Flex not configured — set FLEX_TOKEN and FLEX_QUERY_ID.", "trades": []}
    now = time.time()
    if not refresh and _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]
    # Warm from the durable Postgres cache (survives restarts) before hitting Flex.
    if not refresh:
        db = _db_read()
        if db and now - db[0] < CACHE_TTL:
            _cache.update(ts=db[0], data=db[1])
            return db[1]
    try:
        result = _fetch()
    except Exception as e:              # network / parse failure
        log.warning("Flex fetch failed", extra={"error": str(e)})
        result = {"configured": True, "ok": False, "error": str(e), "trades": []}
    if result.get("ok"):
        _cache.update(ts=now, data=result)
        _db_write(result)
        return result
    # Fetch failed (e.g. rate-limited) — serve the last good data (memory, then DB).
    if _cache["data"]:
        return _cache["data"]
    db = _db_read()
    if db:
        _cache.update(ts=db[0], data=db[1])
        return db[1]
    return result
