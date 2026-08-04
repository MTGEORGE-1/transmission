"""
Supply-chain shock propagation.

A hand-built directed graph of the three sectors. Edges carry a sign and a
weight: how much, and in which direction, does a shock at the source node
transmit to the target?

This is scenario analysis, not prediction. It answers "if X happens, who else
is exposed and roughly how much?" — a question that is genuinely hard to answer
from memory once you are three hops out, and easy once the graph exists.

Edge weights are judgment calls informed by disclosed revenue dependence.
They are documented, not fitted, and the dashboard shows them so a reader can
disagree with a specific number rather than the whole model.
"""

from __future__ import annotations

from collections import defaultdict

# node id -> display metadata
NODES = {
    # policy / external nodes
    "us_export_controls": dict(label="US Export Controls", kind="policy", sector=None),
    "nev_subsidy":        dict(label="NEV Purchase Tax Policy", kind="policy", sector=None),
    "pboc_easing":        dict(label="PBOC Easing", kind="policy", sector=None),
    "price_war_rules":    dict(label="Below-Cost Sales Ban", kind="policy", sector=None),
    "five_year_plan":     dict(label="15th Five-Year Plan Capex", kind="policy", sector=None),

    # semis & AI
    "asml_equipment":  dict(label="Foreign Fab Equipment", kind="input", sector="semis_ai"),
    "smic":            dict(label="SMIC", kind="company", sector="semis_ai", ticker="688981.SS"),
    "hua_hong":        dict(label="Hua Hong Semi", kind="company", sector="semis_ai", ticker="1347.HK"),
    "naura":           dict(label="NAURA", kind="company", sector="semis_ai", ticker="002371.SZ"),
    "amec":            dict(label="AMEC", kind="company", sector="semis_ai", ticker="688012.SS"),
    "cambricon":       dict(label="Cambricon", kind="company", sector="semis_ai", ticker="688256.SS"),
    "hygon":           dict(label="Hygon", kind="company", sector="semis_ai", ticker="688041.SS"),
    "huawei_ascend":   dict(label="Huawei Ascend", kind="private", sector="semis_ai"),
    "alibaba_cloud":   dict(label="Alibaba Cloud", kind="company", sector="semis_ai", ticker="BABA"),
    "tencent_cloud":   dict(label="Tencent Cloud", kind="company", sector="semis_ai", ticker="0700.HK"),
    "iflytek":         dict(label="iFlytek", kind="company", sector="semis_ai", ticker="002230.SZ"),

    # EV & auto
    "lithium":     dict(label="Lithium Supply", kind="input", sector="ev_auto"),
    "ganfeng":     dict(label="Ganfeng Lithium", kind="company", sector="ev_auto", ticker="002460.SZ"),
    "catl":        dict(label="CATL", kind="company", sector="ev_auto", ticker="300750.SZ"),
    "byd":         dict(label="BYD", kind="company", sector="ev_auto", ticker="002594.SZ"),
    "nio":         dict(label="NIO", kind="company", sector="ev_auto", ticker="NIO"),
    "li_auto":     dict(label="Li Auto", kind="company", sector="ev_auto", ticker="LI"),
    "xpeng":       dict(label="XPeng", kind="company", sector="ev_auto", ticker="XPEV"),
    "gwm":         dict(label="Great Wall Motor", kind="company", sector="ev_auto", ticker="601633.SS"),
    "saic":        dict(label="SAIC Motor", kind="company", sector="ev_auto", ticker="600104.SS"),
    "ev_demand":   dict(label="Domestic NEV Demand", kind="demand", sector="ev_auto"),

    # fintech & consumer
    "consumer_credit": dict(label="Consumer Credit Availability", kind="demand", sector="fintech_consumer"),
    "ping_an":         dict(label="Ping An", kind="company", sector="fintech_consumer", ticker="601318.SS"),
    "cmb":             dict(label="China Merchants Bank", kind="company", sector="fintech_consumer", ticker="600036.SS"),
    "meituan":         dict(label="Meituan", kind="company", sector="fintech_consumer", ticker="3690.HK"),
    "jd":              dict(label="JD.com", kind="company", sector="fintech_consumer", ticker="9618.HK"),
    "pdd":             dict(label="PDD Holdings", kind="company", sector="fintech_consumer", ticker="PDD"),
    "zhongan":         dict(label="ZhongAn Online", kind="company", sector="fintech_consumer", ticker="6060.HK"),
    "hkex":            dict(label="HKEX", kind="company", sector="fintech_consumer", ticker="0388.HK"),
}

