# polymarket-nvidia-ceo-forecast

Forecast of the Yes price of every trading market of Polymarket's
"Next CEO of NVIDIA?" event, 4 hours ahead, minute by minute, as five
quantiles (0.05 / 0.25 / 0.5 / 0.75 / 0.95) — entry for
`polymarket-nvidia-ceo-forecast-01` on make.fun.

## Model

Per-market calibrated persistence. For market `m` with checkpoint price
`x`, horizon minute `h = 1..240`:

```
q_tau(h) = clamp(x + z_tau * sigma_m * sqrt(h), 0, 1)   (rounded to 6 dp)
```

- `z_tau` is the standard-normal quantile at each level.
- `sigma_m = clip(0.6 * sd of the market's 1-minute price changes over
  its last 120 minutes, 0.0005, 0.005)`.

That is the house baseline's random-walk spread, except the spread is
estimated per market from its own recent realised volatility instead of
using the baseline's single fixed 0.0025 for every market.

## Why this should beat the baseline

Most markets are far quieter than sigma 0.0025 over a 4-hour window:
the median 120-minute realised 1-minute sd across practice markets is
about 0.0006, so the baseline's intervals are roughly 3–4x too wide for
the typical market and it pays pinball loss at every quiet minute. A
few markets do jump hard (a 0.24-point move inside one 4-hour window),
so sigma is floored at 0.0005 and capped at 0.005. The 0.6 multiplier,
120-minute window, floor and cap come from a small grid search scored
on practice cases p00–p04 (each case's 240 forecast minutes are the
next case's first 240 minutes of history, so the answers are
recoverable locally). The same search tested mean-reversion of the
median toward the 60-minute mean and drift from the last hour's trend;
both made the score worse, so the median stays at the checkpoint price.

## Practice results (measured locally, p00–p04)

| case | this model | house baseline |
|------|-----------:|---------------:|
| p00  | 0.462735   | 0.5361         |
| p01  | 0.311474   | 0.3804         |
| p02  | 0.333166   | 0.4084         |
| p03  | 0.241802   | 0.3686         |
| p04  | 0.199224   | 0.2988         |
| **weighted mean** | **0.301759** | **0.392518** |

The model beats the baseline in every scored case. Case p05's answer
is not in the kit, so it cannot be scored locally; the house baseline's
published full-practice (p00–p05) loss is 0.363589, and this model
would need a p05 loss above 0.63 to lose overall — far above any
plausible value — so the improvement is not a p05 artefact.

## Running it

Python 3.13, standard library only, deterministic, no network:

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `<id>.in` in the input directory and writes
`<id>.out` to the output directory (or `/input` / `/output` when the
environment variables are unset, as in the grader). All six practice
cases run in ~0.3 s total locally, far under the 8 s per-case cap;
every output is well under the 1 MiB limit and byte-identical across
runs (verified by running twice and diffing).
