# Data provenance log

One entry per dataset. Record source, exact endpoint, retrieval date, data
vintage, and methodology caveats. Newest entries at the top.

---

## Revenue / payback datasets — "can the revenue pay it back?" thread

- **Methodology:** `notes/methodology_revenue.md`. **Scripts:** `fetch_cloud_revenue.py`,
  `model_revenue_payback.py`, `model_payback_montecarlo.py`. Retrieved 2026-05-30.
- **cloud_segments.csv** — cloud-segment revenue + operating income. **PRIMARY** rows
  (`verified=true`): AWS FY2025 ($128.7B rev / $45.6B OI / 35%), Google Cloud FY2025 ($58.7B /
  $13.9B / 24%), Microsoft Intelligent Cloud FY2025 ($106.3B / $44.6B / 42%) — captured from SEC
  EDGAR 10-Ks via the `get_segment_data` MCP (Amazon accession 0001018724-26-000004; GOOGL/MSFT
  FY2025 10-Ks). The AWS 2013–2024 ramp is hand-keyed from Amazon's published segment figures
  (Tier-2). Anchors the mature-cloud margin ceiling and the AWS revenue-ramp comparable.
- **ai_native_revenue.csv** (Tier-2, press): OpenAI ~$25B and Anthropic ~$30B annualized
  run-rate, with trajectories; flagged that AI-native revenue is currently unprofitable.
- **token_volume.csv** (Tier-2, keynotes): Google tokens/month 9.7T (2024) → 480T (2025) → 3.2
  quadrillion (2026); calibrates the adoption S-curve.
- **revenue_payback.csv / payback_montecarlo.csv** (model outputs): WACC ≈ 10%; capital deployed
  ~$3.5–7.4T; required revenue ~$3.5–6.1T/yr (35% margin) vs achievable ~$0.7–1.4T by 2030;
  required ramp ~4× AWS's pace; probability the buildout clears its cost of capital ≈ **7%
  (AI-specific revenue)** / **48% (broad attribution)**. Achievable revenue is scenario;
  attribution is the dominant assumption; probabilities are conditional on the input ranges.

---

## 2026 news/framing datasets — report reframe ("The Build and the Bill")

- **Files:** `data/raw/manual/ai_capex_revenue_2026.csv`, `data/raw/manual/ai_adoption_signals.csv`.
- **Used by:** `build_report.py` (the reframed long-read), retrieved 2026-05-30.
- **TIER-2 FRAMING, not data of record.** Journalism + analyst estimates gathered via web
  search; every row is `verified=false` and carries a `source` + `url`. These are cited inline
  in the report and listed in its Sources block; the primary-source pipeline (SEC/FRED/EIA/BLS)
  remains the spine. Figures move quarter to quarter — confirm against the linked source before
  re-quoting.
- **ai_capex_revenue_2026.csv:** Big-Five 2026 capex guidance (~$635–725B combined, ~2× 2024;
  Amazon ~$200B, Alphabet ~$180B, Meta ~$135B, Microsoft ~$120B+), AI-service revenue ~$25B
  (2025), capex ~45–57% of revenue, projected FCF drop, OpenAI ~$1.4T commitments vs ~$13B
  revenue. Sources: Futurum, MUFG, NPR, HeyGoTrade (URLs in file).
- **ai_adoption_signals.csv:** MIT NANDA 95% of GenAI pilots no P&L return (~$30–40B spend);
  Robert Half 29% rehired after AI layoffs; Forrester 55% regret; ~$800B circular financing;
  ~50% of 2026 US data centers delayed (power-constrained); Microsoft ~$80B unfulfilled Azure
  orders; Burry ~2.5yr GPU useful-life claim. Sources: Fortune, Washington Times, BlockEden,
  Tech-Insider, Global Data Center Hub, Quasa (URLs in file).

---

## Hardware-economics datasets — energy / efficiency / depreciation thread

- **Methodology:** `notes/methodology_hardware_economics.md`; bibliography
  `notes/bibliography_hardware_economics.md`.
- **Scripts:** `fetch_gpu_specs.py`, `fetch_epoch_hardware.py`, `model_gpu_tco.py`,
  `model_economic_obsolescence.py`. Retrieved 2026-05-29.

