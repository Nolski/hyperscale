# Methodology — AI Hardware Economics: Energy, Efficiency, Depreciation & Token Value

*Research thread added 2026-05-29. Scope: the unit economics of AI accelerators and the
data centers they sit in — how hardware efficiency, hardware price, electricity price, and
token price/usage jointly determine an asset's value and its true useful life. Grew out of
the depreciation work (`analyze_hyperscaler_depreciation.py`). This note is the spine;
`scripts/fetch_gpu_specs.py`, `scripts/model_gpu_tco.py`, and
`scripts/model_economic_obsolescence.py` operationalize Threads 1–2; Threads 3–5 are
designed here with data staged. Bibliography: `notes/bibliography_hardware_economics.md`.*

---

## 0. The reframe (read this first)

There are **three different "useful lives"** for a GPU, and they get conflated:

| Life | Set by | Typical |
|---|---|---|
| **Physical life** | when the silicon fails (heat, wear) | unknown for AI GPUs run hot 24/7; maybe 3–6+ yrs |
| **Accounting life** | the depreciation schedule in the 10-K | extended to **6 years** (MSFT, GOOGL, 2023) |
| **Economic life `L*`** | when it's cheaper to run a NEWER chip per unit of work | the real question — and often **shorter** |

A chip dies **economically**, not physically, when running it costs more per token than
buying-and-running a more-efficient successor. **Energy is the swing variable**: an old
chip's only ongoing cost is power, so its competitiveness collapses when (i) new chips are
far more efficient (perf/watt), and/or (ii) electricity gets expensive. If the economic life
`L* < ` the 6-year accounting life, depreciation is **understated** and reported earnings
**overstated** — which loops back to the debt-financed buildout (the prior thread): the
financing rests on profits that may be flattered by an over-generous life assumption.

