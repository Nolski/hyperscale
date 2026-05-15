# Cross-cutting synthesis — the AI investment cycle and the autocolonial churn

*Working synthesis of the empirical findings (Q1–Q3) against the paper's
argument. Compiled 2026-05-15. Every figure here is traceable to a dataset in
`data/processed/` and a provenance entry in `notes/provenance.md`; the headline
numbers are collected in `output/synthesis_indicators.csv` and the integrating
figure is `output/fig_synthesis_dashboard.png`.*

This memo connects three empirical strands to the paper's three claims. It is
deliberate about where the data **supports** the argument and where it **cannot
reach** it — the second list matters as much as the first.

---

## 1. The investment cycle is real, macro-scale, and extraordinarily concentrated

Seven hyperscalers spent **$424B** on capital investment in 2025 (cash capex +
finance leases), up from roughly $20B a decade earlier and nearly double the 2024
figure. That single year is:

- **1.4%** of US GDP,
- **~10%** of *all* US private nonresidential fixed investment,
- **30.7%** of *all* US investment in IT equipment and software.

The paper frames AI as "hyperscaling" — an investment cycle, not merely a
technology. The capital accounts bear this out literally: a discrete, steep surge
in fixed-capital formation, concentrated in seven firms that now command close to
a third of the economy's information-technology investment. This is the
empirical content of "hyperscaling": the prefix is a description of the capital
intensity, and the concentration is its political-economic signature. Around the
spine sit a **$259B** global venture flow into AI firms (the financing layer) and
**$405B** of AI-chip revenue (the supply mirror) — separate accounts, not
additive, but each confirming the same concentration.

## 2. The forward bet outruns the revenue — which is where the "backstop" thesis lives

The projection work puts cumulative 2026–2030 capital investment for the seven US
hyperscalers at **$2.8T–$6.8T** (independent estimate, mid case $4.6T); the
global, all-operator third-party forecasts run **$6.7T** (McKinsey, data-center
capex) to **$7.6T** (Goldman, AI capex incl. chips and power).

The paper's provocative claim — "why is this bubble different? it is geopolitical
… the state has infinite money … valuations don't matter" — is not something the
data can *prove*. What the data can do is **size the gap the backstop thesis
points at**. Bain's finding (carried in the forecast catalogue) is that funding
this path needs roughly **$2T/yr of new revenue by 2030**, against an estimated
**~$800B funding shortfall**; Goldman itself flags its numbers as "baseline
estimates, extremely sensitive." A forward commitment of multiple trillions is
being made against a revenue base that, on these sources' own arithmetic, does not
yet exist. That structural gap — committed capex vs. revenue to service it — is
the empirically loadable core of the "geopolitically-backstopped cycle" argument.
The *backstop* itself (intent, guarantee, the state's role) is a claim the
financing data here cannot adjudicate; see §4.

## 3. The churn: the cycle's costs are displaced onto energy and labour

The paper's "autocolonial churn" names a dispossession turned inward — extraction
whose targets are domestic. Two cost systems measured here are consistent with
that framing, and notably **every cost series is a US-domestic one**.

**Energy.** US electricity demand was flat for thirteen years (−0.1%/yr,
2007–2020); it is now rising (+1.8%/yr, 2020–2025). Data centers were **4.4%** of
US electricity in 2023 and are projected at **9–17%** by 2030. Over 2001–2025
residential electricity prices **doubled** (8.6¢ → 17.3¢/kWh, nominal). The load
growth is corporate; a rising share of the bill is borne by households. The data
shows the *coincidence* of surging corporate load and rising household prices —
it does not by itself establish that the former *causes* the latter (see §4) —
but the distributional shape (private capital formation, socialised grid cost) is
exactly the "churn" the paper theorises.

**Labour.** The average US job has **~32%** of its tasks LLM-exposed
(employment-weighted); **23%** of employment sits in high-exposure occupations.
Crucially, exposure **rises with wage** — bottom wage decile ~0.20, deciles 7–10
around 0.42–0.50. Earlier automation waves hit manual, lower-wage work; this one
concentrates on cognitive, linguistic, white-collar tasks. The most-exposed large
occupations — customer-service representatives, sales representatives,
secretaries and administrative assistants — are the white-collar core, and they
are precisely the roles the paper's introduction flags. This is the labour-market
shadow of the paper's central claim about the **dispossession of cultural capital
(language, art, music, code)**: the tasks being absorbed are linguistic and
interpretive. "Language is leaving us" has a measurable occupational footprint.

**Capital allocation** is itself a third site of churn: directing ~31% of US IT
investment into seven firms' data centers reallocates the economy's investable
surplus toward the buildout — a crowding effect that the GDP-share figures make
visible.

## 4. What the data does NOT show — load-bearing caveats

The argument is strengthened, not weakened, by stating these plainly:

- **No clean AI/non-AI split.** Filings do not disaggregate AI capex; the $424B
  includes non-AI cloud. "AI investment" here is a scoped proxy, not a clean
  measure.
- **The buildout is larger and more opaque than measured.** Cash capex + finance
  leases still excludes operating-lease- and SPV/JV-financed capacity. The
  financing layer (private credit, off-balance-sheet vehicles) is not captured —
  and it is exactly where the "backstop" would operate.
- **The backstop is a thesis, not a finding.** The data sizes the revenue gap; it
  cannot show state intent, an implicit guarantee, or whether demand will
  materialise. Model collapse and demand realisation are unmeasured here.
- **Exposure is not displacement.** The Eloundou β measures task *exposure*, not
  job loss. The labour data shows what is exposed, not what has been automated;
  the paper should not let the two slide together. It is also *one* methodology —
  Anthropic's Economic Index and Frey & Osborne would bracket it.
- **Electricity-price causation is not established.** Prices rose for many
  reasons; attributing the rise to data centers needs the node-level / Dallas Fed
  work, not these aggregates.
- **Scope is US-primary.** The geopolitical-concentration strand — compute and
  capital concentrated across borders — is thinner here than the domestic strands.

## 5. Open questions / next data work

1. **Bracket the labour estimate** — add the Anthropic Economic Index (and
   Frey-Osborne) as second/third exposure methods; present a range.
2. **The financing layer** — pursue private-credit and SPV/JV disclosures; this
   is the missing evidence for or against the backstop thesis.
3. **Electricity-price attribution** — node-level / Dallas Fed analysis to move
   from coincidence to causation.
4. **Demand realisation** — track revenue against the forward bet; the gap in §2
   is the live empirical question.
5. **International concentration** — compute geography (chips, data-center siting)
   to firm up the geopolitical strand.
