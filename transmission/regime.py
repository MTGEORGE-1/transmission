"""Regime classification.

The output is deliberately *not* a price forecast (SCOPING.md §L3: point
forecasts are excluded). It is a statement of what kind of market this is, with
a probability attached, plus the transition structure between kinds.

Two probabilities are produced and they are not interchangeable:

* `filtered`  — uses only data up to t. This is the live reading and the only
  one that can honestly be called a current signal.
* `smoothed`  — uses the whole sample. Prettier, more confident, hindsight
  only. Used for the historical bands and nothing else.

Known limitation, stated rather than buried: HMMs mark turning points late.
That is inherent to the method, not a tuning problem.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .hmm import GaussianHMM

# Names are assigned from fitted state statistics, not hard-coded to indices —
# EM does not guarantee state ordering between runs.
LABELS = {
    "stimulus": "Stimulus Risk-On",
    "consolidation": "Grinding Consolidation",
    "stress": "Policy Stress",
    "euphoria": "Retail Euphoria",
}

COLORS = {
    "Stimulus Risk-On": "#2f9e6e",
    "Grinding Consolidation": "#8a8f98",
    "Policy Stress": "#c8503f",
    "Retail Euphoria": "#d99a2b",
}


def _assign_labels(stats: pd.DataFrame) -> dict[int, str]:
    """Map fitted states to names by their return/vol signature.

    Deterministic and order-independent:
      worst mean return                    → Policy Stress
      highest vol of what remains          → Retail Euphoria
      of the last two, higher return       → Stimulus Risk-On
                                    lower  → Grinding Consolidation
    """
    remaining = list(stats.index)

    stress = stats.loc[remaining, "ret_4w"].idxmin()
    remaining.remove(stress)

    euphoria = stats.loc[remaining, "realized_vol"].idxmax()
    remaining.remove(euphoria)

    ordered = stats.loc[remaining, "ret_4w"].sort_values(ascending=False)
    out = {stress: LABELS["stress"], euphoria: LABELS["euphoria"]}
    if len(ordered) >= 1:
        out[ordered.index[0]] = LABELS["stimulus"]
    if len(ordered) >= 2:
        out[ordered.index[1]] = LABELS["consolidation"]
    for s in stats.index:
        out.setdefault(s, f"State {s}")
    return out


def fit(features: pd.DataFrame, n_states: int = C.N_REGIMES, seed: int = C.RANDOM_SEED):
    """Fit the regime model. Returns a dict of everything the exporter needs."""
    cols = list(features.columns)
    X_raw = features.to_numpy(dtype=float)

    # Standardised for fitting so no single feature dominates by scale.
    # Full-sample statistics are used, which is a mild in-sample normalisation —
    # recorded in the limitations rather than glossed over.
    mu, sd = X_raw.mean(0), X_raw.std(0)
    sd[sd == 0] = 1.0
    X = (X_raw - mu) / sd

    model = GaussianHMM(n_states, seed=seed).fit(X)

    filt = model.filtered(X)
    smooth = model.smoothed(X)
    path = model.viterbi(X)

    # State signature in the ORIGINAL units — this is what gets shown, and
    # z-scores are not readable to a finance audience.
    stats = pd.DataFrame(
        {c: [X_raw[path == k, i].mean() if (path == k).any() else np.nan
             for k in range(n_states)]
         for i, c in enumerate(cols)},
        index=range(n_states),
    )
    stats["n_weeks"] = [int((path == k).sum()) for k in range(n_states)]

    names = _assign_labels(stats)
    stats["label"] = [names[k] for k in stats.index]

    # Expected duration of a state, in weeks: 1 / (1 - self-transition).
    diag = np.diag(model.A_)
    stats["expected_weeks"] = np.where(diag < 1, 1.0 / (1.0 - diag), np.inf)

    return {
        "model": model,
        "features": features,
        "columns": cols,
        "filtered": pd.DataFrame(filt, index=features.index,
                                 columns=[names[k] for k in range(n_states)]),
        "smoothed": pd.DataFrame(smooth, index=features.index,
                                 columns=[names[k] for k in range(n_states)]),
        "path": pd.Series([names[k] for k in path], index=features.index, name="regime"),
        "stats": stats,
        "transition": pd.DataFrame(model.A_,
                                   index=[names[k] for k in range(n_states)],
                                   columns=[names[k] for k in range(n_states)]),
        "loglik": model.loglik_,
    }


def segments(path: pd.Series) -> list[dict]:
    """Contiguous runs of one regime — what the chart shades."""
    out = []
    if path.empty:
        return out
    cur, start, prev = path.iloc[0], path.index[0], path.index[0]
    for ts, val in path.items():
        if val != cur:
            out.append({"regime": cur, "start": str(start.date()), "end": str(prev.date())})
            cur, start = val, ts
        prev = ts
    out.append({"regime": cur, "start": str(start.date()), "end": str(prev.date())})
    return out