### gpu_specs.csv (manual, Tier-2)
- Hand-keyed AI-accelerator specs (`data/raw/manual/gpu_specs.csv`): NVIDIA V100→GB200,
  AMD MI300X, Huawei Ascend 910B/910C. FLOPS are **dense** (not the headline sparse
  numbers); `flops_dense_bf16` and `flops_dense_fp8` stored separately (Volta = FP16).
  Prices are approximate street/list. **Huawei rows are ESTIMATES** (`verified=false`),
  used for the China-vs-US thread. `country` column tags US vs China.

### pue_assumptions.csv (manual, Tier-2)
- PUE, system-overhead (GPU≈60-70% of server power → ~1.5×), utilization, hours/yr by
  scenario (hyperscaler ~1.12 / industry ~1.5 / off-grid). Sources: hyperscaler
  sustainability reports, Uptime Institute. The models use `hyperscaler_modern`.

### epoch_hardware.csv (Epoch AI, live download)
- `https://epoch.ai/data/ml_hardware.csv` (CC-BY; no key), ≈300 accelerators, 62 with both
  BF16 perf and TDP retained. Used as external corroboration of gpu_specs.csv and the
  perf/watt frontier. **Caveat:** Epoch's BF16 figure may follow a different sparsity
  convention than our DENSE gpu_specs (e.g. Epoch H100 PCIe ≈2.16 TF/W vs our dense H100 SXM
  ≈1.41) — trends agree; absolute levels differ by convention. Manual fallback supported.

### gpu_tco.csv / economic_obsolescence.csv (model outputs)
- TCO and economic-obsolescence model outputs (in `output/`). Key honest finding: at US
  industrial power (~8.6¢/kWh, EIA, via `us_electricity.csv`), energy is ~10-17% of GPU TCO,
  so **energy COST alone strands only old silicon** (V100 stranding price ≈13.5¢, A100 ≈32¢,
  H100 ≈$1.00/kWh). The real refresh driver is power-CAPACITY opportunity cost (compute/MW).
  The earnings-overstatement figure is a **conditional, illustrative** back-of-envelope.
  Price scenarios (+20/+50%) anchor on Dallas Fed WP2606 via `electricity_price_outlook.csv`.

### token_prices.csv / gpu_rental_rates.csv (manual, Tier-2 — STAGED, not yet analyzed)
- Hand-keyed anchors for Thread 4 (token NPV): frontier-LLM $/Mtok over time and cloud
  GPU $/hour over time. All `verified=false` — list prices change frequently; CONFIRM against
  provider pages. Document the ~order-of-magnitude $/token decline and the H100 rent collapse
  (~$8→$2/hr) as the revenue-side pressure on hardware value.

### endogenous_price.csv (model output — demand→price feedback)
- `model_endogenous_price.py`. Makes industrial electricity price a function of data-center
  demand (LBNL path from `datacenter_energy.csv`), pinned to Dallas Fed WP2606 (+20%/+50% by
  2028, `electricity_price_outlook.csv`) with an **IER null** (no causal link). Feeds the
  price path into the per-vintage stranding thresholds. Finding: even the high path only
  nears stranding V100 (~2029) and never modern chips. **Causation is CONTESTED** (Dallas Fed
  vs IER, both carried); price path is scenario-anchored, not a structural grid model.

### chip_margins.csv (SEC EDGAR)
- `fetch_chip_margins.py`: GrossProfit / Revenue (10-K) for NVDA, AMD. Latest: NVIDIA ~71%
  blended gross margin (FY2026, $216B rev), AMD ~50%. The vendor-markup slice of the cost stack.

### cost_stack.csv (manual BOM + model output)
- `data/raw/manual/cost_stack.csv` (Tier-2 analyst BOM ESTIMATES, `verified=false`: die / HBM /
  packaging / other) + `model_cost_stack.py`. Decomposes full deployed cost: manufacturing |
  vendor margin | facility+cooling capex (@ ~$9M/MW, flagged range) | lifetime energy. Finding
  (H100): margin ~60%, facility+cooling ~24%, energy ~8%, manufacturing ~8% (HBM ~41% of COGS).
  Explains the "energy looks small" artifact — the MSRP is mostly margin. Facility $/MW and BOM
  are wide-range assumptions; proportions, not precision.

