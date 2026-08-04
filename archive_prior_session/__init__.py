"""
Transmission — a policy-transmission model engine for Chinese tech equities.

Thesis: Chinese tech equities are priced by policy, not by earnings.
This package quantifies that.

Layers:
    config      universe and constants
    ingest      live data (AkShare / yfinance)
    demo_data   synthetic fallback so the pipeline runs before ingest is wired
    policy      hand-scored policy corpus + stance index + event studies
    features    causal feature construction
    regime      Gaussian HMM regime classifier
    graph       supply-chain shock propagation
    build       orchestrator -> data/transmission.json
"""

__version__ = "0.1.0"
