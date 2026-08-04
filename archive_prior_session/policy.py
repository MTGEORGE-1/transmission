"""
Policy Stance Index.

Two pieces:

1. CORPUS — a hand-encoded set of real Chinese policy events, 2015–2026, each
   scored against a fixed rubric. This is the seed set and the validation
   benchmark. It is deliberately human-scored so there is a ground truth to
   check automated scoring against.

2. score_document() — the LLM scoring path for new documents scraped from
   PBOC / NDRC / MIIT / State Council. Stubbed with the exact rubric the human
   scores follow, so automated and manual scores are directly comparable.

SCORING RUBRIC
--------------
monetary  : -1.0 tightening ......  0.0 neutral ......  +1.0 easing
support   : -1.0 suppressive  ......  0.0 neutral ......  +1.0 promotional
            (scored separately per sector; a document may be promotional for
             semis and suppressive for fintech in the same breath)
weight    :  0.0–1.0 — how much market attention the document commands.
             Politburo readouts and Five-Year Plans score high; routine
             ministry notices score low.

The index is the weighted sum of event scores decayed over a 90-day half-life,
so a major announcement keeps influencing the stance reading for a quarter and
then fades.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd

from .config import SECTORS

HALF_LIFE_DAYS = 90


# ---------------------------------------------------------------------------
# The corpus. (date, source, headline, monetary, {sector: support}, weight)
# ---------------------------------------------------------------------------
def _e(date, source, headline, monetary, ev, semi, fin, weight):
    return dict(
        date=date, source=source, headline=headline, monetary=monetary,
        support=dict(ev_auto=ev, semis_ai=semi, fintech_consumer=fin),
        weight=weight,
    )


CORPUS = [
    _e("2015-04-20", "PBOC", "RRR cut of 100bp, largest since 2008", 0.8, 0.2, 0.2, 0.4, 0.7),
    _e("2015-07-08", "CSRC/State Council", "State rescue package halts market crash; IPOs suspended", 0.7, 0.1, 0.1, -0.2, 0.9),
    _e("2015-08-11", "PBOC", "Surprise RMB devaluation, ~2% band shift", -0.2, -0.3, -0.2, -0.4, 0.9),
    _e("2015-10-23", "PBOC", "Double cut: benchmark rates and RRR", 0.9, 0.3, 0.2, 0.4, 0.7),
    _e("2016-03-05", "NPC", "13th Five-Year Plan names semiconductors a strategic priority", 0.1, 0.2, 0.9, 0.1, 0.9),
    _e("2016-12-16", "CEWC", "Central Economic Work Conference: 'houses are for living in, not speculation'", -0.3, 0.0, 0.1, -0.5, 0.8),
    _e("2017-04-01", "State Council", "Xiongan New Area announced", 0.2, 0.3, 0.2, 0.2, 0.6),
    _e("2017-07-14", "State Council", "National Financial Work Conference: deleveraging campaign begins", -0.8, -0.2, -0.1, -0.8, 0.9),
    _e("2017-11-17", "PBOC/CBRC", "Draft asset-management rules target shadow banking", -0.7, -0.1, 0.0, -0.9, 0.8),
    _e("2018-03-22", "US/MOFCOM", "US Section 301 tariffs announced; trade war opens", -0.2, -0.5, -0.5, -0.3, 1.0),
    _e("2018-04-16", "US BIS", "ZTE denied US component access", 0.0, -0.1, -0.8, -0.1, 0.9),
    _e("2018-06-24", "PBOC", "Targeted RRR cut to support deleveraging fallout", 0.6, 0.2, 0.2, 0.3, 0.6),
    _e("2018-10-31", "Politburo", "Readout drops 'deleveraging', adds 'downward pressure'", 0.7, 0.3, 0.3, 0.5, 0.9),
    _e("2019-05-16", "US BIS", "Huawei added to Entity List", 0.0, -0.1, -0.9, -0.1, 1.0),
    _e("2019-06-13", "SSE", "STAR Market launched to fund hard tech", 0.2, 0.2, 0.9, 0.1, 0.9),
    _e("2020-02-03", "PBOC", "Liquidity injection as COVID shuts economy", 0.9, -0.4, -0.3, -0.4, 0.9),
    _e("2020-04-23", "MOF/MIIT", "NEV purchase subsidies extended two years", 0.1, 0.9, 0.1, 0.1, 0.8),
    _e("2020-08-20", "PBOC/MOHURD", "'Three red lines' property leverage caps", -0.8, -0.1, 0.0, -0.7, 0.9),
    _e("2020-11-03", "CSRC/PBOC", "Ant Group IPO suspended two days before listing", -0.3, 0.0, -0.1, -1.0, 1.0),
    _e("2020-12-24", "SAMR", "Antitrust probe opened into Alibaba", 0.0, 0.0, -0.6, -0.8, 0.9),
    _e("2021-04-10", "SAMR", "Alibaba fined RMB 18.2bn for monopolistic conduct", 0.0, 0.0, -0.5, -0.8, 0.9),
    _e("2021-07-02", "CAC", "DiDi app removed from stores days after US IPO", 0.0, -0.2, -0.4, -0.9, 1.0),
    _e("2021-07-24", "State Council", "After-school tutoring sector effectively banned", 0.0, 0.0, -0.3, -1.0, 1.0),
    _e("2021-08-17", "Politburo", "'Common prosperity' elevated to central policy goal", 0.0, 0.0, -0.4, -0.9, 1.0),
    _e("2021-12-06", "PBOC", "RRR cut as property developers default", 0.7, 0.2, 0.2, 0.1, 0.7),
    _e("2022-03-16", "Financial Stability Cmte", "Liu He pledges support for platform economy and overseas listings", 0.5, 0.3, 0.5, 0.9, 1.0),
    _e("2022-10-07", "US BIS", "Sweeping semiconductor export controls on advanced nodes and equipment", 0.0, -0.1, -1.0, -0.1, 1.0),
    _e("2022-11-11", "State Council", "Twenty measures easing zero-COVID", 0.3, 0.5, 0.3, 0.7, 0.9),
    _e("2022-12-07", "State Council", "Zero-COVID abandoned", 0.4, 0.6, 0.4, 0.8, 1.0),
    _e("2023-07-24", "Politburo", "Property language softens; platform-economy support reaffirmed", 0.5, 0.3, 0.3, 0.7, 0.9),
    _e("2023-08-27", "MOF", "Stamp duty on stock trades halved", 0.4, 0.2, 0.2, 0.5, 0.8),
    _e("2023-10-24", "NPC Standing Cmte", "RMB 1tn additional sovereign bond issuance", 0.6, 0.3, 0.3, 0.3, 0.8),
    _e("2024-04-12", "State Council", "New 'Nine Measures' tighten listing and delisting standards", -0.2, 0.0, 0.0, -0.3, 0.7),
    _e("2024-09-24", "PBOC/CSRC", "Coordinated stimulus: RRR cut, mortgage repricing, equity swap facility", 1.0, 0.5, 0.5, 0.8, 1.0),
    _e("2024-09-26", "Politburo", "Rare September economic readout pledges forceful rate cuts", 0.9, 0.5, 0.5, 0.7, 1.0),
    _e("2024-12-09", "Politburo", "Monetary stance shifts to 'moderately loose', first time since 2010", 1.0, 0.4, 0.5, 0.6, 1.0),
    _e("2025-01-27", "Market event", "DeepSeek R1 repricing of China AI capability", 0.0, 0.1, 0.9, 0.2, 1.0),
    _e("2025-02-17", "Xi Jinping", "Symposium with private-sector founders signals rehabilitation", 0.3, 0.4, 0.7, 0.9, 1.0),
    _e("2025-03-05", "NPC", "Deficit target raised to ~4% of GDP; 'AI+' initiative launched", 0.7, 0.4, 0.8, 0.4, 0.9),
    _e("2025-03-20", "CAAM", "Industry body asks media to stop publishing weekly registration data", 0.0, -0.3, 0.0, 0.0, 0.4),
    _e("2025-05-23", "MIIT/NDRC", "Regulators summon EV makers over below-cost pricing", 0.0, -0.4, 0.0, 0.0, 0.7),
    _e("2025-10-15", "NDRC", "15th Five-Year Plan drafting elevates self-reliance in chips and AI", 0.2, 0.3, 0.9, 0.2, 0.9),
    _e("2025-12-10", "CEWC", "PBOC commits to further RRR and rate cuts through 2026", 0.9, 0.3, 0.4, 0.5, 0.9),
    _e("2026-02-11", "MIIT/SAMR", "Rules implemented explicitly forbidding below-cost vehicle sales", -0.1, -0.5, 0.0, 0.0, 0.9),
    _e("2026-03-05", "NPC", "15th Five-Year Plan (2026–2030) ratified; state-directed fab capex confirmed", 0.4, 0.2, 0.9, 0.2, 1.0),
    _e("2026-04-27", "Market event", "BYD average discounts hit record ~10%; margin fears spread", 0.0, -0.6, 0.0, -0.1, 0.8),
    _e("2026-06-12", "PBOC", "May TSF +7.7% YoY; governor reiterates room for further cuts", 0.8, 0.3, 0.3, 0.4, 0.7),
    _e("2026-07-20", "Market event", "Weak July EV sales revive price-war fears across the complex", 0.0, -0.5, 0.0, -0.1, 0.7),
]


# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------
def corpus_frame() -> pd.DataFrame:
    df = pd.DataFrame(CORPUS)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def build_stance_index(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Decay-weighted policy stance on a daily grid.

    Each event contributes its score multiplied by weight, decayed with a
    90-day half-life from the announcement date. Events do not influence the
    past — this is strictly causal, which matters if you ever backtest on it.
    """
    df = corpus_frame()
    lam = math.log(2) / HALF_LIFE_DAYS

    out = pd.DataFrame(index=dates)
    cols = {"monetary": [], **{s: [] for s in SECTORS}}

    ev_dates = df["date"].values.astype("datetime64[D]").astype(int)
    grid = dates.values.astype("datetime64[D]").astype(int)

    weights = df["weight"].to_numpy()
    monetary = df["monetary"].to_numpy()
    support = {s: df["support"].apply(lambda d: d[s]).to_numpy() for s in SECTORS}

    for t in grid:
        age = t - ev_dates
        live = age >= 0
        decay = np.where(live, np.exp(-lam * np.clip(age, 0, None)), 0.0)
        w = decay * weights
        denom = w.sum() if w.sum() > 1e-9 else 1.0
        cols["monetary"].append(float((w * monetary).sum() / denom))
        for s in SECTORS:
            cols[s].append(float((w * support[s]).sum() / denom))

    for k, v in cols.items():
        out[f"stance_{k}"] = v

    # Composite stance used by the regime model: monetary plus mean sector support
    out["policy_stance"] = (
        out["stance_monetary"] * 0.5
        + out[[f"stance_{s}" for s in SECTORS]].mean(axis=1) * 0.5
    )
    return out


