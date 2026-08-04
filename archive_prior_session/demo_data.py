"""
Demo data generator.

>>> THIS IS SYNTHETIC DATA. IT IS NOT REAL MARKET DATA. <<<

Its only job is to let the full pipeline and dashboard run end-to-end before
the live ingest is wired up. Every artifact generated from it is stamped
`"data_source": "SYNTHETIC"` so a demo can never be mistaken for a result.

It is not random noise, though. Price paths are driven by a hand-coded timeline
of real Chinese market regimes (2015 crash, 2018 trade war, 2021 crackdown,
2022 export controls, 2024 stimulus, 2025 DeepSeek, 2026 price war) with
plausible drift and volatility per sector in each period. That way the regime
model has genuine structure to find and the dashboard shows a realistic shape.

Replace with ingest.py output as soon as Phase 0 confirms your data sources.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import END_DATE, START_DATE, UNIVERSE

# (start, end, label, {sector: (annual drift, annual vol)}, breadth, credit impulse)
REGIME_TIMELINE = [
    ("2015-01-01", "2015-06-12", "leverage melt-up",
     dict(ev_auto=(1.40, 0.42), semis_ai=(1.80, 0.50), fintech_consumer=(1.20, 0.40)), 0.86, 1.8),
    ("2015-06-12", "2016-02-29", "crash and rescue",
     dict(ev_auto=(-0.70, 0.62), semis_ai=(-0.80, 0.70), fintech_consumer=(-0.65, 0.58)), 0.14, 0.9),
    ("2016-03-01", "2017-12-31", "reflation grind",
     dict(ev_auto=(0.16, 0.26), semis_ai=(0.22, 0.31), fintech_consumer=(0.24, 0.24)), 0.60, 0.6),
    ("2018-01-01", "2018-12-31", "trade war and deleveraging",
     dict(ev_auto=(-0.34, 0.34), semis_ai=(-0.46, 0.44), fintech_consumer=(-0.30, 0.31)), 0.20, -1.4),
    ("2019-01-01", "2019-12-31", "entity-list localisation bid",
     dict(ev_auto=(0.10, 0.30), semis_ai=(0.55, 0.44), fintech_consumer=(0.20, 0.27)), 0.63, 0.3),
    ("2020-01-01", "2020-03-23", "covid shock",
     dict(ev_auto=(-0.55, 0.55), semis_ai=(-0.45, 0.58), fintech_consumer=(-0.50, 0.50)), 0.16, 0.8),
    ("2020-03-24", "2021-02-17", "liquidity boom",
     dict(ev_auto=(1.55, 0.46), semis_ai=(0.85, 0.44), fintech_consumer=(0.70, 0.36)), 0.88, 2.2),
    ("2021-02-18", "2022-03-15", "regulatory crackdown",
     dict(ev_auto=(0.05, 0.40), semis_ai=(-0.30, 0.42), fintech_consumer=(-0.62, 0.46)), 0.18, -0.9),
    ("2022-03-16", "2022-10-31", "covid lockdowns and export controls",
     dict(ev_auto=(-0.18, 0.42), semis_ai=(-0.52, 0.50), fintech_consumer=(-0.24, 0.44)), 0.22, -0.4),
    ("2022-11-01", "2023-01-31", "reopening rally",
     dict(ev_auto=(0.60, 0.40), semis_ai=(0.75, 0.44), fintech_consumer=(1.10, 0.42)), 0.83, 1.1),
    ("2023-02-01", "2024-09-23", "disappointment grind",
     dict(ev_auto=(-0.22, 0.30), semis_ai=(-0.10, 0.36), fintech_consumer=(-0.28, 0.32)), 0.30, -0.7),
    ("2024-09-24", "2024-11-30", "stimulus shock",
     dict(ev_auto=(2.20, 0.60), semis_ai=(2.60, 0.66), fintech_consumer=(2.80, 0.62)), 0.94, 2.6),
    ("2024-12-01", "2025-01-24", "post-stimulus digestion",
     dict(ev_auto=(-0.25, 0.36), semis_ai=(-0.15, 0.40), fintech_consumer=(-0.30, 0.38)), 0.42, 1.4),
    ("2025-01-25", "2025-08-31", "deepseek AI repricing",
     dict(ev_auto=(0.12, 0.34), semis_ai=(1.35, 0.52), fintech_consumer=(0.45, 0.36)), 0.72, 1.0),
    ("2025-09-01", "2026-01-31", "AI capex euphoria",
     dict(ev_auto=(-0.15, 0.36), semis_ai=(1.60, 0.58), fintech_consumer=(0.30, 0.34)), 0.68, 1.3),
    ("2026-02-01", "2026-08-01", "EV price war, AI narrowing",
     dict(ev_auto=(-0.48, 0.44), semis_ai=(0.55, 0.54), fintech_consumer=(0.05, 0.33)), 0.41, 1.1),
]


def _trading_days() -> pd.DatetimeIndex:
    return pd.bdate_range(START_DATE, END_DATE)


def _regime_params(dates: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for d in dates:
        chosen = REGIME_TIMELINE[-1]
        for seg in REGIME_TIMELINE:
            if pd.Timestamp(seg[0]) <= d <= pd.Timestamp(seg[1]):
                chosen = seg
                break
        rows.append(dict(date=d, label=chosen[2], params=chosen[3],
                         breadth=chosen[4], credit=chosen[5]))
    return pd.DataFrame(rows).set_index("date")


def generate_prices(seed: int = 20260804) -> pd.DataFrame:
    """Daily close panel, index=date, columns=ticker. Synthetic."""
    rng = np.random.default_rng(seed)
    dates = _trading_days()
    reg = _regime_params(dates)
    n = len(dates)
    dt = 1 / 252

    # one common market factor plus one factor per sector
    mkt_shock = rng.standard_normal(n)
    sector_shock = {s: rng.standard_normal(n) for s in ["ev_auto", "semis_ai", "fintech_consumer"]}

    out = {}
    for row in UNIVERSE:
        sec = row["sector"]
        mu = np.array([reg["params"].iloc[i][sec][0] for i in range(n)])
        sig = np.array([reg["params"].iloc[i][sec][1] for i in range(n)])

        beta_m, beta_s = rng.uniform(0.5, 1.0), rng.uniform(0.6, 1.1)
        idio = rng.standard_normal(n)
        idio_w = np.sqrt(max(0.0, 1 - 0.35 * beta_m**2 - 0.45 * beta_s**2) + 0.15)

        shock = 0.35 * beta_m * mkt_shock + 0.45 * beta_s * sector_shock[sec] + idio_w * idio
        # name-level drift dispersion so cross-sectional breadth is meaningful
        mu = mu + rng.normal(0, 0.18)

        logret = (mu - 0.5 * sig**2) * dt + sig * np.sqrt(dt) * shock
        px = 100 * np.exp(np.cumsum(logret))

        # ADRs and H-shares of the same company should not be independent —
        # nudge H/US listings toward their A-share counterpart later in features
        out[row["ticker"]] = px

    return pd.DataFrame(out, index=dates)


def generate_macro() -> pd.DataFrame:
    """
    Monthly macro panel. Values are shaped to resemble the real series
    (TSF YoY growth in the 7-14% band, PMI oscillating around 50) but are
    NOT the actual published numbers.
    """
    months = pd.date_range(START_DATE, END_DATE, freq="ME")
    reg = _regime_params(pd.DatetimeIndex(months))
    rng = np.random.default_rng(7)

    credit = reg["credit"].to_numpy()
    tsf_yoy = 11.5 + credit * 1.4 + rng.normal(0, 0.35, len(months))
    tsf_yoy = np.clip(tsf_yoy, 6.5, 16.0)

    m2_yoy = 9.0 + credit * 1.1 + rng.normal(0, 0.4, len(months))
    pmi = 50.0 + credit * 0.9 + rng.normal(0, 0.6, len(months))

    return pd.DataFrame(
        dict(tsf_yoy=tsf_yoy, m2_yoy=m2_yoy, pmi=pmi),
        index=months,
    )
