"""Paths and run-wide constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
ARTIFACTS = DATA / "artifacts"
SITE = ROOT / "site"

for _d in (CACHE, ARTIFACTS, SITE):
    _d.mkdir(parents=True, exist_ok=True)

# 2015 start captures the 2015 crash, 2018 trade war, 2021 crackdown and the
# 2024-26 stimulus cycle — four distinct regimes (SCOPING.md §8.3).
START_DATE = "2015-01-01"

# Chinese endpoints are flaky and rate-limited (a transient
# ChunkedEncodingError showed up during development). Cache hard, retry, and
# never let a rebuild depend on a live call succeeding.
CACHE_TTL_HOURS = 20
HTTP_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0

RANDOM_SEED = 7

# Latent states for the regime HMM (SCOPING.md L3 Model B).
N_REGIMES = 4

# Publication lags, in calendar days, applied to monthly macro series so that
# no feature uses a number before it was actually released. Deliberately
# conservative — over-lagging costs a little signal, under-lagging invalidates
# every backtest downstream.
PUB_LAG_DAYS = {
    "m2": 45,    # money supply for month M lands mid-M+1
    "pmi": 3,    # NBS PMI lands on the last day of M / first of M+1
}

# A block page served by an intercepting firewall is still HTTP 200. Any
# response containing this is data loss masquerading as success.
BLOCKPAGE_MARKERS = ("Connection denied by Geolocation", "Fireware")
