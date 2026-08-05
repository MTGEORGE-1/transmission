#!/usr/bin/env python3
"""Transmission — build the whole engine end to end.

    python run.py            # use cache where fresh
    python run.py --force    # re-fetch everything

Writes data/artifacts/*.json and site/data.js, then site/index.html is
openable directly in a browser.
"""

from __future__ import annotations

import argparse
import sys
import time

from transmission import config as C
from transmission import export, features, ingest, regime


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore cache, re-fetch")
    ap.add_argument("--regimes", type=int, default=C.N_REGIMES)
    args = ap.parse_args()

    t0 = time.time()
    print("Transmission — build\n" + "=" * 58)

    print("[1/5] ingest")
    prices = ingest.fetch_prices(force=args.force)
    print(f"      prices     {prices.shape[1]:>3} tickers, {len(prices):>5} days")
    csi = ingest.fetch_csi300(force=args.force)
    print(f"      CSI 300    {len(csi):>5} days  → {csi.index[-1].date()}")
    macro = ingest.fetch_macro(force=args.force)
    print(f"      macro      {list(macro.columns)}  {len(macro)} months")

    print("[2/5] features")
    sectors = features.sector_indices(prices)
    feats, notes = features.build(prices, csi, macro)
    print(f"      {feats.shape[1]} features × {len(feats)} weeks "
          f"({feats.index[0].date()} → {feats.index[-1].date()})")
    for n in notes:
        print(f"      - {n['feature']}: {n['status']}")

    print(f"[3/5] regime HMM ({args.regimes} states)")
    reg = regime.fit(feats, n_states=args.regimes)
    print(f"      converged in {len(reg['loglik'])} iters, "
          f"loglik {reg['loglik'][-1]:.1f}")
    for _, r in reg["stats"].iterrows():
        print(f"      {r['label']:<24} {int(r['n_weeks']):>4}w  "
              f"expected run {r['expected_weeks']:.1f}w")

    print("[4/5] export")
    payload = export.build_payload(
        csi300=csi, prices=prices, sectors=sectors, feats=feats,
        feat_notes=notes, reg=reg, lineage=ingest.LINEAGE)
    export.write(payload)
    ingest.write_lineage()

    cur = payload["regimes"]["current"]
    print(f"      artifacts → {C.ARTIFACTS}")
    print(f"      site data → {C.SITE / 'data.js'}")

    print("[5/5] done")
    print("=" * 58)
    print(f"Current regime ({cur['as_of']}): {cur['label']}  "
          f"p={cur['probability']:.3f}")
    print("  " + "  ".join(f"{d['label']}={d['p']:.3f}"
                           for d in cur["distribution"]))
    print(f"\nBuilt in {time.time() - t0:.1f}s. Open site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
