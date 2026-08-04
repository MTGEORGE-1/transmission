"""Export precomputed artifacts for the front end.

Per SCOPING.md §4 the site is static and reads precomputed JSON — it must not
be able to break because a Chinese endpoint had a bad day.

Two files are written: `data/artifacts/*.json` (the real artifacts, what a
GitHub Actions job would commit) and `site/data.js`, which is the same payload
assigned to `window.TRANSMISSION`. The second exists so the dashboard opens
directly from the filesystem — `fetch()` on a `file://` URL is blocked by CORS,
and requiring a local web server to view a prototype is friction with no
upside.
"""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import config as C
from .regime import COLORS, segments
from .universe import SECTORS


def _clean(o):
    """Make numpy/pandas types JSON-safe and NaN-free."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 6)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def _series(s: pd.Series) -> list[dict]:
    s = s.dropna()
    return [{"d": str(pd.Timestamp(i).date()), "v": _clean(v)} for i, v in s.items()]


def build_payload(*, csi300, prices, sectors, feats, feat_notes, reg, lineage) -> dict:
    weekly_csi = csi300.resample("W-FRI").last().dropna()
    weekly_csi = weekly_csi[weekly_csi.index >= C.START_DATE]

    filt = reg["filtered"]
    latest_ts = filt.index[-1]
    latest = filt.iloc[-1].sort_values(ascending=False)

    stats = reg["stats"]
    state_rows = []
    for k in stats.index:
        row = {"label": stats.loc[k, "label"],
               "color": COLORS.get(stats.loc[k, "label"], "#888"),
               "n_weeks": int(stats.loc[k, "n_weeks"]),
               "expected_weeks": _clean(stats.loc[k, "expected_weeks"]),
               "signature": {c: _clean(stats.loc[k, c]) for c in reg["columns"]}}
        state_rows.append(row)

    sector_series = {
        key: _series(sectors[key].resample("W-FRI").last())
        for key in SECTORS if key in sectors.columns
    }

    return {
        "meta": {
            "name": "Transmission",
            "tagline": "Chinese tech equities are priced by policy, not by earnings.",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "data_source": "LIVE",
            "start_date": C.START_DATE,
            "n_tickers": int(prices.shape[1]),
            "benchmark": "CSI 300",
            "n_regimes": C.N_REGIMES,
        },
        "benchmark": {"label": "CSI 300", "series": _series(weekly_csi)},
        "regimes": {
            "segments": segments(reg["path"]),
            "colors": COLORS,
            "current": {
                "as_of": str(latest_ts.date()),
                "label": latest.index[0],
                "probability": _clean(latest.iloc[0]),
                "distribution": [{"label": k, "p": _clean(v)} for k, v in latest.items()],
                "basis": "filtered (causal — uses no data after the as-of date)",
            },
            "states": state_rows,
            "transition": {
                "labels": list(reg["transition"].index),
                "matrix": _clean(reg["transition"].to_numpy().tolist()),
            },
        },
        "features": {
            "columns": reg["columns"],
            "latest": {c: _clean(feats[c].iloc[-1]) for c in reg["columns"]},
            "series": {c: _series(feats[c]) for c in reg["columns"]},
            "notes": feat_notes,
        },
        "sectors": {"labels": SECTORS, "series": sector_series},
        "lineage": lineage,
        "limitations": [
            "Outputs are regimes, probabilities and exposures — never point price forecasts.",
            "The universe is HK-listed and ADR names only. The A-share leg is geo-blocked "
            "on this network from every source tested (akshare/EastMoney and baostock).",
            "Breadth is computed on the HK/ADR universe while the benchmark is the mainland "
            "CSI 300. Different venues, imperfectly comparable.",
            "Credit impulse is a proxy — the 12-month change in M2 growth. Total Social "
            "Financing, the series actually wanted, is not reachable.",
            "HMMs identify turning points late. The historical bands use smoothed "
            "probabilities (hindsight); the current reading uses filtered probabilities.",
            "Feature standardisation uses full-sample mean and standard deviation, a mild "
            "in-sample normalisation.",
            "Regime probabilities saturate near 1.0. With six features the Gaussian emission "
            "densities differ by many orders of magnitude, so the posterior collapses onto one "
            "state. Read it as 'the model is confident', not as a calibrated 99% chance — these "
            "probabilities have not been calibration-tested.",
            "2015-2026 covers only three or four genuine policy cycles — small sample, "
            "wide error bars.",
            "Not yet built: the policy stance index (Model A) and the supply-chain "
            "propagation graph (Model C).",
        ],
    }


def write(payload: dict) -> None:
    data = _clean(payload)

    (C.ARTIFACTS / "dashboard.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False))

    (C.SITE / "data.js").write_text(
        "// Generated by transmission.export — do not edit by hand.\n"
        "window.TRANSMISSION = "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + ";\n")
