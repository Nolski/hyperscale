# Methodology — broadening the analysis beyond the 7 hyperscalers

*Research thread added 2026-06-01. The project has measured the AI bet through ~7 hyperscalers
and ~5 chipmakers — its core, not its footprint. This note is the blueprint for widening to the
**AI-industrial complex**: how others measure the AI economy, the sectors we've missed, and —
the crux — exactly how to pull the additional data. Core build: `fetch_bea.py` +
`analyze_macro_attribution.py` (the macro layer) and `fetch_ai_complex.py` +
`analyze_ai_complex.py` (the supply-chain footprint). The other layers are specified here for
the next build.*

## 0. The discipline that governs all of this: exposure ≠ attribution

The hardest problem in broadening is the **AI boundary**. Eaton makes electrical gear; some of
it goes to data centers, most does not. NextEra sells power; a slice serves AI. Counting their
*whole* revenue as "AI" would be a lie of convenience. So three rules, applied everywhere below:
1. **Prefer disclosed segments.** Where a firm reports an AI / cloud / data-center segment, pull
   it (`get_segment_data`, proven on AWS/GCP/MSFT) and use that, not the whole company.
2. **Otherwise: label it exposure, not attribution.** A firm's total revenue is an *upper bound*
   on its AI tie; report it as "AI-exposed," in ranges, never summed into one "AI total."
3. **Use the macro layer for the disciplined number.** BEA's contribution-to-growth and
   input-output don't require firm-by-firm guessing — they measure the IT-investment component of
   the economy directly. That is the rigorous answer to "how big is this?"; the firm rollup is
   the texture around it.

## 1. How others measure the AI footprint (and which method we take)

- **Jason Furman (Harvard):** information-processing equipment + software ≈ **92% of US real GDP
  growth in H1 2025**; without it, ~0.1% annualized. *Method we adopt:* contribution-to-growth
  from BEA, replicated with primary data (below).
- **IMF** (WP/25/76 "Mind the Gap"; 2026 scenario notes): ~40% of global / ~60% of advanced-economy
  employment AI-exposed; "macro-critical transition." *Method:* occupational exposure (we already
  have Eloundou + Anthropic; extend with BLS).
- **FSB** (May 2026 private-credit vulnerabilities report) + **BofA survey** (34% of managers: AI
  capex = most likely systemic credit trigger) + **JPMorgan** (~$1.5T IG issuance needed):
  the financing-fragility layer.
- **Goldman "Tracking Trillions"**, **IDC** (semis $1.29T in 2026; HBM the binding constraint,
  60–70% margins), **Deloitte** (US AI power 4→123 GW by 2035): supply-chain sizing/bottlenecks.
- **BIS Bulletin 120**, **ECB/OECD** outlooks: AI capex as a macro growth driver.

## 2. The AI-industrial-complex map + per-layer acquisition spec

### Layer 1 — Macro-attribution  *(BEA + FRED; primary; CORE BUILD)*
- **Source/route:** BEA API `https://apps.bea.gov/api/data` (UserID=`BEA_API_KEY`, method=GetData,
  datasetname=NIPA). **Verified working.** Key tables:
  - **T50306** — Real Private Fixed Investment by Type (chained $). Line for
    *"information-processing equipment and software"* (the Furman category), plus its parts
    (info-processing equipment, software, IP products). The numerator.
  - **T10106** — Real GDP, chained-$ levels (line 1). The denominator for contribution-to-growth.
  - **T10102** — Contributions to % change in real GDP (aggregate Equipment + IP-products lines) —
    sanity cross-check.
- **Method:** contribution of IT-investment to real GDP growth ≈ annualized QoQ Δ(real IT
  investment) ÷ lagged real GDP; share of total real GDP growth; IT investment as % of GDP over
  time. (Approximates BEA's chain-weighted contributions; cross-checked against T10102.)

### Layer 2 — The supply-chain complex  *(expanded SEC EDGAR; primary; CORE BUILD)*
- **Route:** reuse the `companyconcept` REST pattern from `fetch_hyperscaler_capex.py`; resolve
  CIKs from SEC's `company_tickers.json`; pull **Revenues** and **capex**
  (`PaymentsToAcquirePropertyPlantAndEquipment`) per firm; tag each with a `layer`. Foreign filers
  (ASML, TSMC) try the **`ifrs-full`** namespace; flag if absent. Prefer `get_segment_data` where
  an AI/DC segment exists.
- **Universe (US-listed unless noted):**
  - Memory: **MU** (have via semis); SK Hynix / Samsung → Tier-2 (foreign).
  - Equipment: **ASML** (20-F/ifrs), **AMAT**, **LRCX**, **KLAC**.
  - Networking/interconnect: **ANET**, **MRVL**, **AVGO** (have).
  - Data-center REITs: **EQIX**, **DLR**.
  - Electrical & cooling: **VRT**, **ETN**, **GEV**, **PWR**.
  - Power / IPP / utilities: **CEG**, **VST**, **NRG**, **NEE**, **D**.
  - Neoclouds: **CRWV** (have), **NBIS** (foreign → Tier-2).
- **Output:** size the complex by revenue & capex per layer vs the hyperscaler core; segment where
  disclosed, else **exposure** (flagged).

### Layer 3 — Systemic financing / private credit  *(FRED + Tier-2; staged)*
- **Route:** FRED (IG/HY OAS + issuance proxies — partly have) + a manual `private_credit.csv`
  (Tier-2) capturing the FSB report, JPMorgan ~$1.5T IG-issuance estimate, BofA-survey share, and
  insurer/pension/bank linkages; optionally SEC BDC filings for direct private-credit exposure.
- **Method:** size the AI debt wave vs total IG issuance; map who holds it (banks→funds→
  insurers/pensions); the contagion path. Schema: `metric,value,unit,source,url,verified,note`.

### Layer 4 — Labor & productivity, economy-wide  *(BLS + Census; staged)*
- **Route:** **BLS API** (`BLS_API_KEY`, v2) — labor productivity by industry, QCEW employment by
  detailed industry; **Census ACES** (`CENSUS_API_KEY`) — capital expenditures by industry (an
  economy-wide cross-check on the SEC firm rollup). Extends the existing OEWS + Eloundou/Anthropic
  exposure work from headline occupations to the whole labor market and to productivity.

## 3. Reuse (existing machinery)

`fetch_hyperscaler_capex.py` (companyconcept candidate-concept + 10-K annual-facts dedup) →
`fetch_ai_complex.py`. `fetch_macro_investment.py` (FRED key/raw-tidy) → `fetch_bea.py`.
`fetch_vc_ai.py` (manual-loader validation) → the Tier-2 files. `get_segment_data` MCP → segment
splits. Keys (`BEA/BLS/CENSUS/EIA/FRED/SEC`) all in `.env.sh`, loaded into the session.

## 4. What this cannot settle

- The **AI boundary is fuzzy**; complex-revenue is exposure, not a clean AI total. Never summed
  into one "AI GDP" figure without flagging.
- BEA figures are **real (chained) and revised** — note vintage; contribution-from-real-levels is
  an approximation of BEA's chain-weighted contributions.
- Foreign-filer, private-credit, and commodity/HBM-spot figures are **Tier-2**.
- Macro-attribution is **contribution, not causation** (Furman's own caveat: absent the boom,
  lower rates/power would have offset perhaps half).
