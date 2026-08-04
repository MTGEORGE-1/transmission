# China Tech Model Engine — Project Scoping

**Status:** pre-build scoping
**Date:** August 2026
**Purpose:** portfolio / showcase piece
**Sectors:** EV & auto, semiconductors & AI, fintech & consumer

---

## 1. The thesis

> **Chinese tech equities are priced by policy, not by earnings. This engine quantifies that.**

That one line is the whole project. It is the reason this isn't "another stock dashboard," and it should be the first thing on the landing page.

It also happens to be true, and the current market gives us clean evidence:

- **Cambricon** posted Q1 2026 revenue up 160% YoY and trades near 278x P/E. Its 2026 target of 500,000 AI accelerators (vs. 116,000 in 2025) is gated not by customer demand but by SMIC yield — which is gated by equipment import restrictions, which are gated by export-control policy. Three layers of policy between the chip and the earnings number.
- **SMIC** capex is explicitly state-directed under the 15th Five-Year Plan (2026–2030), not driven by conventional demand signals.
- **BYD** ran seven consecutive months of YoY sales declines through March 2026 with record ~10% average discounts — until regulators implemented rules in February 2026 explicitly forbidding below-cost selling. A price war ended by decree, not by equilibrium.
- **PBOC** has committed to "moderately loose" policy for 2026 with further RRR and rate cuts signalled; TSF grew 7.7% YoY in May 2026 against a 456.89tn yuan outstanding stock.

A Western-style factor model has nothing to say about any of that. A model built around policy transmission does.

---

## 2. What the engine actually does

Four layers. Each is independently demo-able, which matters for a portfolio piece — you always have something to show.

```
┌─────────────────────────────────────────────────────────┐
│  L4  PRESENTATION   static site, precomputed JSON       │
├─────────────────────────────────────────────────────────┤
│  L3  MODELS         policy index │ regime HMM │ graph   │
├─────────────────────────────────────────────────────────┤
│  L2  FEATURES       credit impulse, A-H premium, z-scores│
├─────────────────────────────────────────────────────────┤
│  L1  INGEST         AkShare │ yfinance │ policy scrapers │
└─────────────────────────────────────────────────────────┘
```

### L3 in detail — three models, honestly scoped

**Model A — Policy Stance Index (NLP)**

Scrape PBOC statements, NDRC and MIIT releases, State Council announcements, and Politburo readouts. Score each document along two axes using an LLM with a fixed, published rubric: *monetary stance* (hawkish↔dovish) and *sector support* (suppressive↔promotional, per sector).

Output: a weekly per-sector policy support score, 2015–present.

Validate with an event study — do sector returns move with the index, and does the index lead or lag? Publishing the rubric and the lead/lag result is what makes this research rather than vibes.

*Why this is the strongest component:* it is the part nobody else builds, it requires judgment rather than library calls, and the input data (government text) is free and complete.

**Model B — Regime Classifier**

A Hidden Markov Model over a small feature set: credit impulse, A-H premium, sector breadth, realized volatility, policy stance index. Fit 3–4 latent states, which will likely resolve to something like *stimulus-driven risk-on / grinding consolidation / policy-tightening stress / retail euphoria*.

Output: current regime + transition probabilities, plus historical regime bands.

*Why:* it is the right statistical tool for a market that genuinely switches regimes, and regime bands shaded behind a CSI 300 chart is the single best-looking visual in quant finance. Cheap to compute, high visual return.

**Model C — Supply-Chain Shock Propagation**

A hand-built directed graph of ~80–150 nodes across the three sectors, with edges for supplier, customer, competitor, and policy-exposure relationships. Weight edges by revenue dependence where disclosed.

Shock a node — *"SMIC 7nm yield improves 20%"*, *"NEV purchase tax exemption ends"*, *"new US entity-list additions"* — and propagate to estimate affected revenue exposure across the graph.

*Frame this as scenario analysis, not prediction.* It is a reasoning tool that makes second-order exposure visible. Overclaiming here is the fastest way to lose credibility with a finance reader.

**Deliberately excluded: point price forecasts.** Any portfolio project claiming to predict Chinese equity prices reads as naive to exactly the audience you want to impress. Outputs are regimes, probabilities, and exposures.

---

## 3. Data layer — the audit you need to run first

I could not test these endpoints from my sandbox (its network is allowlisted and blocks both the Chinese data hosts and Yahoo). **Phase 0 is running the audit script on your own machine.** Everything below is researched, not verified live.

| Source | Covers | Cost | Confidence |
|---|---|---|---|
| **AkShare** (v1.18.81) | A-shares, ETFs, bonds, futures, macro. 1,000+ interfaces, no API key, actively maintained | Free | High — the backbone |
| **yfinance** | HK-listed, US ADRs, index history | Free | High |
| **Baostock** | A-share history, clean adjusted prices | Free | Medium — good cross-check on AkShare |
| **PBOC / NDRC / MIIT / State Council sites** | Policy text corpus | Free | Medium — scraping effort, Chinese-language |
| **Tushare** | Deeper fundamentals | Free tier needs a Chinese mobile number | Low — treat as unavailable |
| **Wind / Choice** | Everything, properly | Institutional pricing | Out of scope |

**Two data risks worth knowing before you commit:**