# ---------------------------------------------------------------------------
# LLM scoring path (for newly scraped documents)
# ---------------------------------------------------------------------------
RUBRIC_PROMPT = """You are scoring a Chinese government or regulatory document for its \
market-relevant policy stance. Return strict JSON, no prose.

Score three fields:

"monetary": float in [-1, 1]
  -1.0 = explicit tightening (rate hikes, RRR increases, deleveraging campaigns,
         credit quota reductions)
   0.0 = neutral / no monetary content
  +1.0 = explicit easing (rate cuts, RRR cuts, liquidity injections,
         "moderately loose" language)

"support": object with keys "ev_auto", "semis_ai", "fintech_consumer",
           each a float in [-1, 1]
  -1.0 = suppressive (bans, antitrust action, price controls, licence removal,
         export-control damage)
   0.0 = no bearing on that sector
  +1.0 = promotional (subsidies, strategic-priority designation, state capex,
         explicit rehabilitation of a sector)
  Score each sector independently. A document can be promotional for one and
  suppressive for another.

"weight": float in [0, 1]
  Market attention the document commands.
  0.9-1.0 = Politburo readout, Five-Year Plan, coordinated stimulus package,
            major foreign export-control action
  0.6-0.8 = PBOC rate action, ministry rules with teeth, CEWC
  0.3-0.5 = routine ministry notice, industry-body guidance
  0.0-0.2 = administrative minutiae

Also return "rationale": one sentence, under 25 words, citing the specific
language that drove the score.

Document source: {source}
Document date: {date}
Document text:
{text}
"""


