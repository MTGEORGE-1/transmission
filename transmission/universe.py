"""The curated universe.

Deliberately hand-picked and small (SCOPING.md §8.2 — ~60 names is enough to be
credible and small enough that every inclusion is a decision you can defend).

Every name is HK-listed or a US ADR, because those are what this network can
reach. The A-share leg is geo-blocked from every source tested — akshare,
EastMoney and baostock alike (PHASE0_FINDINGS.md). Where a name has an A-share
twin, `a_share` records it, so the A-H premium feature switches on the moment
that leg becomes reachable (a VPN, or the GitHub Actions runner) rather than
needing the universe rewritten.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Name:
    ticker: str           # yfinance symbol
    label: str
    sector: str           # ev_auto | semis_ai | fintech_consumer
    a_share: str = ""     # A-share code of the same issuer, if one exists
    tags: tuple[str, ...] = field(default_factory=tuple)


UNIVERSE: list[Name] = [
    # ---------------- EV & auto ----------------
    Name("1211.HK", "BYD",                  "ev_auto", a_share="002594", tags=("oem", "battery")),
    Name("2015.HK", "Li Auto",              "ev_auto", tags=("oem",)),
    Name("9868.HK", "XPeng",                "ev_auto", tags=("oem",)),
    Name("9866.HK", "NIO",                  "ev_auto", tags=("oem",)),
    Name("0175.HK", "Geely Automobile",     "ev_auto", tags=("oem",)),
    Name("2333.HK", "Great Wall Motor",     "ev_auto", a_share="601633", tags=("oem",)),
    Name("2238.HK", "GAC Group",            "ev_auto", a_share="601238", tags=("oem",)),
    # Dongfeng (0489.HK) removed — yfinance returns "possibly delisted; no
    # timezone found" for it. Verified via the unresolved-ticker check in
    # ingest.fetch_prices rather than assumed.
    Name("3750.HK", "CATL",                 "ev_auto", a_share="300750", tags=("battery",)),
    Name("1772.HK", "Ganfeng Lithium",      "ev_auto", a_share="002460", tags=("upstream", "lithium")),
    Name("2338.HK", "Weichai Power",        "ev_auto", a_share="000338", tags=("powertrain",)),
    Name("0285.HK", "BYD Electronic",       "ev_auto", tags=("supplier",)),

    # ---------------- Semiconductors & AI ----------------
    Name("0981.HK", "SMIC",                 "semis_ai", a_share="688981", tags=("foundry", "policy_core")),
    Name("1347.HK", "Hua Hong Semi",        "semis_ai", a_share="688347", tags=("foundry",)),
    Name("9660.HK", "Horizon Robotics",     "semis_ai", tags=("ai_chip",)),
    Name("2533.HK", "Black Sesame Intl",    "semis_ai", tags=("ai_chip",)),
    Name("0522.HK", "ASMPT",                "semis_ai", tags=("equipment",)),
    Name("2382.HK", "Sunny Optical",        "semis_ai", tags=("components",)),
    Name("0992.HK", "Lenovo",               "semis_ai", tags=("hardware",)),
    Name("1810.HK", "Xiaomi",               "semis_ai", tags=("hardware", "oem")),
    Name("0700.HK", "Tencent",              "semis_ai", tags=("ai_capex", "platform")),
    Name("9988.HK", "Alibaba",              "semis_ai", tags=("ai_capex", "platform")),
    Name("9888.HK", "Baidu",                "semis_ai", tags=("ai_capex", "platform")),
    Name("0268.HK", "Kingdee Intl",         "semis_ai", tags=("software",)),

    # ---------------- Fintech & consumer ----------------
    Name("3690.HK", "Meituan",              "fintech_consumer", tags=("platform",)),
    Name("9618.HK", "JD.com",               "fintech_consumer", tags=("platform",)),
    Name("1024.HK", "Kuaishou",             "fintech_consumer", tags=("platform",)),
    Name("2318.HK", "Ping An Insurance",    "fintech_consumer", a_share="601318", tags=("financial",)),
    Name("3968.HK", "China Merchants Bank", "fintech_consumer", a_share="600036", tags=("bank",)),
    Name("1398.HK", "ICBC",                 "fintech_consumer", a_share="601398", tags=("bank", "policy_core")),
    Name("6060.HK", "ZhongAn Online",       "fintech_consumer", tags=("insurtech",)),
    Name("0388.HK", "HKEX",                 "fintech_consumer", tags=("exchange",)),
    Name("9633.HK", "Nongfu Spring",        "fintech_consumer", tags=("staples",)),
    Name("2020.HK", "Anta Sports",          "fintech_consumer", tags=("discretionary",)),
    Name("1928.HK", "Sands China",          "fintech_consumer", tags=("discretionary",)),
    Name("6618.HK", "JD Health",            "fintech_consumer", tags=("healthcare",)),

    # ---------------- US ADRs (independent venue, useful cross-check) ----------------
    Name("BABA", "Alibaba ADR",  "semis_ai",         tags=("adr",)),
    Name("PDD",  "PDD Holdings", "fintech_consumer", tags=("adr", "platform")),
    Name("NIO",  "NIO ADR",      "ev_auto",          tags=("adr",)),
    Name("LI",   "Li Auto ADR",  "ev_auto",          tags=("adr",)),
]

# Benchmarks. CSI 300 comes from akshare (reachable, history back to 2002).
# ^HSTECH returned empty in the Phase 0 audit — a symbol problem, not the
# firewall — so 3067.HK (iShares Hang Seng TECH ETF) stands in as the HK tech
# proxy.
BENCHMARKS = {
    "csi300": {"source": "akshare", "symbol": "sh000300", "label": "CSI 300"},
    "hsi": {"source": "yfinance", "symbol": "^HSI", "label": "Hang Seng Index"},
    "hstech_proxy": {"source": "yfinance", "symbol": "3067.HK", "label": "Hang Seng TECH (ETF proxy)"},
}

SECTORS = {
    "ev_auto": "EV & Auto",
    "semis_ai": "Semiconductors & AI",
    "fintech_consumer": "Fintech & Consumer",
}


def by_sector(sector: str) -> list[Name]:
    return [n for n in UNIVERSE if n.sector == sector]


def tickers() -> list[str]:
    return [n.ticker for n in UNIVERSE]


def label_of(ticker: str) -> str:
    for n in UNIVERSE:
        if n.ticker == ticker:
            return n.label
    return ticker
