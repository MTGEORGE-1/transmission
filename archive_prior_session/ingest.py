"""
Live data ingest.

Swaps in for demo_data.py once Phase 0 confirms your sources are reachable.
Same return signatures, so build.py needs no changes:

    generate_prices()  ->  DataFrame(index=date, columns=ticker)
    generate_macro()   ->  DataFrame(index=month_end, columns=[tsf_yoy, m2_yoy, pmi])

Run with:  python -m transmission.build --live

Caching is on by default. Chinese endpoints are rate-limited and occasionally
flaky, so every successful pull is written to cache/ as parquet and reused
until you pass refresh=True. Never let the dashboard depend on a live call.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .config import END_DATE, START_DATE, UNIVERSE

CACHE = Path(__file__).resolve().parent.parent / "cache"
CACHE.mkdir(exist_ok=True)


def _cached(name: str, fn, refresh: bool = False) -> pd.DataFrame:
    path = CACHE / f"{name}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    df = fn()
    if df is not None and len(df):
        df.to_parquet(path)
    return df


# ---------------------------------------------------------------------------
# Equities
# ---------------------------------------------------------------------------
def _akshare_a_share(ticker: str) -> pd.Series | None:
    """A-share daily close via AkShare. Ticker form: 002594.SZ / 688981.SS"""
    import akshare as ak

    code = ticker.split(".")[0]
    df = ak.stock_zh_a_hist(
        symbol=code, period="daily",
        start_date=START_DATE.replace("-", ""),
        end_date=END_DATE.replace("-", ""),
        adjust="qfq",                      # forward-adjusted; required for returns
    )
    if df is None or df.empty:
        return None
    df = df.rename(columns={"日期": "date", "收盘": "close"})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].rename(ticker)


def _yfinance_series(ticker: str) -> pd.Series | None:
    import yfinance as yf

    df = yf.download(ticker, start=START_DATE, end=END_DATE,
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    close = df["Close"]
    if isinstance(close, pd.DataFrame):     # yfinance returns MultiIndex for single tickers
        close = close.iloc[:, 0]
    return close.rename(ticker)


def _akshare_hk(ticker: str) -> pd.Series | None:
    """HK daily via AkShare — fallback when yfinance is unavailable."""
    import akshare as ak

    code = ticker.split(".")[0].zfill(5)
    df = ak.stock_hk_hist(symbol=code, period="daily",
                          start_date=START_DATE.replace("-", ""),
                          end_date=END_DATE.replace("-", ""),
                          adjust="qfq")
    if df is None or df.empty:
        return None
    df = df.rename(columns={"日期": "date", "收盘": "close"})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"].rename(ticker)


def generate_prices(refresh: bool = False, pause: float = 0.4) -> pd.DataFrame:
    def pull():
        series, failed = [], []
        for row in UNIVERSE:
            t, venue = row["ticker"], row["venue"]
            s = None
            try:
                if venue == "A":
                    s = _akshare_a_share(t)
                elif venue == "HK":
                    s = _yfinance_series(t) or _akshare_hk(t)
                else:
                    s = _yfinance_series(t)
            except Exception as e:
                print(f"  {t}: {type(e).__name__}: {str(e)[:90]}")

            if s is None or s.empty:
                failed.append(t)
                print(f"  {t}: NO DATA")
            else:
                series.append(s)
                print(f"  {t}: {len(s)} rows")
            time.sleep(pause)

        if not series:
            raise RuntimeError(
                "No price series retrieved. Run phase0_data_audit.py to diagnose "
                "before assuming this is a code problem."
            )
        if failed:
            print(f"\n  WARNING: {len(failed)} tickers missing: {', '.join(failed)}")
            print("  Sector indices will be computed on the survivors. "
                  "Document this in the validation page.")

        df = pd.concat(series, axis=1).sort_index()
        return df.loc[START_DATE:END_DATE].ffill().dropna(how="all")

    return _cached("prices", pull, refresh)


# ---------------------------------------------------------------------------
# Macro
# ---------------------------------------------------------------------------
def generate_macro(refresh: bool = False) -> pd.DataFrame:
    def pull():
        import akshare as ak

        frames = {}

        # Total social financing / money supply — the credit impulse input
        try:
            ms = ak.macro_china_money_supply()
            ms.columns = [str(c) for c in ms.columns]
            date_col = next(c for c in ms.columns if "月份" in c or "统计时间" in c)
            m2_col = next(c for c in ms.columns if "M2" in c and "同比" in c)
            ms["date"] = pd.to_datetime(ms[date_col].astype(str).str.replace("年", "-")
                                        .str.replace("月份", "").str.replace("月", ""),
                                        errors="coerce")
            frames["m2_yoy"] = ms.set_index("date")[m2_col].astype(float)
        except Exception as e:
            print(f"  money supply: {type(e).__name__}: {str(e)[:90]}")

        try:
            pmi = ak.macro_china_pmi()
            pmi.columns = [str(c) for c in pmi.columns]
            date_col = pmi.columns[0]
            pmi_col = next(c for c in pmi.columns if "制造业" in c and "指数" in c)
            pmi["date"] = pd.to_datetime(pmi[date_col].astype(str), errors="coerce")
            frames["pmi"] = pmi.set_index("date")[pmi_col].astype(float)
        except Exception as e:
            print(f"  pmi: {type(e).__name__}: {str(e)[:90]}")

        if not frames:
            raise RuntimeError("No macro series retrieved — check AkShare reachability.")

        df = pd.DataFrame(frames).sort_index()
        df = df.resample("ME").last().loc[START_DATE:END_DATE]

        # TSF YoY: AkShare's interface for this changes periodically. If the
        # dedicated series is unavailable, M2 growth is a serviceable proxy —
        # but say so on the validation page rather than passing it off as TSF.
        if "tsf_yoy" not in df.columns:
            print("  NOTE: TSF series unavailable; using M2 YoY as credit proxy.")
            df["tsf_yoy"] = df.get("m2_yoy")

        return df.interpolate().ffill().bfill()

    return _cached("macro", pull, refresh)
