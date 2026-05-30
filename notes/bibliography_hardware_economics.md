# Bibliography & framing — AI hardware economics (energy, efficiency, depreciation)

*Compiled 2026-05-29. Companion to `notes/methodology_hardware_economics.md`. Records the
model lineage the anchor models build on, and the framing literature for the economic-
obsolescence / energy / China threads.*

**Citation discipline (per CLAUDE.md):** framing/method sources, not the data of record.
Empirical claims rest on `data/processed/`. `[verify]` = recent, fast-moving, secondary, or
reconstructed from memory — confirm bibliographic details and figures before publication.

---

## 1. Vintage capital & embodied technical change (the "old machines get scrapped" frame)

- **Robert M. Solow (1960)**, "Investment and Technical Progress," in *Mathematical Methods
  in the Social Sciences* (Stanford UP). The founding **vintage-capital** model: new capital
  embodies better technology, so older vintages become obsolete and are scrapped — exactly
  the GPU-generation succession we model. **Application:** `L*` is the scrapping date.
- **Leif Johansen (1959)**, "Substitution versus Fixed Production Coefficients in the Theory
  of Economic Growth," *Econometrica*. Putty-clay vintage capital. [verify ed.]
- **W. E. Diewert / Dale Jorgenson** — capital measurement and the user cost of capital; the
  rental price that should equate to marginal product. Frames "what a GPU-hour should cost."

## 2. Economic vs accounting depreciation (the earnings-quality core)

- **Charles R. Hulten & Frank C. Wykoff (1981)**, "The Measurement of Economic
  Depreciation," in *Depreciation, Inflation, and the Taxation of Income from Capital*
  (Urban Institute). The canonical treatment of how an asset's **economic** value decays vs
  its **book** schedule — the precise gap Thread 1 estimates for AI hardware.
- **BEA fixed-asset methodology** — service lives and depreciation profiles used in national
  accounts; a benchmark for "what life is reasonable." [verify specifics]

## 3. Cost-decline & efficiency curves (the efficiency trend)

- **Theodore Wright (1936)** / **Boston Consulting Group (1968)** — the experience/learning
  curve: unit cost falls a constant % per doubling of cumulative output. Applied to $/FLOP
  and $/token. **Application:** the new-chip capex trajectory in the retirement inequality.
- **Jonathan Koomey et al. (2011)**, "Implications of Historical Trends in the Electrical
  Efficiency of Computing," *IEEE Annals of the History of Computing* — **Koomey's law**:
  computations per kWh roughly doubled every ~1.6 yrs historically (slowing since). The
  empirical backbone of the perf/watt assumption.
- **Epoch AI** (epochai.org) — ML-hardware database (FLOP/s, TDP, perf/watt over time),
  notable-models compute/cost, and algorithmic-efficiency trends. The best machine-readable
  source for the efficiency march; `fetch_epoch_hardware.py` targets it. [verify dataset/endpoint]

## 4. Total cost of ownership & cost-per-token (the unit-economics method)

- **SemiAnalysis** (Dylan Patel et al.) — the de facto industry methodology for GPU/cluster
  **TCO** and **cost-per-token**, and for cluster power/networking accounting. Mostly
  paywalled — use for method/benchmarks, not as data of record. [verify]
- **Cloud GPU rental markets** (H100/A100 $/hr histories; CoreWeave, Lambda, hyperscaler
  list prices) — a market read on the *decaying economic value* of a vintage; staged in
  `gpu_rental_rates.csv`. [verify]
- **MLPerf (MLCommons)** — Inference & Training benchmark suites: realized throughput and
  perf/watt per accelerator (replaces peak-FLOP in Thread 4). [verify]

## 5. Energy rebound (Thread 3)

- **William Stanley Jevons (1865)**, *The Coal Question* — efficiency gains can *raise* total
  consumption (the **Jevons paradox**). The central tension in "more efficient chips → less
  energy?"
- Modern **energy-rebound** literature (direct + economy-wide rebound) — for the elasticity
  framing. [verify specific surveys, e.g. Gillingham et al.]
- **LBNL (2024)**, *US Data Center Energy Usage Report* — the demand anchor
  (`datacenter_energy.csv`); the benchmark the rebound projection is tested against.

## 6. China vs US hardware & geopolitics (Thread 5 — all `[verify]`)

- **CSET, Georgetown** (Center for Security and Emerging Technology) — analyses of Chinese AI
  chips, SMIC process nodes, and export-control effects.
- **CSIS** — semiconductor supply-chain & export-control policy analysis.
- **SemiAnalysis** — Huawei **Ascend 910B/910C** specs and **CloudMatrix 384** system
  benchmarks vs Nvidia GB200 NVL72 (the "scale-out, higher-power" comparison). [verify]
- **US BIS (Bureau of Industry and Security)** — the export-control rules (advanced-computing
  / FDPR) that shape the divergence. Primary regulatory source.
- **Epoch AI** — compute capacity and notable models by country.
- Framing claim to verify: Chinese designs trade **perf/watt for compute availability**,
  economic given cheaper/more-abundant Chinese electricity — implying a more energy-intensive
  Chinese compute base. Confirm against CloudMatrix power-draw figures before quoting.

---

## 7. Revenue / payback modelling (the "can it pay back?" thread)

- **Cost of capital / WACC & capital recovery:** standard corporate-finance apparatus —
  CAPM (Sharpe 1964), the weighted-average cost of capital, and the capital-recovery factor
  (annuity that returns r and recovers principal over life L). Used to set the *required*
  revenue bar. Inputs from FRED (Treasury, OAS).
- **Adoption / diffusion:** the logistic / **Bass diffusion** model (Bass 1969) and S-curve
  technology adoption — the shape of the *achievable* revenue path; calibrated to observed
  token-volume growth.
- **Learning / experience curves:** Wright's law again, here on the *price* side (token-price
  decline) feeding effective revenue-per-token.
- **The AWS comparable:** Amazon segment disclosures (SEC) — AWS's ~13-year ramp to ~$130B at
  ~36%/yr as the steepest real precedent for a compute-infrastructure revenue ramp; the mature
  cloud operating margins (AWS ~35%, MSFT IC ~42%, GCP ~24%) as the profitability ceiling. Primary.
- **Revenue/usage figures** (OpenAI/Anthropic ARR, Google token volume) are press/keynote
  Tier-2 `[verify]`; the cloud-segment revenue/margins are SEC primary.

## Status legend
- **[verify]** = confirm details/figures against the primary source before publication.
- Unflagged entries are established works with stable citations; still check edition/pages.
