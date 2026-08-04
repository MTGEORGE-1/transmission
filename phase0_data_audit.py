#!/usr/bin/env python3
"""
Phase 0 — Data source availability audit.

Run this on your own machine (not in a sandbox) to find out which China
market/macro data sources you can actually reach. Everything in SCOPING.md
assumes the results of this script.

    pip install akshare yfinance baostock pandas
    python phase0_data_audit.py

Writes results to phase0_audit_results.json and prints a summary table.
"""

import json
import time
import traceback
from datetime import datetime

RESULTS = []


def check(name, category, fn, note=""):
    """Run one probe, record outcome and latency."""
    start = time.time()
    try:
        rows, sample = fn()
        RESULTS.append({
            "source": name,
            "category": category,
            "status": "OK" if rows else "EMPTY",
            "rows": rows,
            "seconds": round(time.time() - start, 2),
            "sample": sample,
            "note": note,
            "error": None,
        })
    except Exception as e:
        RESULTS.append({
            "source": name,
            "category": category,
            "status": "FAIL",
            "rows": 0,
            "seconds": round(time.time() - start, 2),
            "sample": None,
            "note": note,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        })


# --------------------------------------------------------------------------
# AkShare — the intended backbone
# --------------------------------------------------------------------------
def probe_akshare():
    import akshare as ak
    print(f"  akshare version: {ak.__version__}")

    check("akshare: A-share spot (EastMoney)", "equity",
          lambda: (len(d := ak.stock_zh_a_spot_em()), list(d.columns[:6])),
          "Real-time quotes for all A-shares. Core universe builder.")

    check("akshare: BYD daily history (002594)", "equity",
          lambda: (len(d := ak.stock_zh_a_hist(symbol="002594", period="daily",
                                               start_date="20240101", end_date="20260801",
                                               adjust="qfq")), list(d.columns[:6])),
          "Adjusted daily OHLCV. Needed for every price series.")

    check("akshare: SMIC daily history (688981)", "equity",
          lambda: (len(d := ak.stock_zh_a_hist(symbol="688981", period="daily",
                                               start_date="20240101", end_date="20260801",
                                               adjust="qfq")), list(d.columns[:6])),
          "STAR Market coverage check — semis names live here.")

    check("akshare: HK spot", "equity",
          lambda: (len(d := ak.stock_hk_spot_em()), list(d.columns[:6])),
          "Hong Kong listings. Needed for the A-H premium feature.")

    check("akshare: macro China GDP", "macro",
          lambda: (len(d := ak.macro_china_gdp()), list(d.columns[:6])),
          "Baseline macro.")

    check("akshare: macro China CPI", "macro",
          lambda: (len(d := ak.macro_china_cpi()), list(d.columns[:6])),
          "Baseline macro.")

    check("akshare: macro China M2 / money supply", "macro",
          lambda: (len(d := ak.macro_china_money_supply()), list(d.columns[:6])),
          "Input to credit impulse.")

    check("akshare: China PMI", "macro",
          lambda: (len(d := ak.macro_china_pmi()), list(d.columns[:6])),
          "Regime model feature.")

    check("akshare: China bond yield curve", "macro",
          lambda: (len(d := ak.bond_china_yield(start_date="20250101",
                                                end_date="20260801")), list(d.columns[:6])),
          "Rates context for policy stance validation.")

    check("akshare: CSI 300 index history", "index",
          lambda: (len(d := ak.stock_zh_index_daily(symbol="sh000300")), list(d.columns[:6])),
          "Primary benchmark for regime bands.")


