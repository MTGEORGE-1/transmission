"""
Universe definition and shared constants.

Tickers are kept small and hand-curated on purpose — ~30 names across three
sectors is enough to be credible and small enough that every inclusion is a
decision you can defend. Widening the universe adds noise, not signal.
"""

START_DATE = "2015-01-01"
END_DATE = "2026-08-01"

SECTORS = ["ev_auto", "semis_ai", "fintech_consumer"]

SECTOR_LABELS = {
    "ev_auto": "EV & Auto",
    "semis_ai": "Semiconductors & AI",
    "fintech_consumer": "Fintech & Consumer",
}

# venue: A = mainland A-share, HK = Hong Kong, US = ADR
# ah_pair: the counterpart listing, for A-H premium calculation
UNIVERSE = [
    # ---- EV & Auto -------------------------------------------------------
    dict(ticker="002594.SZ", name="BYD",              sector="ev_auto", venue="A",  ah_pair="1211.HK"),
    dict(ticker="1211.HK",   name="BYD (H)",          sector="ev_auto", venue="HK", ah_pair="002594.SZ"),
    dict(ticker="300750.SZ", name="CATL",             sector="ev_auto", venue="A",  ah_pair=None),
    dict(ticker="NIO",       name="NIO",              sector="ev_auto", venue="US", ah_pair=None),
    dict(ticker="LI",        name="Li Auto",          sector="ev_auto", venue="US", ah_pair=None),
    dict(ticker="XPEV",      name="XPeng",            sector="ev_auto", venue="US", ah_pair=None),
    dict(ticker="9868.HK",   name="XPeng (HK)",       sector="ev_auto", venue="HK", ah_pair=None),
    dict(ticker="601633.SS", name="Great Wall Motor", sector="ev_auto", venue="A",  ah_pair="2333.HK"),
    dict(ticker="600104.SS", name="SAIC Motor",       sector="ev_auto", venue="A",  ah_pair=None),
    dict(ticker="002460.SZ", name="Ganfeng Lithium",  sector="ev_auto", venue="A",  ah_pair="1772.HK"),

    # ---- Semiconductors & AI --------------------------------------------
    dict(ticker="688981.SS", name="SMIC",             sector="semis_ai", venue="A",  ah_pair="0981.HK"),
    dict(ticker="0981.HK",   name="SMIC (H)",         sector="semis_ai", venue="HK", ah_pair="688981.SS"),
    dict(ticker="688256.SS", name="Cambricon",        sector="semis_ai", venue="A",  ah_pair=None),
    dict(ticker="688041.SS", name="Hygon",            sector="semis_ai", venue="A",  ah_pair=None),
    dict(ticker="1347.HK",   name="Hua Hong Semi",    sector="semis_ai", venue="HK", ah_pair="688347.SS"),
    dict(ticker="002371.SZ", name="NAURA",            sector="semis_ai", venue="A",  ah_pair=None),
    dict(ticker="688012.SS", name="AMEC",             sector="semis_ai", venue="A",  ah_pair=None),
    dict(ticker="BABA",      name="Alibaba",          sector="semis_ai", venue="US", ah_pair="9988.HK"),
    dict(ticker="9988.HK",   name="Alibaba (HK)",     sector="semis_ai", venue="HK", ah_pair="BABA"),
    dict(ticker="0700.HK",   name="Tencent",          sector="semis_ai", venue="HK", ah_pair=None),
    dict(ticker="9888.HK",   name="Baidu (HK)",       sector="semis_ai", venue="HK", ah_pair="BIDU"),
    dict(ticker="002230.SZ", name="iFlytek",          sector="semis_ai", venue="A",  ah_pair=None),

    # ---- Fintech & Consumer ---------------------------------------------
    dict(ticker="3690.HK",   name="Meituan",          sector="fintech_consumer", venue="HK", ah_pair=None),
    dict(ticker="9618.HK",   name="JD.com (HK)",      sector="fintech_consumer", venue="HK", ah_pair="JD"),
    dict(ticker="PDD",       name="PDD Holdings",     sector="fintech_consumer", venue="US", ah_pair=None),
    dict(ticker="6060.HK",   name="ZhongAn Online",   sector="fintech_consumer", venue="HK", ah_pair=None),
    dict(ticker="601318.SS", name="Ping An",          sector="fintech_consumer", venue="A",  ah_pair="2318.HK"),
    dict(ticker="600036.SS", name="China Merchants Bank", sector="fintech_consumer", venue="A", ah_pair="3968.HK"),
    dict(ticker="1024.HK",   name="Kuaishou",         sector="fintech_consumer", venue="HK", ah_pair=None),
    dict(ticker="0388.HK",   name="HKEX",             sector="fintech_consumer", venue="HK", ah_pair=None),
]

BENCHMARKS = {
    "csi300": dict(ticker="sh000300", name="CSI 300",        source="akshare"),
    "hstech": dict(ticker="^HSTECH",  name="Hang Seng Tech", source="yfinance"),
}

# Regime model configuration
N_REGIMES = 4

REGIME_NAMES = {
    0: "Stimulus Risk-On",
    1: "Grinding Consolidation",
    2: "Policy Stress",
    3: "Retail Euphoria",
}

REGIME_COLORS = {
    0: "#2f9e6e",
    1: "#8a8f98",
    2: "#c8503f",
    3: "#d99a2b",
}

REGIME_FEATURES = [
    "credit_impulse",
    "realized_vol",
    "breadth",
    "ah_premium",
    "policy_stance",
    "momentum_3m",
]