# (source, target, weight, rationale)
# weight is signed: positive means a positive shock at source helps target.
EDGES = [
    # export controls -> equipment -> foundry -> chips
    ("us_export_controls", "asml_equipment", -0.90, "Controls directly restrict advanced tool imports"),
    ("asml_equipment", "smic", 0.85, "Advanced-node capacity gated by tool access and spares"),
    ("asml_equipment", "hua_hong", 0.45, "Mature-node exposure is lower but not zero"),
    ("us_export_controls", "naura", 0.55, "Domestic toolmakers gain share as imports are blocked"),
    ("us_export_controls", "amec", 0.50, "Same substitution dynamic in etch"),
    ("us_export_controls", "cambricon", 0.60, "Nvidia exclusion hands domestic accelerators the market"),
    ("us_export_controls", "hygon", 0.45, "Server CPU substitution benefit"),
    ("smic", "cambricon", 0.80, "Cambricon volume is capped by SMIC 7nm yield"),
    ("smic", "huawei_ascend", 0.75, "Ascend production depends on the same capacity"),
    ("smic", "hygon", 0.40, "Partial foundry dependence"),
    ("five_year_plan", "smic", 0.85, "Fab capex is state-directed, not demand-driven"),
    ("five_year_plan", "naura", 0.60, "Localisation targets pull domestic equipment orders"),
    ("five_year_plan", "amec", 0.55, "Same"),
    ("cambricon", "alibaba_cloud", 0.35, "Cheaper domestic accelerators lower cloud capex per FLOP"),
    ("huawei_ascend", "alibaba_cloud", 0.40, "Primary alternative to restricted Nvidia supply"),
    ("huawei_ascend", "tencent_cloud", 0.40, "Same"),
    ("alibaba_cloud", "iflytek", 0.30, "Cheaper inference expands the application layer"),
    ("tencent_cloud", "iflytek", 0.25, "Same"),

    # EV chain
    ("lithium", "ganfeng", 0.90, "Direct commodity exposure"),
    ("lithium", "catl", -0.55, "Battery makers are buyers; cheap lithium widens margin"),
    ("catl", "byd", -0.20, "Direct competitor in battery supply"),
    ("catl", "nio", 0.55, "Primary cell supplier"),
    ("catl", "li_auto", 0.50, "Primary cell supplier"),
    ("catl", "xpeng", 0.50, "Primary cell supplier"),
    ("ev_demand", "byd", 0.85, "Volume-driven, mass-market exposure"),
    ("ev_demand", "nio", 0.70, "Premium segment, thinner buffer"),
    ("ev_demand", "li_auto", 0.70, "Premium segment"),
    ("ev_demand", "xpeng", 0.70, "Mid-market"),
    ("ev_demand", "gwm", 0.55, "Mixed ICE and NEV book"),
    ("ev_demand", "saic", 0.50, "Legacy exposure dilutes NEV sensitivity"),
    ("ev_demand", "catl", 0.80, "Cell demand is downstream volume"),
    ("nev_subsidy", "ev_demand", 0.80, "Purchase-tax treatment is the main demand lever"),
    ("price_war_rules", "byd", 0.45, "Discount floor protects the biggest discounter's margin"),
    ("price_war_rules", "nio", 0.35, "Relieves pressure on sub-scale players"),
    ("price_war_rules", "xpeng", 0.35, "Same"),
    ("price_war_rules", "ev_demand", -0.35, "Higher effective prices suppress volume"),

    # macro / consumer
    ("pboc_easing", "consumer_credit", 0.80, "Rate and RRR cuts transmit to household credit"),
    ("pboc_easing", "cmb", 0.35, "Volume gain partly offset by margin compression"),
    ("pboc_easing", "ping_an", 0.50, "Rate-sensitive liability book and equity portfolio"),
    ("pboc_easing", "hkex", 0.55, "Liquidity drives turnover, which is HKEX's revenue"),
    ("consumer_credit", "meituan", 0.55, "Discretionary local services spend"),
    ("consumer_credit", "jd", 0.60, "Big-ticket electronics and appliances"),
    ("consumer_credit", "pdd", 0.30, "Value positioning is partly counter-cyclical"),
    ("consumer_credit", "ev_demand", 0.45, "Auto purchases are credit-financed"),
    ("consumer_credit", "zhongan", 0.40, "Embedded insurance rides transaction volume"),
    ("ev_demand", "zhongan", 0.25, "Auto insurance premium volume"),
]