### token_economics.csv (model output — Thread 4)
- `model_token_economics.py`. Converts GPU compute to tokens/sec via the standard inference
  rule (~2·N_active_params FLOPs/token) with **explicit flagged assumptions** (N≈100B active,
  MFU 0.30, util 80%, discount 12%, 5y life); decode is often memory-bound so this is a
  compute-bound proxy (MLPerf would refine). Cost/Mtok by vintage (H100 ≈$0.24) vs the API
  OUTPUT price path (frontier flagship tier from `token_prices.csv`: ~$15/Mtok now, ~69%/yr
  decline — flagship line GPT-4→4-Turbo→4o, EXCLUDING the "mini" tier). Finding: at list prices
  + high utilisation, inference hardware pays back in ~year 1 (break-even flat price ~$0.32/Mtok,
  ~50× below list) — so GPU unit economics aren't the risk; training capex, the price war, and
  utilisation are. **Best-case monetisation** (all output tokens at list, high util) — upper bound.

### jevons_rebound.csv (model output — Thread 3)
- `model_jevons_rebound.py`. Decomposes DC energy growth via the identity E = C·e: frontier
  perf/watt improving ~23%/yr (gpu_specs.csv), LBNL energy 176→325-580 TWh (datacenter_energy.csv),
  so implied compute growth ~40-57%/yr — about 2× the efficiency rate. **Jevons result:** demand
  outruns efficiency, total energy rises. Counterfactual (LBNL high): efficiency 'saved' ~1,084 TWh
  (580 actual vs 1,664 frozen-efficiency), but energy still tripled from the 176 base. Caveats:
  FLEET efficiency lags the FRONTIER (rebound even stronger); compute growth is INFERRED from the
  identity (Epoch corroborates magnitude); the Jevons causal claim is interpretation; LBNL is a
  scenario range.

---

## Financial-markets datasets — "Two Markets" thread (bonds vs. equities vs. AI)

- **Methodology note:** `notes/methodology_financial_markets.md`.
- **Files:** `data/processed/{treasury_curve, credit_spreads, market_stress,
  equity_prices, equity_market_caps, shiller_cape, hyperscaler_debt}.csv`.
- **Scripts:** `fetch_{treasury_curve, credit_spreads, market_stress, equity_market,
  hyperscaler_debt}.py`; `analyze_{curve_decomposition, recession_signals,
  equity_concentration, ai_financing_linkage, credit_equity_coherence}.py`.
  Retrieved 2026-05-29.

### treasury_curve.csv (FRED REST, https://api.stlouisfed.org/fred/)
- Series: DGS3MO/2/5/10/30 (nominal CMT), T10Y2Y, T10Y3M (spreads), DFII5/DFII10
  (TIPS real), T5YIE/T10YIE/T5YIFR (breakevens), **THREEFYTP10** (ACM 10y term
  premium), DFEDTARU/EFFR (policy). Daily except policy.
- **THREEFYTP10 is a MODEL ESTIMATE** (Adrian–Crump–Moench), not an observed price;
  Kim–Wright and other models give different levels. Report level *and* model
  dependence. Sanity check: nominal_10y − real_10y − breakeven_10y ≈ 0 (it does).

### credit_spreads.csv (FRED REST)
- ICE BofA OAS: BAMLH0A0HYM2 (HY), BAMLC0A0CM (IG), BAMLH0A3HYC (CCC); Moody's
  BAA10Y/AAA10Y; DRTSCILM (SLOOS net % tightening C&I, quarterly survey).
- ICE OAS series begin ~2023 in this pull's vintage window (n≈785); Moody's spreads
  run to the 1980s. Percentile comparisons in analyze_* use each series' own history.

### market_stress.csv (FRED REST)
- VIXCLS, NFCI, STLFSI4, RECPROUSM156N (12-mo recession prob), SAHMREALTIME, USREC
  (NBER dates), UNRATE, PAYEMS, ICSA, GDPC1.
- **MOVE gap:** ICE BofA MOVE (Treasury implied vol) is paywalled / not on FRED.
  analyze_credit_equity_coherence.py substitutes REALIZED 10y vol (21-day annualized
  std of DGS10 daily changes) — a proxy, not the index. Flagged in-figure.

### equity_prices.csv, equity_market_caps.csv (Yahoo Finance via `yfinance`, Tier-2)
- Daily adjusted closes (auto_adjust) for SPY, RSP, QQQ, SMH and the Mag-7 (AAPL,
  MSFT, GOOGL, AMZN, NVDA, META, TSLA) from 2003; current marketCap per Mag-7 name.