1. **Weekly EV registration data is less reliable than it used to be.** In March 2025 CAAM asked media to stop publishing weekly registration numbers, arguing they "fuel vicious competition." Third parties (e.g. CarNewsChina via China EV DataTracker) still publish, but this is now a fragile dependency on an intermediary rather than a stable feed. *Design for monthly CPCA/CAAM data as the primary series and treat weekly as a bonus.*
2. **AkShare endpoints hit Chinese servers.** Reliability and latency from outside China vary, and endpoints occasionally break when upstream sites change. Cache aggressively; never let the site depend on a live call.

---

## 4. Recommended stack

For a portfolio piece specifically, the architecture that maximizes impressiveness per hour:

**Python engine → nightly GitHub Actions job → precomputed JSON → static React/Next.js site on Vercel.**

- No backend to run, no server cost, no cold starts, page loads instantly
- The site cannot break when a Chinese data endpoint has a bad day
- The GitHub Actions cron is itself a credibility signal — it shows you think about production, not just notebooks
- Storage: DuckDB or Parquet locally, committed JSON artifacts for the front end

Streamlit is faster to build but reads as a prototype. If the goal is showcase, spend the extra time on a real front end.

---

## 5. Build phases

| Phase | Work | Est. |
|---|---|---|
| **0** | Data audit — run every candidate source on your machine, record what works | 1 day |
| **1** | Ingest + storage layer, historical backfill | 3–5 days |
| **2** | Feature engineering: credit impulse, A-H premium, breadth, z-scores | 2–3 days |
| **3** | Regime HMM + validation | 3–4 days |
| **4** | Policy text corpus + stance index + event study | 5–7 days |
| **5** | Supply-chain graph + scenario engine | 4–6 days |
| **6** | Front end | 5–8 days |
| **7** | Validation page + written methodology | 2–3 days |

Phases 3 and 4 are the intellectual core. Phase 7 is what separates this from a student project — **do not cut it.**

**Minimum viable showcase:** phases 0–3 + a stripped phase 6. That is roughly two weeks to something genuinely presentable, with 4 and 5 as extensions.

---

## 6. The credibility move

Most finance portfolio projects show only what worked. Build a **validation page** that shows:

- Event-study results for the policy index, including the cases where it failed
- Regime classifier hit rates and confusion matrix
- Explicit statements of what the model cannot do
- Data lineage — every number traceable to a source and a timestamp

A reviewer who sees you documenting your own model's failure modes will trust everything else on the site. This is a bigger differentiator than any additional feature.

---

## 7. Honest limitations to state up front

- Chinese corporate disclosure quality is uneven; reported fundamentals carry real uncertainty
- The policy corpus is Chinese-language — translation and LLM scoring both introduce error that should be quantified, not hidden
- Regime models fit history well and identify turning points late; this is inherent, not a bug to be fixed
- A-share retail dominance means sentiment can decouple from every fundamental input for months
- Backtests over 2015–2026 span only two or three genuine policy cycles — small sample, wide error bars

---

## 8. Open questions before Phase 1

1. **Name.** Suggestions: *Transmission*, *Mandate*, *Sinotel*, *Policy Alpha*. "Transmission" is my pick — it names the actual mechanism and works as both a monetary-policy term and an auto-sector pun.
2. **Universe size.** ~60 tickers across three sectors is enough to be credible and small enough to curate by hand. Going wider adds noise, not signal.
3. **History depth.** 2015 start captures the 2015 crash, 2018 trade war, 2021 tech crackdown, and 2024–26 stimulus cycle — four distinct regimes. Earlier data adds little.
4. **Chinese-language handling.** Translate the corpus to English then score, or score in Chinese directly? Scoring in Chinese is more faithful; translating is easier to audit and to display on the site.

---

## Sources

- [AKShare — GitHub](https://github.com/akfamily/akshare) · [PyPI](https://pypi.org/project/akshare/)
- [China EVs in 2026: survival test — CNBC](https://www.cnbc.com/2025/12/30/china-electric-car-2026-price-war-evs-sales-global-expansion-slowdown-price-war-2025.html)
- [BYD discounts show China EV price war accelerating — Bloomberg](https://www.bloomberg.com/news/newsletters/2026-04-27/byd-discounts-show-china-ev-price-war-is-accelerating)
- [Price war fears grip China's EV market — SCMP](https://www.scmp.com/business/china-evs/article/3362717/price-war-fears-grip-chinas-ev-market-after-woeful-july-sales-figures)
- [China EV weekly registrations — CarNewsChina](https://carnewschina.com/2025/09/30/china-ev-registrations-in-week-39-xpeng-10400-nio-group-10800-tesla-19300-byd-92400/)
- [Cambricon remains China's top AI chip startup — TrendForce](https://www.trendforce.com/news/2025/12/15/insights-cambricon-remains-chinas-top-ai-chip-startup-rumored-2026-triple-output-faces-smic-limits/)
- [China AI semiconductor localization 2026 — Silicon Analysts](https://siliconanalysts.com/analysis/china-ai-semiconductor-localization-2026-capex-impact)
- [Where China's AI chip supply chain stands in 2026 — The Substrate](https://www.the-substrate.net/p/where-chinas-ai-chip-supply-chain)
- [China's total social financing up 7.7% in May — CGTN](https://news.cgtn.com/news/2026-06-12/China-s-total-social-financing-up-7-7-in-May-1NV0vATaKpq/p.html)
- [PBOC pledges to cut RRR and interest rates in 2026 — Trading Economics](https://tradingeconomics.com/china/news/news/514920)