# Ready-made scenarios for the dashboard sandbox.
SCENARIOS = {
    "export_controls_tighten": dict(
        label="US tightens export controls further",
        shocks={"us_export_controls": 1.0},
        note="Positive shock to the control node means controls get stricter. "
             "Watch the split: foundry hurt, domestic toolmakers and accelerators helped.",
    ),
    "smic_yield_breakthrough": dict(
        label="SMIC 7nm yield improves materially",
        shocks={"smic": 1.0},
        note="The single biggest swing factor for Cambricon's 2026 shipment target.",
    ),
    "nev_tax_exemption_ends": dict(
        label="NEV purchase tax exemption ends",
        shocks={"nev_subsidy": -1.0},
        note="Demand shock propagates to every automaker and back up to cells and lithium.",
    ),
    "price_war_enforcement": dict(
        label="Below-cost sales ban enforced hard",
        shocks={"price_war_rules": 1.0},
        note="Margins up, volumes down. The net sign differs by name — that is the point.",
    ),
    "pboc_cuts_again": dict(
        label="PBOC delivers another RRR and rate cut",
        shocks={"pboc_easing": 1.0},
        note="Broad consumer and financials transmission; limited semis effect.",
    ),
    "lithium_spike": dict(
        label="Lithium price spikes",
        shocks={"lithium": 1.0},
        note="Miner up, cell makers squeezed — a clean illustration of signed edges.",
    ),
}


def _adjacency():
    adj = defaultdict(list)
    for src, dst, w, why in EDGES:
        adj[src].append((dst, w, why))
    return adj


def propagate(shocks: dict[str, float], decay: float = 0.65,
              max_hops: int = 4, threshold: float = 0.02) -> dict:
    """
    Breadth-first propagation with per-hop decay.

    A shock loses `1 - decay` of its force at each hop, so second-order effects
    are visible but do not dominate. Contributions from multiple paths sum,
    which is the intended behaviour: a node hit through two routes is more
    exposed than one hit through a single route.

    Returns node impacts and the paths that produced them, so every number on
    the dashboard can be traced back to specific edges.
    """
    adj = _adjacency()
    impact: dict[str, float] = defaultdict(float)
    paths: dict[str, list] = defaultdict(list)

    frontier = [(n, v, [n]) for n, v in shocks.items()]
    for n, v in shocks.items():
        impact[n] += v

    for hop in range(max_hops):
        nxt = []
        for node, value, path in frontier:
            for dst, w, why in adj.get(node, []):
                if dst in path:          # no cycles
                    continue
                delivered = value * w * (decay ** hop)
                if abs(delivered) < threshold:
                    continue
                impact[dst] += delivered
                paths[dst].append(dict(
                    via=" → ".join(NODES[p]["label"] for p in path + [dst]),
                    contribution=round(delivered, 4),
                    hops=hop + 1,
                    rationale=why,
                ))
                nxt.append((dst, delivered, path + [dst]))
        frontier = nxt
        if not frontier:
            break

    results = []
    for node, val in impact.items():
        if node in shocks:
            continue
        meta = NODES[node]
        results.append(dict(
            node=node,
            label=meta["label"],
            kind=meta["kind"],
            sector=meta.get("sector"),
            ticker=meta.get("ticker"),
            impact=round(val, 4),
            paths=sorted(paths[node], key=lambda p: -abs(p["contribution"]))[:3],
        ))

    results.sort(key=lambda r: -abs(r["impact"]))
    return dict(shocks=shocks, results=results)


def graph_payload() -> dict:
    """Node/edge lists for the dashboard's graph view."""
    return dict(
        nodes=[dict(id=k, **v) for k, v in NODES.items()],
        edges=[dict(source=s, target=t, weight=w, rationale=r) for s, t, w, r in EDGES],
        scenarios={k: dict(**v, result=propagate(v["shocks"])) for k, v in SCENARIOS.items()},
    )
