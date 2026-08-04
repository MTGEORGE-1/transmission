"""
Regime classifier.

A Gaussian HMM over a small, interpretable feature set. The point is not
prediction — it is to say, with a probability attached, *what kind of market
this currently is*, and to show the historical sequence of those states.

Why an HMM and not clustering: regimes are persistent and the transitions
matter. A k-means label flickers day to day; an HMM's transition matrix
enforces the persistence that actually characterises policy cycles, and gives
you transition probabilities for free.

Known limitation, stated plainly: HMMs identify turning points late. The
smoothed (Viterbi) path is only available in hindsight. For the live reading
we use the *filtered* probability, which uses no future data — this is the
honest number and it is less confident than the pretty historical chart.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

from .config import N_REGIMES, REGIME_FEATURES


def _standardise(X: pd.DataFrame) -> tuple[np.ndarray, pd.Series, pd.Series]:
    mu, sd = X.mean(), X.std().replace(0, 1.0)
    return ((X - mu) / sd).to_numpy(), mu, sd


def _label_states(model: GaussianHMM, cols: list[str], mu: pd.Series,
                  sd: pd.Series) -> dict[int, str]:
    """
    Name states by their economic character rather than by index.

    HMM state numbering is arbitrary across fits, so the labels must be derived
    from the fitted means or the dashboard legend becomes meaningless on refit.
    """
    means = pd.DataFrame(model.means_, columns=cols)
    means = means * sd[cols].to_numpy() + mu[cols].to_numpy()  # back to real units

    labels: dict[int, str] = {}
    remaining = set(means.index)

    def take(idx, name):
        labels[int(idx)] = name
        remaining.discard(idx)

    # Stress: highest volatility
    take(means.loc[list(remaining), "realized_vol"].idxmax(), "Policy Stress")

    # Euphoria: among the rest, highest breadth + momentum
    score = (means.loc[list(remaining), "breadth"].rank()
             + means.loc[list(remaining), "momentum_3m"].rank())
    take(score.idxmax(), "Retail Euphoria")

    # Stimulus risk-on: strongest policy stance + credit impulse
    score = (means.loc[list(remaining), "policy_stance"].rank()
             + means.loc[list(remaining), "credit_impulse"].rank())
    take(score.idxmax(), "Stimulus Risk-On")

    for i in list(remaining):
        take(i, "Grinding Consolidation")

    return labels


def fit_regimes(features: pd.DataFrame, n_states: int = N_REGIMES,
                seed: int = 42) -> dict:
    cols = [c for c in REGIME_FEATURES if c in features.columns]
    X = features[cols].copy()
    Z, mu, sd = _standardise(X)

    model = GaussianHMM(
        n_components=n_states,
        covariance_type="diag",
        n_iter=500,
        random_state=seed,
        tol=1e-4,
    )
    model.fit(Z)

    labels = _label_states(model, cols, mu, sd)

    # Smoothed path — hindsight view, uses the whole sample. Good for the chart.
    viterbi = model.predict(Z)
    # Posterior at each t given all data
    smoothed_proba = model.predict_proba(Z)

    # Filtered path — causal, uses only data up to t. This is the honest
    # "what regime are we in right now" number.
    filtered = _filtered_probabilities(model, Z)

    out = pd.DataFrame(index=features.index)
    out["state"] = viterbi
    out["label"] = [labels[s] for s in viterbi]
    out["confidence"] = smoothed_proba.max(axis=1)
    out["filtered_state"] = filtered.argmax(axis=1)
    out["filtered_label"] = [labels[s] for s in filtered.argmax(axis=1)]
    out["filtered_confidence"] = filtered.max(axis=1)

    for i in range(n_states):
        out[f"p_{labels[i].lower().replace(' ', '_').replace('-', '_')}"] = smoothed_proba[:, i]

    means_real = pd.DataFrame(model.means_, columns=cols)
    means_real = means_real * sd[cols].to_numpy() + mu[cols].to_numpy()
    means_real.index = [labels[i] for i in means_real.index]

    return dict(
        model=model,
        path=out,
        labels=labels,
        transition=pd.DataFrame(
            model.transmat_,
            index=[labels[i] for i in range(n_states)],
            columns=[labels[i] for i in range(n_states)],
        ),
        state_means=means_real,
        features_used=cols,
        loglik=float(model.score(Z)),
    )


def _filtered_probabilities(model: GaussianHMM, Z: np.ndarray) -> np.ndarray:
    """
    Forward-only filtering: P(state_t | observations up to t).

    hmmlearn exposes smoothed posteriors, which use future data. For anything
    resembling a live signal that is lookahead bias, so we run the forward
    recursion ourselves.
    """
    framelogprob = model._compute_log_likelihood(Z)
    n_obs, n_states = framelogprob.shape

    log_startprob = np.log(model.startprob_ + 1e-300)
    log_transmat = np.log(model.transmat_ + 1e-300)

    alpha = np.zeros((n_obs, n_states))
    alpha[0] = log_startprob + framelogprob[0]
    alpha[0] -= _logsumexp(alpha[0])

    for t in range(1, n_obs):
        for j in range(n_states):
            alpha[t, j] = _logsumexp(alpha[t - 1] + log_transmat[:, j]) + framelogprob[t, j]
        alpha[t] -= _logsumexp(alpha[t])

    return np.exp(alpha)


def _logsumexp(a: np.ndarray) -> float:
    m = a.max()
    return m + np.log(np.exp(a - m).sum())


def regime_diagnostics(path: pd.DataFrame, market: pd.Series) -> dict:
    """
    Does the regime label carry information about forward returns?

    Reports mean forward 21-day return and hit rate by regime. If every regime
    shows the same forward return, the model is decorative and the validation
    page must say so.
    """
    fwd = market.pct_change(21).shift(-21).reindex(path.index)
    df = pd.DataFrame(dict(label=path["label"], fwd=fwd)).dropna()

    rows = []
    for label, g in df.groupby("label"):
        rows.append(dict(
            regime=label,
            n_days=int(len(g)),
            share=float(len(g) / len(df)),
            mean_fwd_21d=float(g["fwd"].mean()),
            median_fwd_21d=float(g["fwd"].median()),
            pct_positive=float((g["fwd"] > 0).mean()),
            vol_fwd=float(g["fwd"].std()),
        ))

    rows.sort(key=lambda r: r["mean_fwd_21d"], reverse=True)

    spread = rows[0]["mean_fwd_21d"] - rows[-1]["mean_fwd_21d"] if len(rows) > 1 else 0.0

    # Average run length — are regimes actually persistent?
    runs, cur, n = [], path["label"].iloc[0], 1
    for lab in path["label"].iloc[1:]:
        if lab == cur:
            n += 1
        else:
            runs.append(n)
            cur, n = lab, 1
    runs.append(n)

    return dict(
        by_regime=rows,
        best_worst_spread_21d=float(spread),
        mean_run_length_days=float(np.mean(runs)),
        n_regime_changes=len(runs) - 1,
    )
