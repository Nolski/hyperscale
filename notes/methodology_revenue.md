# Methodology — Can the revenue pay the buildout back?

*Research thread added 2026-05-30. The demand/profitability counterpart to the capex and
hardware threads: can AI revenue grow fast enough, long enough, at enough margin to earn back
the buildout at its cost of capital? Operationalized by `scripts/model_revenue_payback.py`
(deterministic, scenario) and `scripts/model_payback_montecarlo.py` (probabilistic). Feeds the
report's "Ten-X Problem" section. Bibliography additions in
`notes/bibliography_hardware_economics.md`.*

## The question, made precise

Set the **required** revenue (to earn the cost of capital on the capital deployed) against the
**achievable** revenue (an adoption S-curve grounded in observed usage), and price the gap.

## Required side

- **WACC (real inputs):** Rf = latest 10y Treasury (`treasury_curve.csv`, ~4.5%); after-tax cost
  of debt = (Rf + IG OAS from `credit_spreads.csv`)·(1−21%); cost of equity = Rf + β·ERP (CAPM,
  β=1.3, ERP=5%); ~85/15 equity/debt (low hyperscaler leverage) → **WACC ≈ 10%**.
- **Capital deployed K:** cumulative ~2024–2030 buildout capex = actuals (`hyperscaler_capex_annual.csv`,
  2024–25) + `investment_projection.csv` (2026–30) → **low $3.5T / mid $5.3T / high $7.4T**.
- **Capital-recovery:** to return WACC and recover K over asset life L, the buildout must throw
  off annual operating profit = K·CRF(WACC, L), where CRF = r(1+r)^L/((1+r)^L−1). **Required
  revenue = that profit ÷ operating margin**, at margins {15%, 25%, **35% (AWS-proven)**} and
  **L ∈ {3, 6}** (our economic-vs-book-life range). Result: **~$3.5–6.1T/yr** at 35% margin,
  more at thinner margins/shorter life.

## Achievable side

- Base 2026 AI revenue R0 ≈ **$80B** = AI-native ARR (OpenAI ~$25B + Anthropic ~$30B,
  `ai_native_revenue.csv`) + hyperscaler AI services (~$25B).
- Grow on a **decelerating S-curve** calibrated to observed token-volume growth (Google ~7×/yr,
  decelerating — `token_volume.csv`) net of the steep effective-price decline. Low/mid/high →
  **$0.29T / $0.73T / $1.44T by 2030**.

## The gap, the comparable, the probability

- **Gap:** required ~$3.5T+/yr vs achievable ~$0.7–1.4T by 2030. The implied required revenue
  CAGR (~156%/yr) is ~**4× AWS's** ~36%/yr over its 13-year ramp, at far larger scale — the
  steepest real precedent for a compute-infrastructure business (`cloud_segments.csv`).
- **Monte Carlo (50k draws, seed 42):** a multi-year DCF (PV of after-tax AI operating profit −
  capital, with a terminal value) over the swing assumptions (K, 2030 revenue, margin, WACC,
  post-2030 growth). The buildout clears its cost of capital in **~7% of paths** if repaid by
  **AI-specific** revenue — or **~48%** under **broad attribution** (crediting AI with lifting
  all cloud/ads/search revenue). The answer hinges on attribution; even the generous view is a
  coin flip. Dominant swing factor: the 2030 revenue level.

## The profitability reality check

The margin ceiling is real and primary: AWS earns **~35%**, Microsoft Intelligent Cloud **~42%**,
Google Cloud **~24%** operating margins at scale (`cloud_segments.csv`, SEC 10-Ks). But AI-native
revenue today is **unprofitable** (reporting: OpenAI ~ −$1.35 per $1). Achievable revenue is real;
*profitable* revenue at mature-cloud margins is the assumption the bet rests on.

## What this cannot settle

- Achievable revenue is **scenario, not forecast**; token-volume and ARR figures are company
  disclosures/press (Tier-2); the cloud-segment margins/AWS ramp are the SEC primary anchor.
- The softest assumption is **attribution** — pairing the full buildout capital with AI-specific
  vs broad cloud revenue swings the probability from ~7% to ~48%. We report both rather than pick.
- WACC/β/ERP and the achievable multipliers are stated assumptions; Monte-Carlo probabilities are
  **conditional on the input ranges** — plausibility, not a market call.
