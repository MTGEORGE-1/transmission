"""The comparison universe: five sectors, roughly ten Chinese and ten US names each.

Chinese names are Hong Kong listings or US ADRs. Mainland A-shares are
geo-blocked from this network (see PHASE0_FINDINGS.md), which costs a handful
of names with no offshore listing — Cambricon, Hygon, NAURA, iFlytek, East
Money. Where that materially weakens a sector it is called out in NOTES below
rather than left for a reader to notice.

Every ticker here was verified to return data from yfinance before being
included; five candidates were dropped after failing that check (Zeekr and
Dongfeng, both taken private; OneConnect; Juniper, acquired by HPE; and Fiserv
under its post-2023 symbol).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Co:
    ticker: str
    name: str
    country: str  # CN | US


SECTORS: dict[str, dict] = {
    "auto": {
        "label": "Automotive & EV",
        "blurb": "China's clearest win. BYD outsells Tesla, and the domestic price war has "
                 "pushed margins down across the board while volumes climb.",
        "cn": [
            Co("1211.HK", "BYD", "CN"),
            Co("0175.HK", "Geely Automobile", "CN"),
            Co("2015.HK", "Li Auto", "CN"),
            Co("9868.HK", "XPeng", "CN"),
            Co("9866.HK", "NIO", "CN"),
            Co("2333.HK", "Great Wall Motor", "CN"),
            Co("2238.HK", "GAC Group", "CN"),
            Co("9863.HK", "Leapmotor", "CN"),
            Co("2338.HK", "Weichai Power", "CN"),
            Co("0285.HK", "BYD Electronic", "CN"),
        ],
        "us": [
            Co("TSLA", "Tesla", "US"),
            Co("GM", "General Motors", "US"),
            Co("F", "Ford", "US"),
            Co("RIVN", "Rivian", "US"),
            Co("LCID", "Lucid", "US"),
            Co("STLA", "Stellantis", "US"),
            Co("APTV", "Aptiv", "US"),
            Co("BWA", "BorgWarner", "US"),
            Co("CMI", "Cummins", "US"),
            Co("PCAR", "Paccar", "US"),
        ],
    },
    "ai": {
        "label": "AI & Internet Platforms",
        "blurb": "The widest gap in the whole comparison. US names carry the AI capex cycle; "
                 "Chinese platforms are rebuilding after the 2021 crackdown.",
        "cn": [
            Co("BABA", "Alibaba", "CN"),
            Co("0700.HK", "Tencent", "CN"),
            Co("9888.HK", "Baidu", "CN"),
            Co("0020.HK", "SenseTime", "CN"),
            Co("KC", "Kingsoft Cloud", "CN"),
            Co("9660.HK", "Horizon Robotics", "CN"),
            Co("6682.HK", "4Paradigm", "CN"),
            Co("0268.HK", "Kingdee International", "CN"),
            Co("3888.HK", "Kingsoft", "CN"),
            Co("1024.HK", "Kuaishou", "CN"),
        ],
        "us": [
            Co("NVDA", "NVIDIA", "US"),
            Co("MSFT", "Microsoft", "US"),
            Co("GOOGL", "Alphabet", "US"),
            Co("META", "Meta Platforms", "US"),
            Co("AMZN", "Amazon", "US"),
            Co("PLTR", "Palantir", "US"),
            Co("AMD", "AMD", "US"),
            Co("ORCL", "Oracle", "US"),
            Co("IBM", "IBM", "US"),
            Co("NOW", "ServiceNow", "US"),
        ],
    },
    "fintech": {
        "label": "Fintech & Financial Platforms",
        "blurb": "Ant Group's pulled IPO still defines this sector. The listed Chinese names "
                 "are brokers and lenders; the US set is payment rails with far deeper moats.",
        "cn": [
            Co("FUTU", "Futu Holdings", "CN"),
            Co("TIGR", "UP Fintech", "CN"),
            Co("QFIN", "Qifu Technology", "CN"),
            Co("LX", "LexinFintech", "CN"),
            Co("FINV", "FinVolution", "CN"),
            Co("6060.HK", "ZhongAn Online", "CN"),
            Co("LU", "Lufax", "CN"),
            Co("YRD", "Yiren Digital", "CN"),
            Co("0388.HK", "HKEX", "CN"),
            Co("2318.HK", "Ping An Insurance", "CN"),
        ],
        "us": [
            Co("V", "Visa", "US"),
            Co("MA", "Mastercard", "US"),
            Co("PYPL", "PayPal", "US"),
            Co("XYZ", "Block", "US"),
            Co("COIN", "Coinbase", "US"),
            Co("SOFI", "SoFi Technologies", "US"),
            Co("AFRM", "Affirm", "US"),
            Co("INTU", "Intuit", "US"),
            Co("HOOD", "Robinhood", "US"),
            Co("FIS", "Fidelity National Info", "US"),
        ],
    },
    "semis": {
        "label": "Semiconductors",
        "blurb": "The sector policy touches most directly. Export controls cap what SMIC can "
                 "build; US names ride the same controls as a moat.",
        "cn": [
            Co("0981.HK", "SMIC", "CN"),
            Co("1347.HK", "Hua Hong Semiconductor", "CN"),
            Co("0522.HK", "ASMPT", "CN"),
            Co("1385.HK", "Shanghai Fudan Micro", "CN"),
            Co("2018.HK", "AAC Technologies", "CN"),
            Co("1478.HK", "Q Technology", "CN"),
            Co("2382.HK", "Sunny Optical", "CN"),
            Co("6088.HK", "FIT Hon Teng", "CN"),
            Co("0763.HK", "ZTE", "CN"),
            Co("0285.HK", "BYD Electronic", "CN"),
        ],
        "us": [
            Co("NVDA", "NVIDIA", "US"),
            Co("AVGO", "Broadcom", "US"),
            Co("AMD", "AMD", "US"),
            Co("INTC", "Intel", "US"),
            Co("MU", "Micron", "US"),
            Co("QCOM", "Qualcomm", "US"),
            Co("TXN", "Texas Instruments", "US"),
            Co("AMAT", "Applied Materials", "US"),
            Co("LRCX", "Lam Research", "US"),
            Co("KLAC", "KLA Corporation", "US"),
        ],
    },
    "phones": {
        "label": "Phones & Consumer Tech",
        "blurb": "Chinese hardware competes on volume and price; Apple takes most of the "
                 "industry's profit. The clearest revenue-vs-margin contrast in the set.",
        "cn": [
            Co("1810.HK", "Xiaomi", "CN"),
            Co("0992.HK", "Lenovo", "CN"),
            Co("0763.HK", "ZTE", "CN"),
            Co("2018.HK", "AAC Technologies", "CN"),
            Co("2382.HK", "Sunny Optical", "CN"),
            Co("0285.HK", "BYD Electronic", "CN"),
            Co("1478.HK", "Q Technology", "CN"),
            Co("6088.HK", "FIT Hon Teng", "CN"),
            Co("1415.HK", "Cowell e Holdings", "CN"),
            Co("0522.HK", "ASMPT", "CN"),
        ],
        "us": [
            Co("AAPL", "Apple", "US"),
            Co("DELL", "Dell Technologies", "US"),
            Co("HPQ", "HP Inc.", "US"),
            Co("HPE", "Hewlett Packard Enterprise", "US"),
            Co("MSI", "Motorola Solutions", "US"),
            Co("GLW", "Corning", "US"),
            Co("GRMN", "Garmin", "US"),
            Co("WDC", "Western Digital", "US"),
            Co("STX", "Seagate", "US"),
            Co("ANET", "Arista Networks", "US"),
        ],
    },
}

# Stated plainly on the page rather than buried.
NOTES = {
    "semis": "China's strongest pure-play chip designers — Cambricon, Hygon, NAURA, AMEC — "
             "list only on mainland exchanges and are unreachable from this network, so the "
             "Chinese basket here leans toward packaging, optics and components. It "
             "understates China's design capability and overstates its supply-chain tilt.",
    "ai": "iFlytek and several AI names are A-share only and excluded. Horizon Robotics "
          "(2024) and 4Paradigm (2023) listed recently, so the Chinese basket has far less "
          "history than the US one.",
    "fintech": "Ant Group, by far China's largest fintech, is private — its 2020 IPO was "
               "pulled by regulators. Its absence is itself the story of the sector.",
}


def all_tickers() -> list[str]:
    out = set()
    for s in SECTORS.values():
        for side in ("cn", "us"):
            out.update(c.ticker for c in s[side])
    return sorted(out)


def all_companies() -> dict[str, Co]:
    out = {}
    for s in SECTORS.values():
        for side in ("cn", "us"):
            for c in s[side]:
                out[c.ticker] = c
    return out