def score_document(text: str, source: str, date: str, client=None) -> dict:
    """
    Score a single scraped document against the rubric.

    Pass an Anthropic client to use the live path. Without one this raises,
    rather than silently returning a fake score — a scoring pipeline that
    quietly invents numbers is worse than one that stops.
    """
    if client is None:
        raise RuntimeError(
            "score_document() needs an Anthropic client. "
            "Until the scraper is wired up, the hand-scored CORPUS is the "
            "source of truth for the stance index."
        )

    import json

    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": RUBRIC_PROMPT.format(source=source, date=date, text=text[:12000]),
        }],
    )
    raw = msg.content[0].text.strip()
    raw = raw[raw.find("{"): raw.rfind("}") + 1]
    return json.loads(raw)


def event_study(prices: pd.DataFrame, sector: str, window: int = 20) -> dict:
    """
    Do sector returns actually respond to policy events?

    For every corpus event with |support| >= 0.4 and weight >= 0.7, measure the
    sector's cumulative return over the following `window` trading days, then
    compare the promotional and suppressive groups.

    This is the honesty check. If promotional and suppressive events produce
    the same forward returns, the index is not measuring anything and the
    validation page should say so.
    """
    df = corpus_frame()
    df["support_s"] = df["support"].apply(lambda d: d[sector])
    sig = df[(df["support_s"].abs() >= 0.4) & (df["weight"] >= 0.7)]

    ret = prices.pct_change()
    rows = []
    for _, ev in sig.iterrows():
        idx = ret.index.searchsorted(ev["date"])
        if idx + window >= len(ret):
            continue
        fwd = float((1 + ret.iloc[idx: idx + window]).prod() - 1)
        rows.append(dict(
            date=ev["date"].strftime("%Y-%m-%d"),
            headline=ev["headline"],
            score=float(ev["support_s"]),
            fwd_return=fwd,
            direction="promotional" if ev["support_s"] > 0 else "suppressive",
        ))

    if not rows:
        return dict(sector=sector, n=0, events=[])

    r = pd.DataFrame(rows)
    pro = r[r.direction == "promotional"]["fwd_return"]
    sup = r[r.direction == "suppressive"]["fwd_return"]

    # sign agreement: did the return move the way the score implied?
    hits = int((np.sign(r["score"]) == np.sign(r["fwd_return"])).sum())

    return dict(
        sector=sector,
        n=len(r),
        window_days=window,
        mean_promotional=float(pro.mean()) if len(pro) else None,
        mean_suppressive=float(sup.mean()) if len(sup) else None,
        spread=float(pro.mean() - sup.mean()) if len(pro) and len(sup) else None,
        hit_rate=hits / len(r),
        events=rows,
    )
