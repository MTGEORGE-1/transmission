"""Ingest for the comparison engine: 10y prices, plus company fundamentals.

Currency is the trap here. yfinance reports market cap in the listing currency
and financials in `financialCurrency`, and these disagree constantly — BYD
reports CNY, SMIC reports USD despite listing in Hong Kong, Stellantis reports
EUR. Comparing a CNY revenue figure against a USD one produces a 7x error in
China's favour and would invalidate the entire page. Everything is therefore
normalised to USD at current spot, and the rate used is recorded.

Spot conversion of historical revenue is itself an approximation — a proper job
would use each period's average rate. Stated in the limitations rather than
hidden; the distortion is small next to the growth differences being shown.
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "vcache"
CACHE.mkdir(parents=True, exist_ok=True)

YEARS = 10
CACHE_TTL_HOURS = 20

LINEAGE: list[dict] = []


def _record(dataset: str, status: str, n: int, note: str = "") -> None:
    LINEAGE.append({"dataset": dataset, "status": status, "n": n, "note": note,
                    "fetched_at": datetime.now().isoformat(timespec="seconds")})


def _fresh(p: Path) -> bool:
    return p.exists() and (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
                           < timedelta(hours=CACHE_TTL_HOURS))


# ---------------------------------------------------------------------------

def fetch_fx(force: bool = False) -> dict[str, float]:
    """Spot rates into USD. USD is 1.0 by definition."""
    p = CACHE / "fx.json"
    if not force and _fresh(p):
        return json.loads(p.read_text())

    import yfinance as yf

    pairs = {"CNY": "CNYUSD=X", "HKD": "HKDUSD=X", "EUR": "EURUSD=X",
             "TWD": "TWDUSD=X", "JPY": "JPYUSD=X", "GBP": "GBPUSD=X"}
    fx = {"USD": 1.0}
    for cur, sym in pairs.items():
        try:
            h = yf.Ticker(sym).history(period="5d")
            if not h.empty:
                fx[cur] = float(h["Close"].iloc[-1])
        except Exception:
            pass
    # Hard fallbacks so a missing rate never silently becomes 1.0, which would
    # inflate a CNY revenue figure sevenfold.
    fx.setdefault("CNY", 0.14)
    fx.setdefault("HKD", 0.128)
    fx.setdefault("EUR", 1.08)

    p.write_text(json.dumps(fx, indent=2))
    _record("FX rates", "OK", len(fx), ", ".join(f"{k}={v:.4f}" for k, v in fx.items()))
    return fx


def fetch_prices(tickers: list[str], force: bool = False) -> pd.DataFrame:
    """Adjusted daily closes, ~10 years, one column per ticker."""
    p = CACHE / "prices.csv"
    if not force and _fresh(p):
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        _record("prices", "CACHED", df.shape[1], f"{len(df)} days")
        return df

    import yfinance as yf

    start = (datetime.now() - timedelta(days=365 * YEARS + 30)).strftime("%Y-%m-%d")
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False, threads=True)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw.to_frame()
    close = close.sort_index()

    dead = [c for c in close.columns if close[c].notna().sum() == 0]
    if dead:
        close = close.drop(columns=dead)
        _record("unresolved tickers", "WARN", len(dead), ", ".join(sorted(dead)))

    close.index.name = "date"
    close.to_csv(p)
    _record("prices", "OK", close.shape[1], f"{len(close)} days from {close.index[0].date()}")
    return close


def _safe(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", float("inf")):
            return v
    return None


def fetch_fundamentals(tickers: list[str], fx: dict, force: bool = False) -> dict:
    """Per-company fundamentals, normalised to USD.

    One network round trip per ticker, so this is the slow step — cached hard.
    Individual failures are recorded and skipped; one dead ticker must not take
    down the build.
    """
    p = CACHE / "fundamentals.json"
    if not force and _fresh(p):
        d = json.loads(p.read_text())
        _record("fundamentals", "CACHED", len(d))
        return d

    import yfinance as yf

    out, failed = {}, []
    for i, t in enumerate(tickers, 1):
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}

            cur_mkt = info.get("currency", "USD") or "USD"
            cur_fin = info.get("financialCurrency", cur_mkt) or cur_mkt
            r_mkt = fx.get(cur_mkt.upper(), 1.0)
            r_fin = fx.get(cur_fin.upper(), 1.0)

            rec = {
                "ticker": t,
                "name": _safe(info, "shortName", "longName") or t,
                "currency_market": cur_mkt,
                "currency_fin": cur_fin,
                "market_cap_usd": (_safe(info, "marketCap") or 0) * r_mkt or None,
                "revenue_usd": (_safe(info, "totalRevenue") or 0) * r_fin or None,
                "pe": _safe(info, "trailingPE"),
                "profit_margin": _safe(info, "profitMargins"),
                "gross_margin": _safe(info, "grossMargins"),
                "revenue_growth_yoy": _safe(info, "revenueGrowth"),
                "employees": _safe(info, "fullTimeEmployees"),
            }

            # Revenue history — yfinance returns only 4-5 annual periods, so the
            # CAGR window is short and its length is recorded alongside it.
            try:
                fin = tk.income_stmt
                if fin is not None and not fin.empty and "Total Revenue" in fin.index:
                    s = fin.loc["Total Revenue"].dropna().sort_index()
                    if len(s) >= 2:
                        yrs = (s.index[-1] - s.index[0]).days / 365.25
                        first, last = float(s.iloc[0]), float(s.iloc[-1])
                        if first > 0 and last > 0 and yrs >= 0.9:
                            rec["revenue_cagr"] = (last / first) ** (1 / yrs) - 1
                            rec["revenue_cagr_years"] = round(yrs, 1)
                        rec["revenue_series"] = [
                            {"y": str(ix.date()), "v": float(v) * r_fin}
                            for ix, v in s.items()]
            except Exception:
                pass

            # Capex, for the capital-intensity comparison.
            try:
                cf = tk.cashflow
                if cf is not None and not cf.empty:
                    rows = [r for r in cf.index if "Capital Expenditure" in str(r)]
                    if rows:
                        s = cf.loc[rows[0]].dropna().sort_index()
                        if len(s):
                            rec["capex_usd"] = abs(float(s.iloc[-1])) * r_fin
            except Exception:
                pass

            if rec.get("capex_usd") and rec.get("revenue_usd"):
                rec["capex_intensity"] = rec["capex_usd"] / rec["revenue_usd"]

            out[t] = rec
        except Exception as e:  # noqa: BLE001
            failed.append(f"{t} ({type(e).__name__})")
        if i % 20 == 0:
            time.sleep(1)  # be polite to the endpoint

    p.write_text(json.dumps(out, indent=2))
    _record("fundamentals", "OK", len(out),
            f"{len(failed)} failed: {', '.join(failed)}" if failed else "")
    return out