- Yahoo is convenience/secondary-grade — fine for index-RELATIVE analysis (SPY vs
  RSP divergence), not a statistical-agency source. Mag-7 share of S&P 500 by index
  weight (~35%) is an EXTERNAL flagged reference in analyze_equity_concentration.py
  (float weights are not computed from this data).

### shiller_cape.csv (MANUAL, Tier-2 / approximate)
- Hand-keyed APPROXIMATE year-end CAPE (CAPE-10) from Robert Shiller's online dataset
  (econ.yale.edu/~shiller/data.htm), plus a current reading. 1/CAPE is a REAL
  cyclically-adjusted earnings yield, compared against the TIPS real 10y to get the
  equity risk premium. Treat the REGIME (high-30s, near dot-com extremes) as the
  finding, not the second digit. Refresh from Shiller's file.

### hyperscaler_debt.csv (SEC EDGAR XBRL companyconcept, no key; User-Agent set)
- Same 7 firms as hyperscaler_capex_annual.csv. Concepts: LongTermDebtNoncurrent
  (instant), ProceedsFromIssuanceOfLongTermDebt (duration), InterestExpense,
  NetCashProvidedByUsedInOperatingActivities. Candidate tags tried in order.
- **Oracle override:** Oracle does not file LongTermDebtNoncurrent; debt stock taken
  from DebtInstrumentCarryingAmount (verified $92.9B at FY2025-05-31).
- **Issuance is GROSS** proceeds (not net of repayment). MSFT/GOOGL/NVDA report no
  issuance tag in recent FYs — shown as MISSING, not zero (they are net repayers /
  cash-funded). Coverage = operating cash flow ÷ capex.

### hyperscaler_depreciation.csv + server_useful_life_changes.csv (depreciation / useful-life test)
- **Scripts:** `fetch_hyperscaler_depreciation.py`, `analyze_hyperscaler_depreciation.py`.
  Bibliography context in `notes/bibliography_financial_markets.md` (Burry/Chanos).
- **hyperscaler_depreciation.csv** — SEC EDGAR XBRL companyconcept: depreciation/D&A
  (duration), PropertyPlantAndEquipmentGross/Net (instant). **Tag heterogeneity:**
  MSFT/GOOGL/ORCL report `Depreciation` (clean); AMZN/META/NVDA/CRWV report
  `DepreciationDepletionAndAmortization` (includes intangible amortization) — so the
  implied-life proxy is NOT comparable across firms. **Coverage gaps:** Meta stops
  reporting gross PP&E after FY2018; Alphabet after FY2024 — implied life is computable
  only for MSFT/AMZN/ORCL, and even then is confounded by capex growth. The implied-life
  number is SUGGESTIVE ONLY; the depreciation-expense fingerprint and the disclosures
  are the evidence.
- **server_useful_life_changes.csv (manual, Tier-2 — NOT yet text-verified):** documented
  server/network useful-life changes from 10-K accounting-policy notes (MSFT 3→4→6y,
  GOOGL 3→4→6y, AMZN 4→5y then a 6→5y *shortening* in 2024, META 4→5y) with disclosed
  income impacts (~$3.7B MSFT FY23, ~$3.4B GOOGL 2023). The SEC EDGAR MCP exposes only
  business/risk-factor sections, not the PP&E footnote, so dollar figures and exact year
  boundaries must be CONFIRMED against the cited filings (e.g. MSFT FY2023 10-K accession
  0000950170-23-035122). The `verified` column is false until checked.

---

## State-level energy datasets — Q3a deepened energy section

- **Files:** `data/processed/us_electricity_by_state.csv`,
  `data/processed/energy_states_summary.csv`; manual sources
  `data/raw/manual/datacenter_energy_states.csv`,
  `data/raw/manual/electricity_price_outlook.csv`,
  `data/raw/manual/datacenter_power_deals.csv`.
- **Scripts:** `fetch_electricity_states.py`, `analyze_energy_states.py`.
  Retrieved 2026-05-15.

### us_electricity_by_state.csv
- **Source:** EIA API v2 `electricity/retail-sales`, `stateid` facet — 50
  states + DC, sectors all + residential, annual 2001-2025. Same EIA key as the
  national pull; the raw JSON has the echoed `api_key` redacted.
- State all-sector sales sum to 100% of the EIA US total (sanity check passes).

