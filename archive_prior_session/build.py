"""
Pipeline orchestrator.

    python -m transmission.build            # demo data (synthetic)
    python -m transmission.build --live     # live ingest via AkShare/yfinance

Writes precomputed JSON to data/ for the static dashboard. The dashboard never
calls a data source directly — it reads these files. That means the site cannot
break when a Chinese endpoint has a bad day, and it loads instantly.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import features as F
from . import graph as G
from . import policy as P
from . import regime as R
from .config import SECTOR_LABELS, SECTORS, UNIVERSE

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _ds(s: pd.Series, places: int = 4) -> list:
    """Series -> [[iso_date, value], ...] with NaN handling."""
    return [[d.strftime("%Y-%m-%d"), (None if pd.isna(v) else round(float(v), places))]
            for d, v in s.items()]


def _downsample(df: pd.DataFrame, every: str = "W") -> pd.DataFrame:
    """Weekly is plenty for charting eleven years and keeps payloads small."""
    return df.resample(every).last().dropna(how="all")


def run(live: bool = False, refresh: bool = False) -> dict:
    DATA.mkdir(exist_ok=True)
    source_tag = "LIVE" if live else "SYNTHETIC"

    print(f"[1/7] Loading data ({source_tag})")
    if live:
        from . import ingest as src
        prices = src.generate_prices(refresh=refresh)
        macro = src.generate_macro(refresh=refresh)
    else:
        from . import demo_data as src
        prices = src.generate_prices()
        macro = src.generate_macro()
    print(f"      prices {prices.shape}  macro {macro.shape}")

    print("[2/7] Building policy stance index")
    stance = P.build_stance_index(prices.index)

    print("[3/7] Building feature panel")
    feats = F.build_feature_panel(prices, macro, stance)
    print(f"      features {feats.shape}: {', '.join(feats.columns[:6])}...")

    print("[4/7] Fitting regime model")
    reg = R.fit_regimes(feats)
    market = F.market_index(prices).reindex(feats.index)
    diag = R.regime_diagnostics(reg["path"], market)
    print(f"      log-likelihood {reg['loglik']:.1f}, "
          f"{diag['n_regime_changes']} regime changes, "
          f"mean run {diag['mean_run_length_days']:.0f}d")

    print("[5/7] Running policy event studies")
    sect_idx = F.sector_indices(prices)
    studies = {s: P.event_study(sect_idx[s], s) for s in SECTORS}
    for s, r in studies.items():
        if r["n"]:
            print(f"      {s}: n={r['n']} hit_rate={r['hit_rate']:.0%} "
                  f"spread={r['spread']:+.1%}" if r.get("spread") is not None
                  else f"      {s}: n={r['n']}")

    print("[6/7] Propagating scenarios")
    graph = G.graph_payload()

    print("[7/7] Writing JSON artifacts")
    meta = dict(
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        data_source=source_tag,
        warning=None if live else
        "SYNTHETIC DATA — price paths are simulated from a hand-coded regime "
        "timeline, not real market data. Run with --live after passing the "
        "Phase 0 data audit.",
        start=str(prices.index[0].date()),
        end=str(prices.index[-1].date()),
        n_tickers=int(prices.shape[1]),
        universe=[dict(ticker=u["ticker"], name=u["name"], sector=u["sector"],
                       venue=u["venue"]) for u in UNIVERSE],
        sector_labels=SECTOR_LABELS,
    )

    # --- series payload -----------------------------------------------------
    si_w = _downsample(sect_idx)
    mkt_w = _downsample(market.to_frame("market"))["market"]
    stance_w = _downsample(stance)
    feats_w = _downsample(feats)
    path_w = _downsample(reg["path"][["state", "label", "confidence",
                                      "filtered_label", "filtered_confidence"]])

    series = dict(
        market=_ds(mkt_w, 2),
        sectors={s: _ds(si_w[s], 2) for s in SECTORS},
        stance={s: _ds(stance_w[f"stance_{s}"], 3) for s in SECTORS},
        stance_monetary=_ds(stance_w["stance_monetary"], 3),
        credit_impulse=_ds(feats_w["credit_impulse"], 3),
        breadth=_ds(feats_w["breadth"], 3),
        ah_premium=_ds(feats_w["ah_premium"], 4),
        realized_vol=_ds(feats_w["realized_vol"], 3),
        regime=[[d.strftime("%Y-%m-%d"), int(r.state), str(r.label),
                 round(float(r.confidence), 3)]
                for d, r in path_w.iterrows()],
    )

    # --- current reading ----------------------------------------------------
    last = reg["path"].iloc[-1]
    current = dict(
        date=str(reg["path"].index[-1].date()),
        # filtered = causal. This is the number that would have been available
        # in real time. The smoothed label is hindsight and is shown separately.
        regime_live=str(last["filtered_label"]),
        confidence_live=round(float(last["filtered_confidence"]), 3),
        regime_smoothed=str(last["label"]),
        confidence_smoothed=round(float(last["confidence"]), 3),
        stance={s: round(float(stance[f"stance_{s}"].iloc[-1]), 3) for s in SECTORS},
        stance_monetary=round(float(stance["stance_monetary"].iloc[-1]), 3),
        credit_impulse=round(float(feats["credit_impulse"].iloc[-1]), 3),
        breadth=round(float(feats["breadth"].iloc[-1]), 3),
        ah_premium=round(float(feats["ah_premium"].iloc[-1]), 4),
        transitions={
            k: round(float(v), 3) for k, v in
            reg["transition"].loc[str(last["filtered_label"])].items()
        },
    )

    # --- validation ---------------------------------------------------------
    validation = dict(
        regime=diag,
        transition_matrix=reg["transition"].round(4).to_dict(),
        state_means=reg["state_means"].round(3).to_dict(),
        features_used=reg["features_used"],
        loglik=reg["loglik"],
        event_studies=studies,
        caveats=([] if live else [
            "CIRCULARITY WARNING — on synthetic data these validation numbers are "
            "meaningless. The demo price paths were generated from a regime timeline "
            "built around the same real events that populate the policy corpus, so the "
            "event study is testing the generator against itself. Hit rates near 60-70% "
            "here demonstrate that the code works, NOT that the signal works. Every "
            "number in this section must be regenerated with --live before it can be "
            "cited or displayed as a result.",
        ]) + [
            "Regime labels are assigned from fitted state means, not chosen by hand — "
            "but the mapping is heuristic and could mislabel a state on refit.",
            "The headline regime uses filtered (causal) probabilities. Historical "
            "regime bands use the smoothed path, which uses future data and is "
            "therefore cleaner than anything achievable in real time.",
            "Event-study windows overlap for events close together, so the "
            "significance of the spread is overstated by naive standard errors.",
            "A-H premium is computed on rebased index levels in the demo; the live "
            "version requires FX conversion of absolute prices.",
            "Eleven years covers roughly four distinct policy cycles. That is a small "
            "sample for a four-state model — treat the transition matrix as "
            "indicative, not precise.",
        ],
    )

    payload = dict(meta=meta, series=series, current=current,
                   validation=validation, graph=graph,
                   corpus=[dict(date=e["date"], source=e["source"],
                                headline=e["headline"], monetary=e["monetary"],
                                support=e["support"], weight=e["weight"])
                           for e in P.CORPUS])

    (DATA / "transmission.json").write_text(
        json.dumps(payload, indent=None, separators=(",", ":"), default=str))

    size = (DATA / "transmission.json").stat().st_size / 1024
    print(f"      data/transmission.json  ({size:.0f} KB)")

    return payload


def main():
    ap = argparse.ArgumentParser(description="Build the Transmission engine artifacts.")
    ap.add_argument("--live", action="store_true", help="use live data ingest")
    ap.add_argument("--refresh", action="store_true", help="bypass ingest cache")
    args = ap.parse_args()

    payload = run(live=args.live, refresh=args.refresh)

    c = payload["current"]
    print("\n" + "=" * 62)
    print(f"  CURRENT READING  ({c['date']})   [{payload['meta']['data_source']}]")
    print("=" * 62)
    print(f"  Regime (live, causal) : {c['regime_live']}  "
          f"({c['confidence_live']:.0%} confidence)")
    print(f"  Regime (smoothed)     : {c['regime_smoothed']}")
    print(f"  Monetary stance       : {c['stance_monetary']:+.2f}")
    for s, v in c["stance"].items():
        print(f"  Policy support {SECTOR_LABELS[s]:<22}: {v:+.2f}")
    print(f"  Credit impulse (z)    : {c['credit_impulse']:+.2f}")
    print(f"  Breadth               : {c['breadth']:.0%}")
    print("=" * 62)
    if payload["meta"]["warning"]:
        print("\n  ⚠  " + payload["meta"]["warning"])


if __name__ == "__main__":
    main()
