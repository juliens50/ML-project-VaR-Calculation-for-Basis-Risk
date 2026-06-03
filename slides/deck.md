---
marp: true
theme: default
paginate: true
math: katex
---

<!--
NOTE: theme is a placeholder. Once Julien provides the IFP / personal slide
template, translate it into a Marp CSS theme and swap `theme:` above (or add a
<style> block / external theme file). Content below is template-independent.
Render: VS Code "Marp for VS Code" extension -> export PDF/PPTX,
or:  npx @marp-team/marp-cli slides/deck.md --pdf
-->

<style>
:root { --ifp-blue: #167ABF; --ifp-ink: #1f2937; }

section {
  font-family: "Lato", "Helvetica Neue", Arial, sans-serif;
  font-size: 24px;
  color: var(--ifp-ink);
  padding: 54px 64px 76px 64px;
  background-image: url("assets/ifp_logo_color.png");
  background-repeat: no-repeat;
  background-position: bottom 18px right 28px;
  background-size: 66px;
}
h1, h2, h3 { color: var(--ifp-blue); font-variant: small-caps; letter-spacing: .4px; font-weight: 700; }
h2 { font-size: 33px; border-bottom: 2px solid var(--ifp-blue); padding-bottom: 10px; margin-bottom: 26px; }
ul { list-style: none; padding-left: 0; }
li { position: relative; padding-left: 26px; margin: 13px 0; line-height: 1.42; }
li::before { content: "▪"; color: var(--ifp-blue); position: absolute; left: 0; top: 0; }
strong { color: var(--ifp-blue); }
img { display: block; margin: 6px auto; }
section::after { color: var(--ifp-blue); font-size: 15px; right: 102px; bottom: 26px; }

/* Title / closing slides */
section.lead {
  background-color: var(--ifp-blue);
  color: #ffffff;
  display: flex; flex-direction: column;
  justify-content: center; align-items: center; text-align: center;
  background-image: url("assets/ifp_logo_white.png");
  background-position: bottom 34px center;
  background-size: 90px;
}
section.lead h1, section.lead h2 { color: #ffffff; border: none; font-size: 46px; }
section.lead p { color: #eaf3fb; font-size: 26px; }
section.lead::after { content: ""; }
</style>

<!-- _class: lead -->

# Regime-Conditional Value-at-Risk on the DFL Brent

Modelling the basis risk of a physical crude desk

Julien — IFP School — June 2026

---

## The problem

A physical crude desk buys Dated-priced cargoes and hedges them with ICE Brent futures.

The leftover gap is the DFL — Dated Brent minus front-line ICE Brent. That gap is basis risk: a structural premium that cannot be fully arbitraged away.

It is real P&L every day, and its tail risk is what we set out to model.

---

## The challenge: the DFL is not normal

![h:380](assets/01_dfl_distribution.png)

Skewness +5.5, kurtosis +62 — extreme, asymmetric fat tails. No single distribution (Gaussian, Student-t, skew-normal) fits, so a flat parametric VaR badly understates the risk.

---

## Why: it is a mixture of regimes

![h:360](assets/02_dfl_timeline.png)

Calm for years, then violent — COVID 2020, Russia 2022, April 2026 (+$36). The extremes cluster, so the DFL behaves differently depending on the market state. The fix: condition the VaR on the regime.

---

## The approach

Data (12 years, 3 crude benchmarks + macro + inventories)

→ PCA — 5 interpretable factors (curve tightness, risk-off, East-West arb, momentum, trans-Atlantic)

→ K-means — 3 market regimes

→ XGBoost quantile regression — conditional VaR + conformal recalibration

→ Backtest vs 6 baselines, then an ensemble

→ Desk application, in dollars

---

## Regimes that mean something

![h:380](assets/03_regime_boxplot.png)

Three directional regimes — Contango (downside), Calm, Physical tightness (upside). Built without ever using the DFL, yet they split it sharply and asymmetrically: contango down to −$11, tightness up to +$36.

---

## The model

XGBoost quantile regression on the regime plus continuous market features, predicting the quantiles of the next-day DFL move (q01 / q05 / q95 / q99).

Temporal split: train 2014–2023, test 2024–2026, so the 2026 spike is a genuine out-of-sample stress test.

An upside calibration leak appeared (q95 breached 10.7% vs 5%). After ruling out three causes, it was fixed post-hoc with split-conformal recalibration.

---

## How the models are evaluated

Two axes, not one:

- Calibration — Kupiec (right number of breaches?) and Christoffersen (are breaches clustered?). The regulatory-grade pass/fail.
- Accuracy — pinball loss, the proper scoring rule that ranks the models.

All out-of-sample, against real baselines including Filtered Historical Simulation (the bank standard).

---

## Comparison: who wins

![h:360](assets/05_pinball_ranking.png)

Conditioning beats distribution: Student-t → regime cuts loss by 26%, while adding fat tails buys only 3%. No single model dominates, but the ensemble (XGBoost + FHS) wins and is the only one to pass every backtest.

---

## The final model

![h:360](assets/04_ensemble_bands.png)

Tight in calm, wide in the 2026 crisis — the risk number breathes. Best pinball loss, passes all twelve backtest checks, and fixes the clustered downside breaches that XGBoost alone failed.

---

## What it means for a desk

For a position long 1,000,000 bbl of DFL:

- 1-day 99% VaR ≈ $2.7M in calm markets, ballooning past $10M in April 2026.
- Expected Shortfall: when the 95% VaR breaks, the average loss is 2.25× the threshold.

The tail is worse than the VaR line suggests — which is exactly why Basel III / FRTB uses Expected Shortfall.

---

## VaR as a self-tightening position limit

![h:340](assets/06_position_sizing.png)

Run in reverse: a fixed risk budget sets the allowed position. For a $20M daily VaR budget, the desk can run ~12 Mbbl in calm and under 2 Mbbl in the crisis — a 6–7× cut, automatically, exactly when it matters.

---

## Limits, stated honestly

- The April 2026 move exceeds anything in training — VaR must be complemented by stress testing.
- The regimes are fit on the full sample (look-ahead); production would refit walk-forward.
- Part of the measured daily move is snap-time noise (Platts 16:30 vs ICE 19:30), not real risk.
- The statistically best VaR is not the most usable — FHS's crisis spikes are pro-cyclical.

---

## Takeaways

- An end-to-end regime-conditional VaR, calibrated and formally validated.
- Conditioning on the market state matters far more than the choice of distribution.
- The ensemble is the only fully-calibrated model — structure (XGBoost) plus volatility (FHS).
- Made tangible: dollar VaR, Expected Shortfall, and position sizing.
- And honest about where, and why, it reaches its limits.

---

<!-- _class: lead -->

# Thank you

Code and notebooks: github.com/juliens50/ML-project-VaR-Calculation-for-Basis-Risk

Questions?
