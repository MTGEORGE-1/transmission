"""
Feature construction.

Everything here is causal — no value at time t uses information from after t.
That discipline is what makes the regime output defensible; a lookahead bug in
a feature invalidates every backtest downstream.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SECTORS, UNIVERSE


def sector_indices(prices: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight total-return index per sector, rebased to 100."""
    out = {}
    for s in SECTORS:
        cols = [u["ticker"] for u in UNIVERSE
                if u["sector"] == s and u["ticker"] in prices.columns]
        ret = prices[cols].pct_change().mean(axis=1)
        out[s] = 100 * (1 + ret.fillna(0)).cumprod()
    return pd.DataFrame(out, index=prices.index)


def market_index(prices: pd.DataFrame) -> pd.Series:
    ret = prices.pct_change().mean(axis=1)
    return 100 * (1 + ret.fillna(0)).cumprod()


def credit_impulse(macro: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    """
    Credit impulse: the *change* in credit growth, not the level.

    The level of TSF growth tells you little; the second derivative is what
    leads cyclical activity. Standard construction is the 12-month change in
    the credit-to-GDP flow. With TSF YoY as the input we use its 12-month
    difference, z-scored.

    China's credit impulse historically leads global cyclicals by roughly
    6-9 months, which is the single most forecastable relationship available
    in this dataset.
    """
    ci = macro["tsf_yoy"].diff(12)
    z = (ci - ci.expanding(min_periods=24).mean()) / ci.expanding(min_periods=24).std()
    return z.reindex(dates, method="ffill").fillna(0.0).rename("credit_impulse")


def realized_vol(prices: pd.DataFrame, window: int = 21) -> pd.Series:
    ret = prices.pct_change().mean(axis=1)
    return (ret.rolling(window).std() * np.sqrt(252)).bfill().rename("realized_vol")


def breadth(prices: pd.DataFrame, window: int = 63) -> pd.Series:
    """Share of names above their own 63-day moving average."""
    ma = prices.rolling(window).mean()
    above = (prices > ma).sum(axis=1) / prices.notna().sum(axis=1)
    return above.fillna(0.5).rename("breadth")


def ah_premium(prices: pd.DataFrame) -> pd.Series:
    """
    Mean A-share premium over the matched H-share listing.

    Same company, same cash flows, two prices — the gap is close to a pure
    read on mainland retail sentiment versus offshore institutional pricing.
    Mean-reverting, and free.

    Note: a correct implementation must convert HKD to CNY. This version works
    on rebased index levels, which is fine for the demo but MUST be replaced
    with FX-adjusted absolute prices when live data lands.
    """
    pairs = [(u["ticker"], u["ah_pair"]) for u in UNIVERSE
             if u["venue"] == "A" and u["ah_pair"]
             and u["ticker"] in prices.columns and u["ah_pair"] in prices.columns]
    if not pairs:
        return pd.Series(0.0, index=prices.index, name="ah_premium")

    prem = pd.DataFrame({
        a: prices[a] / prices[h] - 1 for a, h in pairs
    }, index=prices.index)
    return prem.mean(axis=1).rename("ah_premium")


def momentum(prices: pd.DataFrame, window: int = 63) -> pd.Series:
    idx = market_index(prices)
    return (idx / idx.shift(window) - 1).fillna(0.0).rename("momentum_3m")


def valuation_z(prices: pd.DataFrame, window: int = 252 * 3) -> pd.DataFrame:
    """
    Price z-score against a 3-year trailing window, per sector.

    A stand-in for a real valuation z-score. When live fundamentals land,
    replace with P/E or EV/Sales versus own history — the interface stays
    the same.
    """
    si = sector_indices(prices)
    mean = si.rolling(window, min_periods=252).mean()
    std = si.rolling(window, min_periods=252).std()
    return ((si - mean) / std).fillna(0.0)


def build_feature_panel(prices: pd.DataFrame, macro: pd.DataFrame,
                        stance: pd.DataFrame) -> pd.DataFrame:
    """Assemble everything the regime model consumes."""
    df = pd.concat([
        credit_impulse(macro, prices.index),
        realized_vol(prices),
        breadth(prices),
        ah_premium(prices),
        momentum(prices),
    ], axis=1)

    df["policy_stance"] = stance["policy_stance"].reindex(df.index).ffill().fillna(0.0)
    for s in SECTORS:
        df[f"stance_{s}"] = stance[f"stance_{s}"].reindex(df.index).ffill().fillna(0.0)
    df["stance_monetary"] = stance["stance_monetary"].reindex(df.index).ffill().fillna(0.0)

    return df.dropna()
