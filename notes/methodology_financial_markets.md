# Methodology — Bonds vs. Equities vs. the AI Cycle ("The Two Markets")

*Research thread added 2026-05-29. Scope: US Treasuries, the corporate-credit market,
the broad equity market, and the AI/hyperscaler complex inside both. Empirical question:
why do bond yields appear to "signal collapse" while equities — especially AI names —
stay buoyant? This note is the spine; `scripts/fetch_*` and `scripts/analyze_*` (listed
below) operationalize it, and `notes/provenance.md` logs each dataset.*

---

## 0. The reframe (read this first)

A non-specialist sees "bond yields up / curve doing scary things" and reads a recession
bell. But **two different bond-market signals get conflated**, and they mean opposite things:

| Signal | Mechanism | What it prices | Reading now (2026-05) |
|---|---|---|---|
| **Inverted curve** (short > long), high recession-prob, Sahm trigger, wide credit spreads | Market expects the Fed to *cut* because growth is failing | A **growth collapse** | **Benign** — 10y−3mo ≈ +0.76 (un-inverted), recession prob ≈ 1.8%, Sahm ≈ 0.13, IG OAS ≈ 0.74%, NFCI ≈ −0.51 (loose) |
| **Rising *long-end* yields + positive term premium** | Investors demand more to hold duration: fiscal supply, inflation/term risk, higher neutral rate (r*) | "**Too much borrowing / too much growth**," not collapse | **Elevated** — 10y term premium ≈ +0.83, positive again after turning deeply negative in 2016–2021 |

So part of the puzzle is a **category error**: a long-end sell-off (a *supply / term-premium*
story) is being heard as a recession bell (an *expectations* story). The classic recession
indicators are **not** lit.

The genuinely interesting residue, and what this thread investigates:
1. **Why is the long end heavy?** Term premium, fiscal supply, who the marginal buyer is.
2. **Is the equity calm real or a concentration illusion?** A handful of AI megacaps can
   make a cap-weighted index look healthy while the median stock is not.
3. **How does the debt-financed AI buildout sit inside both?** Hyperscalers are pivoting
   from cash-funded to bond-funded capex; that issuance is exactly where the equity story
   and the bond/credit story meet — and it ties to this project's thesis that the AI cycle
   is a fiscally/geopolitically backstopped bet.

**Decomposition is the method.** Never read a yield level directly; split it into its
economically-distinct components and ask which component is moving.

---

## 1. Data to acquire

All FRED series verified live 2026-05. FRED via `requests` in scripts (key from
`os.environ`), mirroring `fetch_macro_investment.py`; `mcp__fred__FREDSeries` for ad-hoc
checks only.

### A. Treasury curve & its decomposition — `fetch_treasury_curve.py` → `treasury_curve.csv`
- Nominal curve: `DGS3MO`, `DGS2`, `DGS5`, `DGS10`, `DGS30`
- Recession-signal spreads: `T10Y2Y`, `T10Y3M`
- Real (TIPS) yields: `DFII5`, `DFII10`
- Inflation compensation: `T5YIE`, `T10YIE`, `T5YIFR` (5y5y forward)
- **Term premium: `THREEFYTP10`** (ACM 10y) — *model-estimated, flag it*
- Policy anchor: `DFEDTARU`, `EFFR`

