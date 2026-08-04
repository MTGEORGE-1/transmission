# Phase 0 — Data Audit Results

**Run:** 2026-08-04 14:31, macOS, Python 3.14.4, akshare 1.18.81, yfinance 1.5.2
**Raw output:** `phase0_audit_results.json`
**Headline:** 12 / 20 sources reachable. All 8 failures share one root cause.

---

## 1. The root cause — network geo-blocking, not China-side blocking

Every failure returned an SSL error. That looked like a certificate problem, but
the certificate presented on the failing hosts is:

```
subject= /O=WatchGuard/OU=Fireware/CN=Fireware web CA
issuer=  /O=WatchGuard/OU=Fireware/CN=Fireware web CA   (self-signed)
```

Fetching with verification disabled reveals the actual payload:

```html
<title>Connection denied by Geolocation</title>
```

**A WatchGuard Fireware firewall on this network is blocking hosts with
China-geolocated IPs.** It is not the Great Firewall, not akshare breaking, and
not a certificate that can be fixed by adding a CA — the appliance serves its
own cert for a block page, so hostname verification can never succeed and the
content behind it is the block page regardless.

This means: **disabling SSL verification will not help.** Any code that does
`verify=False` to "fix" these endpoints will silently parse a block page as data.
Worth guarding against explicitly in `ingest.py`.

### Fixes, in order of preference
1. **Run the pipeline from a different network** — home Wi-Fi or a phone hotspot.
   The appliance is on this LAN.
2. **VPN / proxy with a non-blocked egress.**
3. **Run ingest in GitHub Actions.** The scoping doc already calls for a nightly
   Actions job. GitHub's runners are not behind this firewall, so the blocked
   sources will likely work there even when they fail locally. *This is the
   strongest option* — it makes the block irrelevant to the real pipeline and
   only affects local development.

---

## 2. What works right now

| Source | Result |
|---|---|
| akshare — macro China GDP | OK, 82 rows |
| akshare — macro China CPI | OK, 222 rows |
| akshare — macro M2 / money supply | OK, 222 rows |
| akshare — China PMI | OK, 223 rows |
| akshare — CSI 300 index history | **OK, 5,963 rows** |
| yfinance — 0700.HK Tencent | OK, 635 rows |
| yfinance — 1211.HK BYD (H) | OK, 635 rows |
| yfinance — BABA | OK, 649 rows |
| yfinance — NIO | OK, 649 rows |
| PBOC site | OK |
| NDRC site | OK, 87 KB |
| State Council site | OK, 67 KB |

Note the split inside akshare: its **macro and index endpoints work** (different
hosts), while everything routed through EastMoney fails.

## 3. What is blocked

| Source | Cause |
|---|---|
| akshare — A-share spot (EastMoney) | geo-block |
| akshare — A-share daily history, BYD 002594 | geo-block (`push2his.eastmoney.com`) |
| akshare — A-share daily history, SMIC 688981 | geo-block |
| akshare — HK spot (EastMoney) | geo-block |
| akshare — China bond yield curve | geo-block (`yield.chinabond.com.cn`) |
| MIIT site | geo-block |
| NBS site | geo-block |
| yfinance — `^HSTECH` | **not a geo-block** — symbol returns empty |

---

## 4. Consequences for the build

**The A-share leg is unavailable locally.** Everything routed through EastMoney
is down, which is akshare's entire equity price backbone.

Three consequences that change the plan:

1. **The A-H premium feature cannot be computed locally.** It needs both legs and
   only the H leg is reachable. It is listed in `config.REGIME_FEATURES` — it
   must either come from Actions, or be dropped from the local feature set
   rather than silently filled with nulls.
2. **A-share-only names are unavailable locally** — including **Cambricon
   (688256)**, which is the single best illustration of the project's thesis, plus
   Hygon, NAURA, AMEC and iFlytek.
3. **The HK leg is fully open, and it is enough.** SMIC (0981.HK), BYD (1211.HK),
   Hua Hong (1347.HK), Xiaomi, Tencent, Alibaba, Meituan and the US ADRs all
   return clean history via yfinance. A credible three-sector universe is
   buildable today with no A-shares at all.

**Recommended split:** treat yfinance HK/ADR + akshare macro/index as the local
development path, and put the A-share and MIIT/NBS ingest behind the GitHub
Actions job where the firewall does not apply. Stamp every artifact with which
sources actually resolved, per the data-lineage goal in SCOPING.md §6.

## 5. Small fix needed

`^HSTECH` returns empty from yfinance — this is a symbol issue, not the firewall.
Use `3067.HK` (iShares Hang Seng TECH ETF) or `^HSI` as the HK tech proxy.

---

## 6. Environment notes

- Python **3.14.4**. pandas resolved to **3.0.5** and numpy to **2.5.1** — both
  majors where `fillna(method=...)`, `.append()` and `'M'` resample aliases are
  removed. Code written against pandas 1.x/2.x idioms will break.
- `baostock` was installed and tested separately **after** the audit run: it is
  also blocked (`10002007 网络接收错误` / broken pipe). It uses a raw socket
  protocol to China-hosted servers, so the same appliance stops it. **No tested
  source provides A-share prices on this network.**
- Working venv at `.venv/` with akshare, yfinance, pandas, numpy, requests.
