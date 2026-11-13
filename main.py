# Polymarket Next-CEO-of-NVIDIA forecast: per-market calibrated persistence.
#
# Model (one line): each market's Yes price stays at its checkpoint price,
# with a spread that widens like a random walk, but the spread is estimated
# per market from its own recent realised volatility instead of the house
# baseline's single fixed 0.0025 for every market:
#
#   q_tau(h) = clamp(x + z_tau * sigma_m * sqrt(h), 0, 1), rounded to 6 dp
#
# where x is the market's price at the checkpoint, z_tau the standard
# normal quantile at tau in (0.05, 0.25, 0.5, 0.75, 0.95), h = 1..240,
# and sigma_m = clip(0.6 * sd of the market's 1-minute price changes over
# its last 120 minutes, 0.0005, 0.005).
#
# Why this beats the fixed baseline on the practice (measured, not assumed):
# most markets are far quieter than sigma 0.0025 over a 4-hour window --
# the median 120-minute realised 1-minute sd across practice markets is
# about 0.0006, so the baseline's intervals are roughly 3-4x too wide for
# the typical market and it pays pinball loss at every quiet minute.
# A few markets do jump (e.g. a 0.24-point move in one 4-hour window), so
# sigma is floored at 0.0005 (never pretend a market cannot move) and
# capped at 0.005 (a single wild hour must not blow up every interval).
# The 0.6 multiplier, 120-minute window, floor and cap were picked by a
# small grid search scored on practice cases p00-p04, whose answers are
# recoverable from the next case's prices (each case's 240 forecast
# minutes are the next case's first 240 minutes of history); the search
# also tested mean-reversion of the median toward the 60-minute mean and
# drift from the last hour's trend, and both made the score worse, so the
# median stays exactly at the checkpoint price (persistence).
#
# Practice result (p00-p04, scored locally against the next case's prices;
# p05's answer is not in the kit, so it cannot be scored locally):
#   this model  0.301759   vs   house baseline  0.392518
# and it beats the baseline in every one of the five scored cases
# (0.463/0.312/0.333/0.242/0.199 vs 0.536/0.380/0.408/0.369/0.299).
# The house baseline's published full-practice loss is 0.363589; this
# model would need a p05 loss above 0.63 to lose overall, far above any
# plausible value, so the improvement is not a p05 artefact.
#
# Standard library only, deterministic, no network, no randomness.
# Reads $MAKEFUN_INPUT_DIR (else /input) and writes $MAKEFUN_OUTPUT_DIR
# (else /output), one <id>.out per <id>.in, in name order.

import json
import math
import os
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.644854, -0.67449, 0.0, 0.67449, 1.644854)

WINDOW_MINUTES = 120   # minutes of 1-minute changes used for realised vol
SIGMA_MULT = 0.6       # shrink realised sd: 1-minute sd overstates the
                       # persistent component (many moves are one-tick noise)
SIGMA_FLOOR = 0.0005   # never narrower than this per sqrt-minute
SIGMA_CAP = 0.005      # never wider than this per sqrt-minute


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)) * 1e6) / 1e6 + 0.0


def realised_sigma(prices):
    """Per-market sigma from the last WINDOW_MINUTES 1-minute changes."""
    n = len(prices)
    if n < 2:
        return SIGMA_FLOOR
    w = min(WINDOW_MINUTES, n - 1)
    # Population sd of the last w one-minute differences.
    diffs = [prices[i] - prices[i - 1] for i in range(n - w, n)]
    mean = math.fsum(diffs) / w
    var = math.fsum((d - mean) * (d - mean) for d in diffs) / w
    sd = math.sqrt(var) if var > 0.0 else 0.0
    sigma = SIGMA_MULT * sd
    if sigma < SIGMA_FLOOR:
        return SIGMA_FLOOR
    if sigma > SIGMA_CAP:
        return SIGMA_CAP
    return sigma


def forecast_market(market, horizon):
    prices = market["prices"]
    if not prices:
        raise ValueError(f"market {market['id']} has no prices")
    x = prices[-1]
    sigma = realised_sigma(prices)
    sqrt_h = [math.sqrt(h) for h in range(1, horizon + 1)]
    rows = []
    for s in sqrt_h:
        spread = sigma * s
        rows.append([price6(x + z * spread) for z in Z])
    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in INPUT_DIR.iterdir() if p.name.endswith(".in"))
    for path in inputs:
        case_id = path.name[: -len(".in")]
        with path.open("r", encoding="utf-8") as f:
            case = json.load(f)
        horizon = int(case["horizon_minutes"])
        forecasts = [
            {"id": m["id"], "q": forecast_market(m, horizon)}
            for m in case["markets"]
        ]
        out_path = OUTPUT_DIR / f"{case_id}.out"
        with out_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"forecasts": forecasts}) + "\n")


if __name__ == "__main__":
    main()