### B. Corporate credit — `fetch_credit_spreads.py` → `credit_spreads.csv`
- `BAMLH0A0HYM2` (HY OAS), `BAMLC0A0CM` (IG OAS), `BAMLH0A3HYC` (CCC OAS)
- `BAA10Y`, `AAA10Y` (Moody's vs 10y)
- `DRTSCILM` (SLOOS — net % of banks tightening C&I standards, quarterly)

### C. Stress / financial conditions / real economy — `fetch_market_stress.py` → `market_stress.csv`
- `VIXCLS` (equity vol), `NFCI`, `STLFSI4` (conditions/stress indices)
- `RECPROUSM156N` (12-mo recession prob), `SAHMREALTIME`, `USREC` (NBER dates)
- Reality check: `UNRATE`, `PAYEMS`, `ICSA`, `GDPC1`
- *Gap:* ICE **MOVE** (bond vol) is paywalled / not on FRED → substitute realized vol from
  `DGS10` daily changes; flag the substitution.

### D. Equity breadth, concentration, valuation — `fetch_equity_market.py` → `equity_market.csv`
- yfinance: `SPY` vs `RSP` (cap- vs equal-weight), `QQQ`, `SMH`/`SOXX`; Mag-7 names
- FRED `SP500`, `NASDAQCOM` for long daily history
- Valuation/ERP input: Shiller CAPE (Shiller online dataset) → earnings yield = 1/CAPE
  *(Tier-2 secondary; forward P/E is paywalled)*

### E. The AI-thesis bridge — `fetch_hyperscaler_debt.py` → `hyperscaler_debt.csv`
SEC EDGAR `companyconcept` (template = `fetch_hyperscaler_capex.py`), same 7 tickers:
- `LongTermDebtNoncurrent`, `ProceedsFromIssuanceOfLongTermDebt`, `InterestExpense`,
  `NetCashProvidedByUsedInOperatingActivities`
- Purpose: size the **debt-financed share of the buildout** — the hinge between equities and bonds.

---

## 2. How to analyze it

| Script | Output | What it does |
|---|---|---|
| `analyze_curve_decomposition.py` | `curve_decomposition.csv` + figs | Split nominal 10y two ways — (a) real + breakeven, (b) expectations + term premium — and chart the term-premium regime shift. **The figure that resolves the confusion.** |
| `analyze_recession_signals.py` | `recession_signals.csv` + fig | Event study: each `T10Y2Y`/`T10Y3M` inversion vs `USREC`, lead times, this cycle's no-recession un-inversion. Current-reading dashboard shows collapse signals are *not* lit. |
| `analyze_credit_equity_coherence.py` | `cross_asset.csv` | Percentile-rank HY/IG spreads, VIX, NFCI vs full history; test whether credit and equity "agree." Tight spreads + low vol = no distress *priced* → the long-end move is supply/term, not credit. |
| `analyze_equity_concentration.py` | `equity_concentration.csv` + figs | Cap- vs equal-weight divergence, Mag-7 share of cap & return, and **ERP = S&P earnings yield − 10y real yield**; a near-zero/negative ERP quantifies "irrational." |
| `analyze_ai_financing_linkage.py` | `ai_financing.csv` + fig | Debt-issuance trend, capex-vs-operating-cash-flow coverage, debt-funded share of capex → issuance → Treasury/credit supply → term-premium pressure. Closes the loop to the project thesis. |

**General analytic moves:**
- *Decompose before interpreting* (yields into components; index returns into constituents).
- *Percentile-rank against history* rather than eyeballing levels — "is this actually extreme?"
- *Cross-asset coherence* — do rates, credit, vol, and equities tell the same story? Divergence is the signal.
- *Real vs nominal, expectations vs term premium, cap- vs equal-weight* — always hold the distinction.

---

## 3. The interesting economics questions

1. **Recession bell or fiscal bell?** Is the long end pricing a growth collapse (expectations)
   or fiscal supply + higher r* (term premium)? Decompose; don't assume.
2. **Did the yield curve cry wolf?** Why did the deepest inversion since the 1980s not produce
   a recession — broken indicator, or "long and variable lags" not yet expired? Is *bull vs
   bear* steepening the more telling signal?
3. **Who is the marginal Treasury buyer** now that the Fed (QT) and foreign officials have
   pulled back — and is that supply/demand shift the term-premium story?
4. **Is the equity calm real or compositional?** Equal-weight vs cap-weight — is there a
   stealth bear market under a few AI megacaps?
5. **Is the equity risk premium near zero/negative?** Are investors paid anything to hold
   stocks over bonds — and does that *quantify* the "irrationality"?
6. **Rolling vs aggregate recession:** is an equity/retained-earnings-funded AI boom offsetting
   contraction in rate-sensitive sectors (housing, CRE, small business), so the aggregate
   looks fine while the composition is stressed?
7. **Fiscal dominance / the backstop bill:** are high long yields the cost of the
   geopolitically-backstopped buildout showing up as deficits + Treasury supply?
8. **Debt-financed buildout → credit/rates transmission:** as hyperscalers shift from cash to
   bond financing, does AI capex begin to *move* credit spreads and the term premium?

---

## 4. What the data cannot settle

- **Term premium is model-estimated** (`THREEFYTP10` = Adrian–Crump–Moench); Kim–Wright and
  others differ — report the level *and* the model dependence.
- **Curve → recession is small-N and correlational** (~7 post-war recessions); the event study
  is suggestive, not predictive.
- **Concentration/ERP rely on constructed or secondary inputs** (yfinance proxies; Shiller CAPE
  for trailing earnings; forward P/E paywalled) — Tier-2.
- **Bond vol (MOVE) unavailable** — realized-vol substitute is a proxy, not the index.
- **Financing → term-premium causation is a thesis, not a measurement** — same honesty as the
  report's energy-price-causation handling.

---

## 5. Build order

1. This note.
2. `fetch_treasury_curve.py` + `fetch_credit_spreads.py` + `fetch_market_stress.py` (FRED, fastest).
3. `analyze_curve_decomposition.py` + `analyze_recession_signals.py` (deliver the core reframe early).
4. `fetch_equity_market.py` + `analyze_equity_concentration.py` (the equity-illusion question).
5. `fetch_hyperscaler_debt.py` + `analyze_ai_financing_linkage.py` (the AI-thesis link).
6. `analyze_credit_equity_coherence.py`, synthesis note, optional report section.
