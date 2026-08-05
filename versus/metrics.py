"""Comparison metrics: sector indices, growth rates, company tables.

The headline number throughout is **10-year growth**, measured as total return
(prices are split- and dividend-adjusted). Fundamentals sit behind it as
supporting evidence, on the shorter window the free data actually supports.

Index construction: equal-weight, built from the mean of available daily
returns rather than the mean of prices. That matters more than it sounds here.
Half the Chinese basket listed after 2020 — Li Auto and XPeng in 2021, Horizon
Robotics in 2024 — and averaging price levels would create a step change on
every new listing. Averaging returns lets a name simply join the index on its
first trading day.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .sectors import SECTORS

TRADING_DAYS = 252


def _cagr(s: pd.Series) -> tuple[float | None, float]:
    """Compound annual growth rate and the window length in years."""
    s = s.dropna()
    if len(s) < 2:
        return None, 0.0
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    if yrs < 0.5 or s.iloc[0] <= 0:
        return None, yrs
    return (float(s.iloc[-1]) / float(s.iloc[0])) ** (1 / yrs) - 1, yrs


def build_index(prices: pd.DataFrame, tickers: list[str]) -> pd.Series:
    """Equal-weight total-return index for a basket, rebased to 100."""
    cols = [t for t in tickers if t in prices.columns]
    if not cols:
        return pd.Series(dtype=float)
    rets = prices[cols].pct_change(fill_method=None)
    # Require two live names before the index starts, so it does not open on a
    # single volatile constituent.
    live = prices[cols].notna().sum(axis=1)
    mean_ret = rets.mean(axis=1, skipna=True).where(live >= 2)
    first = mean_ret.first_valid_index()
    if first is None:
        return pd.Series(dtype=float)
    mean_ret = mean_ret.loc[first:].fillna(0)
    return (1 + mean_ret).cumprod() * 100


def constituent_count(prices: pd.DataFrame, tickers: list[str]) -> pd.Series:
    cols = [t for t in tickers if t in prices.columns]
    return prices[cols].notna().sum(axis=1) if cols else pd.Series(dtype=int)


def company_row(t: str, name: str, country: str,
                prices: pd.DataFrame, fund: dict) -> dict:
    f = fund.get(t, {})
    s = prices[t].dropna() if t in prices.columns else pd.Series(dtype=float)

    cagr, yrs = _cagr(s)
    total_ret = (float(s.iloc[-1]) / float(s.iloc[0]) - 1) if len(s) >= 2 else None

    # Volatility, annualised — the risk side of the growth number.
    vol = None
    if len(s) > 30:
        vol = float(np.log(s).diff().std() * np.sqrt(TRADING_DAYS))

    return {
        "ticker": t,
        "name": f.get("name") or name,
        "label": name,
        "country": country,
        "market_cap_usd": f.get("market_cap_usd"),
        "revenue_usd": f.get("revenue_usd"),
        "pe": f.get("pe"),
        "profit_margin": f.get("profit_margin"),
        "gross_margin": f.get("gross_margin"),
        "capex_usd": f.get("capex_usd"),
        "capex_intensity": f.get("capex_intensity"),
        "revenue_cagr": f.get("revenue_cagr"),
        "revenue_cagr_years": f.get("revenue_cagr_years"),
        "revenue_growth_yoy": f.get("revenue_growth_yoy"),
        "price_cagr": cagr,
        "price_years": round(yrs, 1),
        "total_return": total_ret,
        "volatility": vol,
        "listed_from": str(s.index[0].date()) if len(s) else None,
        "full_history": yrs >= 9.5,
    }


def _agg(rows: list[dict]) -> dict:
    """Sector-level aggregates. Sums for size, medians for ratios — a median
    margin is not distorted by one loss-making name the way a mean is."""
    def total(k):
        vals = [r[k] for r in rows if r.get(k)]
        return sum(vals) if vals else None

    def median(k):
        vals = [r[k] for r in rows if r.get(k) is not None]
        return float(np.median(vals)) if vals else None

    mcap = total("market_cap_usd")
    rev = total("revenue_usd")
    capex = total("capex_usd")
    return {
        "n": len(rows),
        "market_cap_usd": mcap,
        "revenue_usd": rev,
        "capex_usd": capex,
        "capex_intensity": (capex / rev) if (capex and rev) else None,
        "median_price_cagr": median("price_cagr"),
        "median_revenue_cagr": median("revenue_cagr"),
        "median_profit_margin": median("profit_margin"),
        "median_pe": median("pe"),
        "median_volatility": median("volatility"),
        "n_full_history": sum(1 for r in rows if r["full_history"]),
    }


def build(prices: pd.DataFrame, fund: dict) -> dict:
    """Everything the front end needs, sector by sector."""
    out = {}
    for key, spec in SECTORS.items():
        side_data = {}
        for side in ("cn", "us"):
            cos = spec[side]
            idx = build_index(prices, [c.ticker for c in cos])
            cagr, yrs = _cagr(idx)
            rows = [company_row(c.ticker, c.name, c.country, prices, fund) for c in cos]
            rows.sort(key=lambda r: r["market_cap_usd"] or 0, reverse=True)

            side_data[side] = {
                "index": idx,
                "index_cagr": cagr,
                "index_years": round(yrs, 1),
                "index_total_return": (float(idx.iloc[-1]) / 100 - 1) if len(idx) else None,
                "companies": rows,
                "aggregate": _agg(rows),
            }

        out[key] = {
            "label": spec["label"],
            "blurb": spec["blurb"],
            **side_data,
        }
    return out