This single TCO/efficiency frame ties together everything: efficiency (sets perf/watt),
hardware price (capex per unit work), electricity price (the old-chip kill switch), and
token price/usage (the revenue the asset must earn before it's obsolete).

---

## The unifying model

A vintage `g` is retired in favor of the best new chip `g'` when:

```
  e_g · PUE · P_elec        >        capex_g'/W_g'   +   e_g' · PUE · P_elec   +  opex
  └ old chip: ENERGY ONLY ┘          └──────── new chip: ALL-IN per unit work ────────┘
```

with `e = system_power / throughput` (energy per unit work) and `W = lifetime work`. Per
unit of compute delivered (using effective dense-FLOP at a fixed precision as the work unit,
and assuming tokens ∝ FLOP for a fixed workload — MLPerf refines this in Thread 4):

```
  energy_cost_per_PFLOP   = (system_power_kW · P_elec) / (peak_PFLOPps · 3600)
  capex_cost_per_PFLOP(L) = msrp / (peak_PFLOPps · 3600 · 8760 · utilization · L)
  system_power_kW         = tdp_kW · system_overhead_factor · PUE
```

`L*(g)` = years until a successor's all-in cost undercuts `g`'s energy-only cost. It
**shortens** as the efficiency gap widens, `P_elec` rises, or new-chip capex falls.

---

## Thread 1 — Economic vs accounting useful life  *(BUILT)*

**Questions.** Is `L* < L_acct` (6 yrs)? By how much, and under what electricity-price
scenarios? If economic life is ~2–3 yrs while the books assume 6, how overstated is
hyperscaler operating income? Does the gap widen exactly when the buildout is most
debt-financed?

**Method.** `model_economic_obsolescence.py`: walk the Nvidia vintage chain (V100→A100→
H100→H200→B200), apply the retirement inequality, solve `L*` per vintage under electricity
scenarios (current industrial ~8¢/kWh; Dallas-Fed +20–50% from `electricity_price_outlook.csv`).
Compare to `server_useful_life_changes.csv` (4→6 yr) and scale against
`hyperscaler_depreciation.csv` for a back-of-envelope earnings-overstatement figure.

**Model lineage.** Vintage-capital theory & embodied technical change (Solow 1960; Johansen);
**economic vs accounting depreciation** (Hulten & Wykoff 1981). See bibliography.

**Data.** `gpu_specs.csv`, `pue_assumptions.csv`, `us_electricity.csv` (industrial price),
`electricity_price_outlook.csv`, `server_useful_life_changes.csv`, `hyperscaler_depreciation.csv`.

## Thread 2 — Energy share of TCO + scrap threshold  *(BUILT)*

**Questions.** What fraction of a GPU's lifetime cost is electricity (vs upfront silicon)?
How sensitive is that to electricity price, PUE, and utilization? At what electricity price /
efficiency gap does it become cheaper to **scrap** an old chip than keep paying its power
bill?

**Method.** `model_gpu_tco.py`: lifetime TCO = `msrp + Σ_t energy_t`; report energy share,
$/effective-PFLOP-hour, and the break-even (scrap-threshold) electricity price per vintage.
Sensitivity grids over `P_elec`, utilization, PUE.

**Data.** as Thread 1, plus `us_electricity_by_state.csv` (regional) and
`datacenter_power_deals.csv` (PPA $/MWh as alternative price inputs).

## Thread 3 — Jevons / energy rebound  *(DESIGNED; data staged)*

**Questions.** Does better perf/watt **reduce** or **increase** total data-center energy?
"New hardware uses less energy" is a per-chip statement; the system answer depends on
demand. Total energy `E = C · e` (compute demand × energy-per-compute); `E` grows iff
demand-growth `r_C` exceeds efficiency-gain `r_e`. Historically for compute `r_C ≫ r_e`, so
efficiency has **grown** total energy (the Jevons paradox / rebound).

**Method (to build).** `model_energy_rebound.py`: combine the efficiency trend (FLOP/watt
from `gpu_specs.csv` / Epoch) with compute-demand-growth scenarios; project total DC energy;
compare to LBNL (`datacenter_energy.csv`, 176 TWh→325–580 TWh). Report the rebound
elasticity and the demand-growth rate at which efficiency gains are fully offset.

**Model lineage.** Jevons (1865); modern energy-rebound literature. **Data.** `gpu_specs.csv`,
`fetch_epoch_hardware.py` output, `datacenter_energy.csv`, `us_electricity.csv`.

## Thread 4 — Token unit economics / asset NPV  *(DESIGNED; data staged)*

**Questions.** Given that `$/token` (inference) has fallen ~an order of magnitude per year
for a given capability while usage explodes, what is the NPV / break-even of a GPU vintage?
Does revenue-per-GPU keep pace with the capex it must amortize before becoming obsolete (`L*`
from Thread 1)? What break-even token price does the buildout implicitly require?

**Method (to build).** `model_token_economics.py`:
`NPV = Σ_t (tokens_served_t · price_tok_t − energy_t − opex_t)/(1+d)^t − capex`, with
`tokens_served` from throughput (MLPerf, ideally) × utilization × `L*`. Solve break-even
token price; compare to the observed `$/token` path. Tie to Thread 1: shorter `L*` ⇒ less
lifetime revenue to cover the same capex.

**Data (staged).** `token_prices.csv` (API $/Mtok over time), `gpu_rental_rates.csv`
(H100/A100 $/hr — a market read on hardware value decay), MLPerf throughput (to add),
`gpu_specs.csv`.

## Thread 5 — China vs US hardware philosophy & energy  *(DESIGNED; qualitative + data)*

**The reframe.** "Efficiency" is not absolute — it is contingent on energy economics, and
the US and China optimize for different constraints:
- **US / Nvidia:** leading-edge process (TSMC 4N/3nm) → maximize **perf/watt** on a single
  die. Power is a binding constraint (grid limits, high prices), so efficiency is the prize.
- **China:** export controls cap access to leading nodes (SMIC ~7nm) and to Nvidia parts, so
  Chinese designers compensate with **scale-out / system-level** integration — e.g. Huawei's
  **CloudMatrix 384** networks 384 Ascend 910C chips to rival an Nvidia GB200 NVL72 at the
  *system* level, but at **far higher total power draw**. China trades **energy efficiency
  for compute availability** — and that trade is economic because Chinese power is cheaper
  and more abundant (hydro/coal/solar buildout).

**Questions.** Is Chinese hardware closing the *system-performance* gap while losing the
*perf/watt* gap? What does export-control-driven divergence imply for the **global energy
footprint** of AI (a more energy-intensive Chinese compute base)? Does cheap Chinese power
make a "scale over efficiency" strategy durably rational — and does that undercut the premise
that efficiency gains will bound AI's energy demand? Connects to the paper's
geopolitical-compute-concentration question.

**Data / sources (qualitative-led, all `[verify]`).** Huawei Ascend 910B/910C specs and
CloudMatrix benchmarks (SemiAnalysis); SMIC process-node status; US BIS export-control rules;
CSET (Georgetown) and CSIS analyses; Epoch AI compute-by-country. Captured as flagged rows in
`gpu_specs.csv` (`country` column) and written up in the bibliography.

---

## What the models cannot settle

- **Physical longevity is unknown** — the model assumes *economic*, not *failure*,
  retirement. If GPUs genuinely last 6 yrs, the accounting life is defensible.
- **Vendor FLOPS are marketing** — precision/sparsity inconsistencies; we store dense bf16
  and dense fp8 separately and flag sparsity. Peak ≠ realized throughput (MLPerf, Thread 4).
- **tokens ∝ FLOP is a simplification** — fine for cross-vintage ratios; Thread 4 replaces it
  with measured tokens/sec.
- **Token-price/usage and China specs are Tier-2 / `[verify]`**; rebound elasticity is
  assumed, not estimated — scenarios, not forecasts.
- **Electricity-price causation stays contested** (Dallas Fed vs IER, per the energy notes).

## Build order (this thread)

1. This note + `bibliography_hardware_economics.md`.
2. `gpu_specs.csv` + `fetch_gpu_specs.py`; `pue_assumptions.csv`.
3. `model_gpu_tco.py` (Threads 1–2 foundation).
4. `model_economic_obsolescence.py` (the depreciation↔energy headline).
5. `fetch_epoch_hardware.py` (efficiency-trend enrichment; manual fallback).
6. Stage `token_prices.csv` / `gpu_rental_rates.csv`; later build `model_energy_rebound.py`
   (Thread 3) and `model_token_economics.py` (Thread 4).
