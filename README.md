# Transmission — China Tech Model Engine

> **Chinese tech equities are priced by policy, not by earnings. This engine quantifies that.**

Prototype covering **Phases 0–3 plus a stripped Phase 6** of [SCOPING.md](SCOPING.md) — the
"minimum viable showcase". Runs end to end against live data in about 7 seconds.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py          # --force to bypass cache
open site/index.html
```

The dashboard reads `site/data.js`, so it opens straight from the filesystem — no server, and
no live calls from the page.

---

## What it does today

| Layer | Status |
|---|---|
| **L1 Ingest** — yfinance (HK + ADR), akshare (CSI 300, M2, PMI) | ✅ live, cached, lineage-stamped |
| **L2 Features** — breadth, realized vol, momentum, credit-impulse proxy, PMI gap | ✅ causal, publication-lagged |
| **L3 Model B** — 4-state Gaussian HMM | ✅ own Baum-Welch implementation |
| **L3 Model A** — policy stance index (NLP) | ⬜ not built |
| **L3 Model C** — supply-chain graph | ⬜ not built |
| **L4 Presentation** — static dashboard | ✅ regime bands, signatures, transitions, lineage |

39 names across EV & auto, semis & AI, and fintech & consumer; CSI 300 benchmark; 580 weekly
observations from April 2015.

## Does the regime model actually work?

The states are fit blind — nothing tells the model what 2015 or 2018 were. Checked against
events afterwards:

| Period | Model says |
|---|---|
| June 2015 (bubble peak → crash) | **Retail Euphoria → Policy Stress** |
| October 2018 (trade war) | **Policy Stress** |
| October 2024 (stimulus rally) | **Retail Euphoria** |
| August 2021 (tech crackdown) | Grinding Consolidation |

The 2015 Euphoria→Stress handoff is the result worth showing: the model separates a melt-up from
a melt-down using only breadth, vol, momentum and credit, with no labels.

Fitted signatures are coherent — Euphoria carries the highest breadth (0.82) and strong returns;
Policy Stress the highest volatility (0.34) with the worst returns; Stimulus Risk-On the *lowest*
volatility (0.12) with broad participation.

**This is not yet validation.** There is no hit-rate, no confusion matrix, no out-of-sample test.
That is Phase 7, and per the scoping doc it is what separates this from a student project.

## Layout

```
transmission/
  config.py     paths, publication lags, block-page markers
  universe.py   39 curated names + benchmarks
  ingest.py     fetch, cache, retry, lineage, block-page guard
  features.py   causal features; weekly matrix
  hmm.py        Gaussian HMM — scaled Baum-Welch, Viterbi
  regime.py     fit + deterministic state labelling
  export.py     JSON artifacts + site/data.js
run.py          orchestrator
site/           dashboard (opens from file://)
data/           cache/ and artifacts/
```

## Things worth knowing

**The A-share leg is geo-blocked on this network.** A WatchGuard firewall returns
"Connection denied by Geolocation" for China-hosted IPs, which takes out every EastMoney
endpoint, ChinaBond, MIIT, NBS and baostock. Full diagnosis in
[PHASE0_FINDINGS.md](PHASE0_FINDINGS.md). Consequences: no A-H premium, no Cambricon, and the
universe is HK/ADR only. `universe.py` carries `a_share` codes so that leg switches on the
moment it is reachable — a VPN, or the GitHub Actions runner the scoping doc already calls for.

**A firewall block page is still HTTP 200.** `ingest._guard_blockpage` fails loudly rather than
parsing one as data. Do not "fix" a blocked source with `verify=False`; it will silently succeed
and return garbage.

**No lookahead.** Monthly macro is shifted to its release date before being broadcast to daily
(45d for M2, 3d for PMI). Weekly bins are labelled with the last date actually observed, not the
bin's Friday — otherwise the current reading gets stamped with a future date.

**The HMM is hand-written**, not `hmmlearn`: no compiled dependency on Python 3.14, and the
E-step is inspectable for the methodology write-up.

**Probabilities saturate near 1.0.** Six features push the posterior onto one state. Read it as
confidence, not calibration — they have not been calibration-tested.

## Next

1. **Phase 7 validation** — hit rates, confusion matrix, out-of-sample split. Highest credibility
   per hour, and the scoping doc says do not cut it.
2. **Phase 4 — policy stance index.** The strongest differentiator. PBOC, NDRC and State Council
   are all reachable; MIIT is not.
3. **GitHub Actions nightly.** Sidesteps the firewall entirely and restores the A-share leg.
4. **Phase 5 — supply-chain graph.**

`archive_prior_session/` holds an earlier parallel draft (policy corpus, graph scaffolding,
synthetic data generator), kept for reference — it was never executed.
