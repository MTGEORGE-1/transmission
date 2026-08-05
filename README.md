# China vs US — Where Are the Markets Heading

A sector-by-sector comparison of the Chinese and US markets over the last ten years:
**automotive & EV, AI & internet, fintech, semiconductors, and phones & consumer tech.**
Roughly ten leading companies on each side of each sector — 90 companies in total.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py          # --force to re-fetch (~80s, one API call per company)
open site/index.html
```

Live site: **https://mtgeorge-1.github.io/transmission/** — rebuilt automatically each weekday.

---

## What it found

Ten-year annualised return, equal-weight basket per side:

| Sector | China | United States | |
|---|---|---|---|
| Automotive & EV | 15.6% | 15.9% | level |
| AI & Internet Platforms | 16.5% | **36.3%** | US |
| Fintech & Financial Platforms | **24.8%** | 22.2% | China |
| Semiconductors | 23.8% | **45.1%** | US |
| Phones & Consumer Tech | 22.6% | **37.0%** | US |

The US baskets out-grew the Chinese ones in three of five sectors, and the gap is widest
exactly where it gets talked about most — semiconductors and AI. China's one clear win is
fintech. Automotive is a genuine dead heat, notable given the US side is anchored by Tesla.

**The size gap dwarfs the growth gap.** Across all five sectors the US companies here are
worth roughly **21×** their Chinese counterparts by market value.

## How to read it

- **Growth** means total return on split- and dividend-adjusted prices — what an investor
  would have earned, not how big the business got.
- **Indices are equal-weight**, built from mean daily returns rather than mean prices. Half
  the Chinese basket listed after 2020 (Li Auto and XPeng in 2021, Horizon Robotics in 2024),
  and averaging price levels would put a false step in the index every time a name joined.
  Each company's listing date is shown where its history is short of ten years.
- **Everything is in USD.** yfinance reports market cap in listing currency and financials in
  `financialCurrency`, and the two disagree constantly — BYD reports CNY, SMIC reports USD
  despite listing in Hong Kong. Comparing those unconverted produces a 7× error in China's
  favour. Conversion is at current spot and the rates used are printed in the footer.

## Known limits

- **Revenue CAGR covers ~3 years, not ten.** Free data provides only four annual periods.
  The window length is shown next to every figure rather than glossed.
- **Chinese names are HK listings and US ADRs.** Mainland A-shares are geo-blocked from this
  network, which costs Cambricon, Hygon, NAURA, AMEC and iFlytek — several of China's
  strongest chip and AI names. See [PHASE0_FINDINGS.md](PHASE0_FINDINGS.md). This understates
  China's semiconductor design capability, and the page says so.
- **Ant Group is private**, so China's largest fintech is absent from the fintech sector.
- Supply-chain names (Sunny Optical, BYD Electronic, AAC) legitimately sit in two sectors and
  appear twice.
- Nothing here is a forecast.

## Layout

```
versus/
  sectors.py    the 90-company universe, five sectors, two countries
  ingest.py     prices + fundamentals, USD-normalised, cached
  metrics.py    sector indices, CAGRs, per-company rows, aggregates
  export.py     JSON artifact + site/data.js
run.py          orchestrator
site/index.html the page
```

Deployment: [DEPLOY.md](DEPLOY.md). Every push to `main` rebuilds and redeploys.

## Also in here

`run_regime.py` and `transmission/` are an earlier build — a 4-state hidden Markov regime
classifier for Chinese equities, still working (`python run_regime.py`). It found the June
2015 bubble-to-crash handoff without being told the dates. Kept because the validation result
is worth something; not what the site shows. Original plan in [SCOPING.md](SCOPING.md).