### datacenter_energy_states.csv (manual, Tier 3)
- Hand-keyed **approximate** data-center electricity by state (VA ~32 TWh ≈ 25%
  of the state's load; TX ~17; IL ~12; CA ~11; OR ~7), from LBNL/EPRI/secondary
  reporting. No clean machine-readable state breakdown exists — treat the
  *concentration* as the finding, not the second digit.

### electricity_price_outlook.csv (manual, Tier 3)
- Modelled price projections and the **contested** causal finding: Dallas Fed
  WP2606 (wholesale +3-5% now, ~20-50% by 2028; PCE inflation +0.05 → 0.13-0.26pp),
  EIA AEO 2026, PJM capacity-auction prices, and the Institute for Energy Research
  counter-analysis (no significant data-center/price link). Both sides recorded.

### datacenter_power_deals.csv (manual, Tier 3)
- Hyperscaler power procurement / grid participation — Meta-Constellation
  1,121 MW, Amazon-Talen 1,920 MW, Google-NextEra 615 MW, demand response,
  off-grid builds. Data centers are not net power sellers as of 2026.

### Key result (analyze_energy_states.py)
2020-2025: data-center-heavy states' electricity consumption +13% (Virginia +23%)
vs +8% elsewhere; residential price +38% vs +28%, diverging after 2021. Whether
data centers *cause* the price gap stays contested (Dallas Fed vs. IER).

---

## construction_sector.csv — Q3d construction-sector denominators

- **File:** `data/processed/construction_sector.csv`
- **Raw:** `data/raw/fred_TTLCONS_2026-05-15.json`, `data/raw/fred_USCONS_2026-05-15.json`
- **Script:** `scripts/fetch_construction_sector.py`. Analysis: `analyze_linked_sectors.py`.
- **Source:** FRED API — `TTLCONS` (Total Construction Spending, $M SAAR, monthly)
  and `USCONS` (All Employees: Construction, thousands SA, monthly; mirrors BLS
  CES). Key: `FRED_API_KEY`. Retrieved 2026-05-15.
- **Caveat:** `TTLCONS` is monthly SAAR — the analysis takes the mean of a year's
  12 months as that year's annual total, and uses only complete years.

### Key result
Data-center construction rose from 0.28% of all US construction spending (2015)
to 1.32% (2025). AI-chip suppliers (5 US firms) ≈ $405B revenue, NVIDIA 53%.

---

## oews / automation_exposure / anthropic_exposure — Q3c labor exposure

- **Files:** `data/processed/oews_occupations.csv`,
  `data/processed/automation_exposure.csv`, `data/processed/anthropic_exposure.csv`
- **Scripts:** `fetch_oews.py`, `fetch_automation_exposure.py`,
  `fetch_anthropic_economic_index.py`. Analysis: `analyze_automation_exposure.py`.
- **Retrieved:** 2026-05-15.

### oews_occupations.csv
- **Source:** BLS Occupational Employment and Wage Statistics (OEWS), national
  file `oesm24nat.zip` — May 2024 estimates. `bls.gov/oes/`. No key; BLS needs a
  descriptive User-Agent. 831 detailed occupations, 154.2M jobs (100% of US empl.).
- 22 occupations lack a published median wage (BLS suppression / top-coding).

### automation_exposure.csv
- **Source:** Eloundou, Manning, Mishkin & Rock, *GPTs are GPTs* (Science, 2024),
  `github.com/openai/GPTs-are-GPTs` → `data/occ_level.csv`. Free, machine-readable.
- **Method:** `human_rating_beta` — PREDICTED exposure: the share of an
  occupation's tasks an LLM (incl. LLM-powered software) could materially speed
  up, from human annotators. A capability ceiling.
- O*NET-SOC codes mapped to 6-digit SOC (averaging where several roll up); 923
  O*NET-SOC rows → 798 SOC.

### anthropic_exposure.csv (second exposure method)
- **Source:** Anthropic Economic Index — `huggingface.co/datasets/Anthropic/
  EconomicIndex` → `labor_market_impacts/job_exposure.csv` (CC-BY). Free, no key.
- **Method:** `observed_exposure` — OBSERVED exposure built from actual Claude.ai
  usage; an adoption floor, not a capability measure. 756 occupations, native
  6-digit SOC (joins directly to OEWS). 411 occupations show zero observed usage.
- Frey & Osborne (2013/17) remains an un-pulled third method (PDF-appendix only).

### Key result (two methods; 756 occupations, 90.6% of employment)
Employment-weighted exposure: **0.31 predicted** (Eloundou) vs **0.13 observed**
(Anthropic) — the gap between them is the adoption runway. High-exposure
employment: 23% (predicted) vs 4% (observed). The methods correlate 0.60 and both
show exposure **rising with wage** — unlike earlier automation waves.

---

## us_electricity.csv / datacenter_energy.csv — Q3a energy linkage

- **Files:** `data/processed/us_electricity.csv`, `data/processed/datacenter_energy.csv`
- **Scripts:** `fetch_electricity.py`, `fetch_datacenter_energy.py`.
  Analysis: `analyze_energy_linkage.py`.
- **Retrieved:** 2026-05-15.

### us_electricity.csv
- **Source:** EIA API v2, `electricity/retail-sales` — annual US sales (TWh) and
  average retail price (¢/kWh) by sector. Key: `EIA_API_KEY`. 2001-2025.
- **Caveat:** retail *sales* are slightly below total generation (transmission
  losses, direct use), so a data-center share computed against this base runs
  marginally higher than LBNL's generation-based share. Prices are nominal.

### datacenter_energy.csv (manual, Tier 3)
- **Manual source:** `data/raw/manual/datacenter_energy.csv` (hand-keyed).
- **Sources:** LBNL *2024 US Data Center Energy Usage Report* (no machine-readable
  release); EPRI *Powering Intelligence 2026*; cross-checked with CRS R48646.
- **Caveat:** point estimates transcribed from report text — 2023 actual
  (176 TWh, 4.4% of US load) is the well-established anchor; 2028/2030 figures are
  scenario projections. Verify against the primary PDFs before publication.

### Key result
US electricity demand: flat 2007-2020 (-0.1%/yr), then +1.8%/yr 2020-2025.
Data centers 4.4% of US load (2023) → projected 6.7-12% (2028), 9-17% (2030).
Residential retail price doubled, 8.6 → 17.3 ¢/kWh (2001-2025, nominal).

---

## investment_forecasts.csv / projection_assumptions.csv — Q2 projections

- **Files:** `data/processed/investment_forecasts.csv`,
  `data/processed/projection_assumptions.csv`
- **Manual sources:** `data/raw/manual/investment_forecasts.csv`,
  `data/raw/manual/projection_assumptions.csv` (hand-keyed)
- **Script:** `scripts/fetch_forecasts.py` (validates/tidies; no network).
  Analysis: `scripts/analyze_investment_projection.py`.
- **Retrieved:** 2026-05-15.

### investment_forecasts.csv (Method A — third-party forecasts)
- **Sources:** McKinsey *The Cost of Compute* (Apr 2025); Goldman Sachs *Tracking
  Trillions* (2026); Morgan Stanley *AI Market Trends* (2026); Bain *6th Global
  Technology Report* (2025).
- **Verification:** the primary McKinsey/Goldman pages rate-limited during
  compilation; headline figures were corroborated against multiple independent
  reports (DataCenterDynamics, Data Centre Magazine, Fortune) and a web search.
- **Caveats:** scope/metric/horizon differ by source — McKinsey is global
  data-center capex (AI + non-AI), Goldman is global AI capex incl. chips & power,
  Morgan Stanley mixes a US-hyperscaler and a global figure. NOT directly
  comparable without the per-row `scope`/`metric`/`horizon` annotations.

### projection_assumptions.csv (Method B — independent bottom-up)
- These are the **researcher's own modelling choices**, not third-party data:
  year-on-year growth rates (low/mid/high, 2026-2030) applied to the 2025 actual
  seven-hyperscaler capital-investment base (~$424B, computed from
  `hyperscaler_capex_annual.csv`). `capex_intensity_usd_per_mw` = 15 (Goldman
  baseline) is used only for a capacity cross-check.
- **Scope caveat:** Method B covers 7 US hyperscalers only — a SUBSET of the
  global, all-operator third-party forecasts. Documented in the analysis output.

### Result (Method B, cumulative 2026-2030, 7 US hyperscalers)
$2.8T (low) · $4.6T (mid) · $6.8T (high).

---

## vc_ai.csv — venture capital into AI (financing layer)

- **File:** `data/processed/vc_ai.csv`
- **Manual source:** `data/raw/manual/oecd_ai_vc.csv` (hand-keyed)
- **Script:** `scripts/fetch_vc_ai.py` (validates/tidies the manual CSV; no network)
- **Source:** OECD (2026), *Venture capital investments in artificial intelligence
  through 2025*, 17 Feb 2026 — Key messages, p.1. Data from Preqin via OECD.AI.
- **Why manual:** OECD.AI hosts the data but offers no download or API; the
  underlying Preqin data is paid. Figures are therefore transcribed by hand.
- **Retrieved:** 2026-05-15.

### Caveats
- **Financing layer — separate from real investment.** VC into AI-native firms is
  an equity flow; do NOT add it to hyperscaler capex.
- **Point estimates only.** The full 2012-25 annual series exists in the report
  solely as a chart (Figure 2) and is not transcribed. Only 2025 (global + by
  country) and the generative-AI subset for 2022/2023/2025 are captured.
- 2022 World `ai_vc` has a share (30%) but no dollar value — not given in the report.

### Snapshot (2025, AI VC, USD bn)
World 258.7 (61% of all VC) · United States 194.0 (75% of global AI VC) ·
EU27 15.8 · China 13.9 · United Kingdom 13.8. Generative-AI subset: 35.3.

---

## datacenter_construction_monthly.csv / _annual.csv — US data-center construction

- **Files:** `data/processed/datacenter_construction_monthly.csv` and `_annual.csv`
- **Raw:** `data/raw/owid_datacenter_construction_2026-05-15.csv`
- **Script:** `scripts/fetch_datacenter_construction.py`
- **Source:** US Census Bureau, Value of Construction Put in Place (C30) survey,
  data-center category — accessed via Our World in Data's machine-readable mirror
  (`ourworldindata.org/grapher/monthly-spending-data-center-us`), which republishes
  the Census series verbatim. Retrieved 2026-05-15. No API key.
- **Why the mirror:** the direct Census EITS `vip` API was attempted, but the
  category code for data centers could not be resolved without the Census category
  codebook (codes are opaque, e.g. `04XX`, `20IX`). The OWID mirror is the same
  Census numbers; substitute the direct API if the code is later confirmed.
- **Vintage:** monthly, 2014-01 .. 2026-01 (145 obs).

### Caveats
- **Building shell only** — construction put in place. A *subset* of hyperscaler
  capex (servers/equipment are separate); do NOT add to the hyperscaler capex spine.
- **Not seasonally adjusted** — actual monthly values. The annual rollup sums
  calendar months; 2026 is a partial year (Jan only) — flagged `partial_year`.
- Captures *all* US data-center construction (incl. non-hyperscaler / colocation),
  so it is broader than the seven-company capex panel in that one respect.

### Snapshot (annual, USD bn, NSA)
2014 2.2 · 2019 8.8 · 2022 9.9 · 2023 14.3 · 2024 22.2 · 2025 28.6.

---

## semiconductor_revenue_annual.csv — AI-chip supplier revenue (supply mirror)

- **File:** `data/processed/semiconductor_revenue_annual.csv`
- **Raw:** `data/raw/sec_semirev_<ticker>_2026-05-15.json` (one per company)
- **Script:** `scripts/fetch_semiconductors.py`
- **Source:** SEC EDGAR XBRL `companyconcept` API. Retrieved 2026-05-15.
- **Companies / CIKs:** NVDA 1045810, AMD 2488, AVGO 1730168, MU 723125, INTC 50863.
- **Concept:** `us-gaap:Revenues` (NVIDIA) vs.
  `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` (others) — the
  script picks whichever extends to the latest period; recorded in `revenue_concept`.

### Caveats
- **Supply-mirror layer — do NOT add to the real-investment layer.** These chips
  are already inside hyperscaler capex; this panel is a cross-check only.
- **Total company revenue**, not AI-only. NVIDIA's data-center *segment* revenue
  is the AI-relevant slice (in 10-K segment notes) — to be added as a manual entry.
- **TSMC excluded** — files IFRS 20-Fs in New Taiwan dollars; handle manually.
- Fiscal years vary (NVDA ends Jan, AVGO Nov, MU Aug, AMD/INTC Dec).

### Snapshot (latest fiscal year, revenue, USD bn)
NVIDIA 215.9 (FY2026) · Broadcom 63.9 (FY2025) · Intel 52.9 (FY2025) ·
Micron 37.4 (FY2025) · AMD 34.6 (FY2025). Five-firm total ≈ $405 bn.

---

## macro_investment.csv — macro denominator series (FRED)

- **File:** `data/processed/macro_investment.csv`
- **Raw:** `data/raw/fred_<series_id>_2026-05-15.json` (one per series)
- **Script:** `scripts/fetch_macro_investment.py`
- **Source:** FRED API, `https://api.stlouisfed.org/fred/`. Key: `FRED_API_KEY`.
  Retrieved 2026-05-15.
- **Series:** `A679RC1Q027SBEA` (fixed investment in IT equipment & software),
  `B985RC1Q027SBEA` (software), `PNFI` (private nonresidential fixed investment),
  `GDP` (nominal), `GDPC1` (real, chained 2017$), `SP500` (index level).
- **Vintage:** FRED series are revised. Quarterly series latest obs 2026-01-01
  (Q1 2026, SAAR); `SP500` daily, latest 2026-05-14.

### Caveats
- The four $-denominated quarterly series are **nominal, seasonally-adjusted
  annual rates** — not directly comparable to companies' fiscal-year actuals
  without annualization/alignment. `GDPC1` is real (chained 2017$).
- `SP500` is the **index level**, not market capitalization; market-concentration
  (Mag-7 share) work needs a separate source.

---

## hyperscaler_capex_annual.csv — hyperscaler annual capital investment

- **File:** `data/processed/hyperscaler_capex_annual.csv`
- **Raw:** `data/raw/sec_capex_<ticker>_2026-05-15.json` (cash capex) and
  `data/raw/sec_finlease_<ticker>_2026-05-15.json` (finance leases), per company.
- **Script:** `scripts/fetch_hyperscaler_capex.py`
- **Source:** SEC EDGAR XBRL `companyconcept` API —
  `https://data.sec.gov/api/xbrl/companyconcept/CIK<cik>/us-gaap/<concept>.json`
- **Retrieved:** 2026-05-15. No API key; SEC requires a descriptive `User-Agent`.
- **Companies / CIKs:** MSFT 789019, GOOGL 1652044, AMZN 1018724, META 1326801,
  NVDA 1045810, ORCL 1341439, CRWV 1769628.
- **Vintage:** values are as-filed; each row carries its own `filed` date and
  `accession`. Where a fiscal year recurs across filings (restated comparatives),
  the most recently filed value is kept.

### Two components captured
- **`capex_usd`** — cash capex, cash-flow statement. Concept differs by company:
  MSFT, GOOGL, META, ORCL, CRWV use `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`;
  AMZN, NVDA use `us-gaap:PaymentsToAcquireProductiveAssets` (they retagged — the
  older concept holds a stale series ending AMZN FY2016 / NVDA FY2012). The script
  picks, per company, whichever concept extends to the latest period; the choice
  is recorded in the CSV `capex_concept` column.
- **`finance_lease_additions_usd`** — `us-gaap:RightOfUseAssetObtainedInExchange
  ForFinanceLeaseLiability`. A **non-cash** item: data-center capacity funded by
  finance leases. `NULL` where not reported (NVDA does not report it).
- **`total_capacity_investment_usd`** = cash capex + finance-lease additions.

### Caveats
- **Cash capex and finance leases differ in kind** — one is a cash outflow, the
  other a non-cash asset addition. They are summed for a fuller capacity picture
  but should not be treated as interchangeable.
- **Still excludes operating-lease-funded capacity**, so the total remains a
  partial measure of data-center capacity investment.
- NVDA's `PaymentsToAcquireProductiveAssets` line covers "property, equipment and
  intangible assets" — slightly broader than pure PP&E.
- **Fiscal years are not calendar-aligned:** MSFT FY ends June, NVDA late Jan,
  ORCL May, others December. `fiscal_year` is labelled by period-end year.
- Coverage length differs by company (CRWV only IPO'd in 2025; NVDA's current
  concept starts ~FY2022).

### Snapshot (latest fiscal year, USD bn — cash capex / + finance leases / = total)
Amazon 131.8 / 2.9 / 134.7 (FY2025) · Alphabet 91.4 / 1.6 / 93.1 (FY2025) ·
Microsoft 64.6 / 20.5 / 85.1 (FY2025) · Meta 69.7 / 0.6 / 70.3 (FY2025) ·
Oracle 21.2 / 2.9 / 24.1 (FY2025) · CoreWeave 10.3 / 0.3 / 10.7 (FY2025) ·
NVIDIA 6.0 / n.a. / 6.0 (FY2026). Seven-company total ≈ $424 bn.
