"""Feature construction.

The one rule: **no value at time t may use information from after t.** A
lookahead bug in a feature invalidates every regime label downstream, and it is
the single easiest way to produce an impressive-looking result that means
nothing. Monthly macro is therefore shifted by an explicit publication lag
(config.PUB_LAG_DAYS) before it is broadcast to daily.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .universe import SECTORS, UNIVERSE

TRADING_DAYS = 252


def _lag_to_daily(s: pd.Series, lag_days: int, daily_index: pd.DatetimeIndex) -> pd.Series:
    """Shift a monthly series to its release date, then hold it flat forward."""
    shifted = pd.Series(s.values, index=pd.DatetimeIndex(s.index) + pd.Timedelta(days=lag_days))
    shifted = shifted[~shifted.index.duplicated(keep="last")].sort_index()
    joined = shifted.reindex(shifted.index.union(daily_index)).sort_index().ffill()
    return joined.reindex(daily_index)


def sector_indices(prices: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight index per sector, rebased to 100.

    Built from mean daily returns rather than mean prices so that a name
    joining late (Horizon Robotics, CATL's HK line) does not create a step
    change in the index.
    """
    out = {}
    for key in SECTORS:
        cols = [n.ticker for n in UNIVERSE
                if n.sector == key and n.ticker in prices.columns]
        if not cols:
            continue
        # fill_method is pinned explicitly: pandas 2.x forward-filled by
        # default, 3.x does not. Left implicit, the same code produces
        # different sector indices on the laptop and on the CI runner.
        rets = prices[cols].pct_change(fill_method=None)
        idx = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod() * 100
        out[key] = idx
    return pd.DataFrame(out)


def breadth(prices: pd.DataFrame, window: int = 50) -> pd.Series:
    """Share of the universe trading above its own N-day moving average.

    A blunt instrument, but it moves early and it is not derivable from the
    index level alone — which is exactly what you want alongside a benchmark
    return in a regime model.

    The forward-fill matters more than it looks. HK, US and mainland calendars
    do not align, so the raw panel is peppered with holiday NaNs; a strict
    `min_periods=window` rolling mean then returns NaN for essentially every
    window that contains one, and breadth silently collapses to zero. Filling
    each name with its own last traded price first is both correct (that *is*
    the last price) and causal — ffill only ever looks backwards, and leading
    NaNs before a name's first print are left alone so pre-IPO history is not
    invented.
    """
    px = prices.ffill()
    ma = px.rolling(window, min_periods=max(5, window // 2)).mean()
    valid = (px.notna() & ma.notna())
    above = (px > ma) & valid
    return above.sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)


def build(prices: pd.DataFrame,
          csi300: pd.Series,
          macro: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Assemble the weekly feature matrix.

    Returns (features, notes) where notes records any feature that could not be
    built, so the artifact can state its own gaps instead of hiding them.
    """
    notes: list[dict] = []
    csi300 = csi300.sort_index()
    daily = pd.DatetimeIndex(csi300.index)

    logret = np.log(csi300).diff()

    feats = pd.DataFrame(index=daily)
    feats["ret_4w"] = np.log(csi300).diff(20)
    feats["realized_vol"] = logret.rolling(20, min_periods=20).std() * np.sqrt(TRADING_DAYS)
    feats["momentum_3m"] = np.log(csi300).diff(63)

    # Breadth comes off the HK/ADR universe while the benchmark is a mainland
    # index. They are different venues — that is a real limitation, stated in
    # the methodology, not something to paper over.
    b = breadth(prices)
    feats["breadth"] = b.reindex(daily).ffill()

    # --- macro ------------------------------------------------------------
    if "m2_yoy" in macro.columns:
        m2 = macro["m2_yoy"].dropna()
        # Credit impulse proper is the change in new credit flow as a share of
        # GDP. TSF is not reachable from this network, so this is the
        # second-derivative proxy: the 12-month change in M2 growth. Directionally
        # the same object, and it must be labelled as a proxy wherever shown.
        impulse = m2 - m2.shift(12)
        feats["credit_impulse"] = _lag_to_daily(impulse.dropna(), C.PUB_LAG_DAYS["m2"], daily)
        notes.append({"feature": "credit_impulse", "status": "PROXY",
                      "detail": "12m change in M2 YoY; TSF geo-blocked. "
                                f"Publication lag {C.PUB_LAG_DAYS['m2']}d applied."})
    else:
        notes.append({"feature": "credit_impulse", "status": "MISSING",
                      "detail": "M2 series unavailable"})

    if "pmi_mfg" in macro.columns:
        feats["pmi_gap"] = _lag_to_daily(macro["pmi_mfg"].dropna() - 50.0,
                                         C.PUB_LAG_DAYS["pmi"], daily)
    else:
        notes.append({"feature": "pmi_gap", "status": "MISSING",
                      "detail": "PMI series unavailable"})

    # A-H premium is specified in SCOPING.md but needs both legs; only the H
    # leg is reachable here. Left out rather than filled with nulls.
    notes.append({"feature": "ah_premium", "status": "UNAVAILABLE",
                  "detail": "requires A-share prices; geo-blocked on this "
                            "network (PHASE0_FINDINGS.md). Universe carries "
                            "a_share codes so it switches on when reachable."})

    # --- weekly ------------------------------------------------------------
    # Resampling to W-FRI labels each bin with the Friday that ends it, which
    # for the current partial week is a date in the future. Stamping a live
    # regime reading with a date that has not happened yet is indefensible, so
    # each bin is relabelled with the last date actually observed inside it.
    feats["_obs_date"] = feats.index
    weekly = feats.resample("W-FRI").last().dropna(subset=["_obs_date"])
    weekly.index = pd.DatetimeIndex(weekly.pop("_obs_date"))
    weekly.index.name = "date"

    weekly = weekly[weekly.index >= C.START_DATE]
    weekly = weekly.dropna()

    return weekly, notes
