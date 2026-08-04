"""Ingest layer.

Three jobs, in priority order:

1. **Never silently fabricate.** Every fetch is recorded in a lineage log with
   its source, row count, date span and status. If a source fails, the artifact
   says so; nothing is filled in behind your back.
2. **Never trust a 200.** The firewall on this network returns HTTP 200 with a
   "Connection denied by Geolocation" block page. Parsed naively that becomes
   garbage rows. `_guard_blockpage` fails loudly instead.
3. **Cache hard.** Chinese endpoints are flaky — a transient
   ChunkedEncodingError hit CPI during development. Re-running the pipeline
   must not depend on the network cooperating twice.

Caches are CSV rather than Parquet on purpose: no pyarrow dependency, and the
cache stays greppable when a number looks wrong.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

import pandas as pd

from . import config as C
from .universe import BENCHMARKS, tickers

LINEAGE: list[dict] = []


def _record(source: str, dataset: str, status: str, rows: int,
            span: str = "", note: str = "") -> None:
    LINEAGE.append({
        "source": source,
        "dataset": dataset,
        "status": status,
        "rows": rows,
        "span": span,
        "note": note,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    })


def _guard_blockpage(text: str, where: str) -> None:
    for marker in C.BLOCKPAGE_MARKERS:
        if marker in text:
            raise RuntimeError(
                f"{where}: firewall block page received instead of data "
                f"(marker {marker!r}). See PHASE0_FINDINGS.md."
            )


def _cache_file(key: str):
    return C.CACHE / f"{key}.csv"


def _cache_fresh(key: str) -> bool:
    p = _cache_file(key)
    if not p.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    return age < timedelta(hours=C.CACHE_TTL_HOURS)


def _read_cache(key: str) -> pd.DataFrame:
    return pd.read_csv(_cache_file(key), index_col=0, parse_dates=True)


def _write_cache(key: str, df: pd.DataFrame) -> None:
    df.to_csv(_cache_file(key))


def _retry(fn, what: str):
    """Run `fn` with backoff. Chinese endpoints fail transiently far more
    often than they fail permanently."""
    last = None
    for attempt in range(1, C.HTTP_RETRIES + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — we genuinely want any failure
            last = e
            if attempt < C.HTTP_RETRIES:
                time.sleep(C.RETRY_BACKOFF_SEC * attempt)
    raise RuntimeError(f"{what} failed after {C.HTTP_RETRIES} attempts: {last}") from last


def _span(idx: pd.Index) -> str:
    if len(idx) == 0:
        return ""
    return f"{pd.Timestamp(idx[0]).date()} → {pd.Timestamp(idx[-1]).date()}"


# ---------------------------------------------------------------------------
# Equity prices — yfinance (HK + ADR). The working backbone.
# ---------------------------------------------------------------------------

def fetch_prices(force: bool = False) -> pd.DataFrame:
    """Adjusted daily closes for the universe, one column per ticker."""
    key = "prices"
    if not force and _cache_fresh(key):
        df = _read_cache(key)
        _record("cache", "equity prices", "CACHED", len(df), _span(df.index))
        return df

    import yfinance as yf

    syms = tickers()

    def _dl():
        return yf.download(syms, start=C.START_DATE, auto_adjust=True,
                           progress=False, threads=True)

    raw = _retry(_dl, "yfinance universe download")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    close = close.sort_index()

    # A ticker that returned nothing is a curation error (bad symbol), not a
    # market fact. Drop it, but say so.
    empty = [c for c in close.columns if close[c].notna().sum() == 0]
    if empty:
        close = close.drop(columns=empty)
        _record("yfinance", "unresolved tickers", "WARN", len(empty),
                note="no data returned: " + ", ".join(sorted(empty)))

    close.index.name = "date"
    _write_cache(key, close)
    _record("yfinance", "equity prices", "OK", len(close), _span(close.index),
            f"{close.shape[1]} tickers resolved")
    return close


def fetch_benchmark_yf(key_name: str, force: bool = False) -> pd.Series:
    """A single yfinance benchmark series."""
    spec = BENCHMARKS[key_name]
    key = f"bench_{key_name}"
    if not force and _cache_fresh(key):
        s = _read_cache(key).iloc[:, 0]
        _record("cache", spec["label"], "CACHED", len(s), _span(s.index))
        return s

    import yfinance as yf

    def _dl():
        return yf.download(spec["symbol"], start=C.START_DATE,
                           auto_adjust=True, progress=False)

    raw = _retry(_dl, f"yfinance {spec['symbol']}")
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna().sort_index()
    close.name = key_name
    close.index.name = "date"

    if close.empty:
        _record("yfinance", spec["label"], "EMPTY", 0,
                note=f"symbol {spec['symbol']} returned no rows")
        return close

    _write_cache(key, close.to_frame())
    _record("yfinance", spec["label"], "OK", len(close), _span(close.index))
    return close


# ---------------------------------------------------------------------------
# CSI 300 — akshare. Primary benchmark for the regime bands.
# ---------------------------------------------------------------------------

def fetch_csi300(force: bool = False) -> pd.Series:
    key = "csi300"
    if not force and _cache_fresh(key):
        s = _read_cache(key).iloc[:, 0]
        _record("cache", "CSI 300", "CACHED", len(s), _span(s.index))
        return s

    import akshare as ak

    df = _retry(lambda: ak.stock_zh_index_daily(symbol=BENCHMARKS["csi300"]["symbol"]),
                "akshare CSI 300")
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["close"].sort_index()
    s = s[s.index >= C.START_DATE]
    s.name = "csi300"

    _write_cache(key, s.to_frame())
    _record("akshare", "CSI 300", "OK", len(s), _span(s.index))
    return s


# ---------------------------------------------------------------------------
# Macro — akshare. Reachable because these sit on different hosts to EastMoney.
# ---------------------------------------------------------------------------

def _parse_cn_month(col: pd.Series) -> pd.Series:
    """'2026年06月份' → Timestamp('2026-06-01')."""
    cleaned = (col.astype(str)
                  .str.replace("年", "-", regex=False)
                  .str.replace("月份", "", regex=False)
                  .str.replace("月", "", regex=False)
                  .str.strip())
    return pd.to_datetime(cleaned + "-01", errors="coerce")


def fetch_macro(force: bool = False) -> pd.DataFrame:
    """Monthly macro, indexed by the month the data *describes*.

    Publication lag is applied later, in features.py — keeping the raw index
    honest means the lag stays visible and adjustable rather than baked in.
    """
    key = "macro"
    if not force and _cache_fresh(key):
        df = _read_cache(key)
        _record("cache", "macro (M2, PMI)", "CACHED", len(df), _span(df.index))
        return df

    import akshare as ak

    frames = {}

    def _m2():
        d = ak.macro_china_money_supply()
        idx = _parse_cn_month(d["月份"])
        return pd.Series(pd.to_numeric(d["货币和准货币(M2)-同比增长"], errors="coerce").values,
                         index=idx, name="m2_yoy").dropna().sort_index()

    def _pmi():
        d = ak.macro_china_pmi()
        idx = _parse_cn_month(d["月份"])
        return pd.Series(pd.to_numeric(d["制造业-指数"], errors="coerce").values,
                         index=idx, name="pmi_mfg").dropna().sort_index()

    for name, fn in (("m2_yoy", _m2), ("pmi_mfg", _pmi)):
        try:
            s = _retry(fn, f"akshare {name}")
            frames[name] = s
            _record("akshare", name, "OK", len(s), _span(s.index))
        except Exception as e:  # noqa: BLE001
            _record("akshare", name, "FAIL", 0, note=str(e)[:160])

    if not frames:
        raise RuntimeError("no macro series available — cannot build features")

    df = pd.concat(frames.values(), axis=1).sort_index()
    df = df[df.index >= pd.Timestamp("2005-01-01")]
    df.index.name = "month"
    _write_cache(key, df)
    return df


# ---------------------------------------------------------------------------

def write_lineage() -> None:
    """Data lineage — every number traceable to a source and a timestamp
    (SCOPING.md §6, the credibility move)."""
    path = C.ARTIFACTS / "lineage.json"
    path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "entries": LINEAGE,
    }, indent=2, ensure_ascii=False))