# --------------------------------------------------------------------------
# yfinance — HK listings and US ADRs
# --------------------------------------------------------------------------
def probe_yfinance():
    import yfinance as yf

    def dl(ticker):
        d = yf.download(ticker, start="2024-01-01", progress=False, auto_adjust=False)
        return len(d), list(map(str, d.columns[:4]))

    check("yfinance: 0700.HK (Tencent)", "equity", lambda: dl("0700.HK"),
          "HK listing coverage.")
    check("yfinance: 1211.HK (BYD H-share)", "equity", lambda: dl("1211.HK"),
          "A-H pair with 002594. Direct premium calculation.")
    check("yfinance: BABA (Alibaba ADR)", "equity", lambda: dl("BABA"),
          "ADR coverage — AI capex proxy.")
    check("yfinance: NIO", "equity", lambda: dl("NIO"),
          "US-listed EV name.")
    check("yfinance: ^HSTECH (Hang Seng Tech)", "index", lambda: dl("^HSTECH"),
          "Secondary benchmark.")


# --------------------------------------------------------------------------
# Baostock — cross-check on AkShare price data
# --------------------------------------------------------------------------
def probe_baostock():
    import baostock as bs

    def query():
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"login failed: {lg.error_msg}")
        rs = bs.query_history_k_data_plus(
            "sz.002594", "date,code,open,high,low,close,volume",
            start_date="2024-01-01", end_date="2026-08-01",
            frequency="d", adjustflag="2")
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        return len(rows), rows[0] if rows else None

    check("baostock: BYD daily (sz.002594)", "equity", query,
          "Independent price source. Use to validate AkShare adjustments.")


# --------------------------------------------------------------------------
# Policy text sources — reachability only, not parsing
# --------------------------------------------------------------------------
def probe_policy_sites():
    import requests

    sites = [
        ("PBOC", "http://www.pbc.gov.cn/", "Monetary policy statements."),
        ("NDRC", "https://www.ndrc.gov.cn/", "Industrial policy, Five-Year Plan detail."),
        ("MIIT", "https://www.miit.gov.cn/", "Semis, EV, telecom policy. Highest-value source."),
        ("State Council", "https://www.gov.cn/", "Top-level announcements, Politburo readouts."),
        ("NBS", "https://www.stats.gov.cn/", "Official statistics releases."),
    ]

    for name, url, note in sites:
        def fetch(u=url):
            r = requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            return (len(r.content) if r.status_code == 200 else 0), f"HTTP {r.status_code}"
        check(f"policy site: {name}", "policy", fetch, note)


# --------------------------------------------------------------------------

def main():
    print(f"Phase 0 data audit — {datetime.now().isoformat(timespec='seconds')}\n")

    for label, fn in [
        ("AkShare", probe_akshare),
        ("yfinance", probe_yfinance),
        ("Baostock", probe_baostock),
        ("Policy sites", probe_policy_sites),
    ]:
        print(f"[{label}]")
        try:
            fn()
        except ImportError as e:
            print(f"  SKIPPED — {e}")
        except Exception:
            print(f"  probe group crashed:\n{traceback.format_exc()}")
        print()

    # summary
    width = max(len(r["source"]) for r in RESULTS) + 2
    print("=" * (width + 30))
    print(f"{'SOURCE':<{width}} {'STATUS':<8} {'ROWS':>8} {'SECS':>7}")
    print("=" * (width + 30))
    for r in RESULTS:
        print(f"{r['source']:<{width}} {r['status']:<8} {r['rows']:>8} {r['seconds']:>7}")
        if r["error"]:
            print(f"{'':<{width}} └─ {r['error']}")

    ok = sum(1 for r in RESULTS if r["status"] == "OK")
    print("=" * (width + 30))
    print(f"{ok}/{len(RESULTS)} sources reachable\n")

    with open("phase0_audit_results.json", "w") as f:
        json.dump({"run_at": datetime.now().isoformat(), "results": RESULTS}, f,
                  indent=2, ensure_ascii=False)
    print("Written to phase0_audit_results.json")

    failed = [r["source"] for r in RESULTS if r["status"] != "OK"]
    if failed:
        print("\nNeeds a fallback plan:")
        for s in failed:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
