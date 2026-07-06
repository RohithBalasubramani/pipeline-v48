# CMD V2 Card Atomization Audit — card-wise vs page-wise payloads

> ⚠️ HISTORICAL / PRE-MORPH SNAPSHOT (audited 2026-06-23). The payload MODEL has since CHANGED.
> This audit was written under the OLD "per-tab-frame + 3 dialects (flat_asset / widgets_envelope / column_row)" mental model, where Layer 2 emitted a whole backend frame and the only "atom" for coupled cards was the whole snapshot/composite/tab.
> CANONICAL NOW (CMD V2 §B4 "payload-morph", 2026-06-29): the card contract is **ONE payload per card = {data + metadata}, ONE flat object, every key EXACTLY once, no second `root`**. Layer 2 emits ONE payload PER CARD (each card authors its OWN `exact_metadata` block + a `data_instructions` recipe); the per-tab "dialects" survive ONLY as the DATA-FILL (mapper-input) shape a helper targets, NOT as Layer 2 output. Interdependent pages use **Approach B = shared_context (single DATA buffer + interaction seeds + truly-shared config) + lean atoms that each carry their own exact_metadata** (3-tier: lean-on-DATA, fat-on-METADATA); the HOST owns the shared cursor/selection.
> For the CURRENT model see: `V48_PAYLOAD_MORPH_CORRECTION.md` (canon for the contract) and `V48_INTERDEPENDENT_CARDS_DESIGN.md` (canon for Approach B). The interdependency CLASSIFICATION below (which cards share a snapshot / a cursor / multiple keys) is still VALID and still informs Approach B; but every "treat the snapshot/composite/tab as THE atom" / "cannot emit per-card" verdict below is SUPERSEDED — read those as "these cards are interdependent and must share a DATA buffer," not "these cards cannot each be their own atom."

> Audited 2026-06-23 across `CMD_V2/src` (asset tabs, electrical/lt-pcc tabs, energy tabs, composites/3D/story, widgets-v2 registry). Grounded with file:line in the source mappers/viewModels.
> **Question:** can every card have its OWN separable JSON payload (card-wise), or is the data page-wise (shared/bundled across cards)?

## HEADLINE: MIXED

Standalone history/chart cards and the registry/StoryCard widgets are **cleanly card-wise**. But the live/summary cards, several history cards, and **every synced-cursor combo** read a **shared flat snapshot** or a **sibling-owned cursor/selection** — so their DATA is not independent.

> ⚠️ The OLD conclusion here — "the honest unit of separability is the atomic card OR the whole composite/tab, not always the individual card" — is SUPERSEDED. Under §B4 / Approach B the unit of separability IS always the individual card (one `{data + metadata}` payload each); the coupling the audit found is real but is resolved by a single `shared_context` DATA buffer the coupled cards read from, NOT by giving up per-card atoms. Read this HEADLINE as "these cards share DATA," not "these cards can't be atoms."

## Net rule for V48

> ⚠️ SUPERSEDED by §B4 / Approach B. The OLD rule below concluded Layer 2 "cannot emit a fully independent JSON for every individual card" and must bundle coupled cards into one composite/tab payload. CANON now is the opposite: Layer 2 emits **ONE payload per card** (each card = a pure function of its OWN `{data + metadata}`, every key once). Interdependent cards are NOT bundled into a single payload — they each stay a LEAN atom carrying their own `exact_metadata`, and the truly-shared DATA lives ONCE in a `shared_context` buffer (Approach B), with the **host owning the shared cursor/selection** (`selectedSampleIndex`, `selectedFeederId`, `selTime`, `selectedBucket`, `selectedLabel`). The classification below stays useful as the map of WHICH cards must read from that one `shared_context`.
>
> ~~OLD: Layer 2 can emit one payload per ATOMIC card AND one bundled payload per composite/combo or shared-snapshot tab, with the host owning any shared cursor/selection state. It cannot emit a fully independent JSON for every individual card.~~

## The card-wise cases (DATA is independent — no shared buffer needed)

> Note (§B4): "card-wise" here means the card's DATA is self-contained, so it needs NO `shared_context`. It does NOT mean "only these get a per-card payload" — under canon EVERY card gets its own `{data + metadata}` payload; the cases below are simply the ones with no DATA coupling. The OLD "and ONLY these" qualifier is SUPERSEDED.

- **UPS standalone history charts (2):** Battery Health History, Backup Readiness History — each reads ONE dedicated history array and opens its OWN range-filtered socket.
- **UPS Source Transfer — Composite chart (1):** own `history` socket, one `compositeHistory[]`.
- **energy-power widget cards (3):** Today Live Power Analysis (`widgets.live_power`), Energy Consumption Trend (`widgets.energy_trend.buckets`), Daily Power Demand by Feeder (`widgets.demand_profile`) — each reads exactly one keyed widget.
- **widgets-v2 registry family** — per-widget by construction (lowest-confidence; thin evidence).
- **As one-object-per-card (intra-card coupling only):** 3D Asset Viewer (one bundle: kpis+annotations+breakerStatuses+loadHeatmap+currentFlows), StoryCard (one `StoryCardData`).

## The NOT-card-wise cases (shared DATA → must read from one `shared_context`)

> These cards share DATA / a cursor / a selection. Under §B4 they STILL each get their own per-card `{data + metadata}` payload (per-card Layer 2 is NOT broken); the shared DATA + cursor/selection live ONCE in `shared_context` (Approach B) and the host owns the cursor. The classification below is the authoritative map of WHICH cards must point at that one buffer. (OLD header "break a naive per-card emit" → read as "break a naive DUPLICATE-the-data emit.")

**(A) page-wise-shared** — multiple sibling cards read fields off ONE snapshot / `points[]` / `visibleQueue` (shared scalars):
- DG voltage-current: Voltage Live Health + Current Live Health share one flat snapshot (`load` read by both).
- DG engine-cooling: Thermal chart + Mech chart read the SAME indivisible `points[]` (split is only a `SERIES[].chart` config tag, not a JSON slice).
- UPS battery-autonomy: Battery Health + Backup Readiness share `snapshot` + once-computed `derived`.
- UPS source-transfer: Transfer Readiness + Activity share one `live` snapshot frame.
- electrical voltage-current: Voltage Health + Current Health are sub-slices of one fused snapshot (Current Health even falls back into the sibling's `currentHistory.stats`).
- electrical real-time-monitoring: Power&Energy + Voltage Monitor + Current Monitor all derive from ONE `visibleQueue` + one shared time axis (mapper: the axis is only honest if all read the same slice).
- electrical power-quality: PQ Summary shares the aggregate widget with the trend charts' threshold lines.

**(B) cross-card-coupled** — shared status object, or a sibling-owned cursor/selection dictates another card's content/shape:
- Transformer thermal-life: Thermal Life + Life & Capacity share ONE `status` object; agingFactor/headroomKva/lifeRemainingYears each read by 2+ cards.
- energy-power: Cumulative Energy reaches into `widgets.live_power` for its insight.
- lt-pcc real-time-monitoring: Heatmap + Rail — heatmap sets selection and pushes `select_feeder`; the **Rail's very SHAPE** is a function of the heatmap's selection.
- RT-Monitoring combo: Heatmap section + Footer scrubber + Rail share ONE history buffer + ONE `selectedSampleIndex` cursor + ONE selection owned by the hub.
- BMS Overview Split: shared `selTime` + `selectedSeries` across chart + footer + detail.
- DG Operations & Runtime grid: shared `selectedBucket` re-scopes the PowerEnergy panel.
- V&C panel tab and Harmonics & PQ tab: tab-level `selectedLabel` shared across timeline + panels/strip + table.

**(C) card-spans-multiple-keys** — one card reads several frame keys / reaches into the shared snapshot or thresholds:
- DG Voltage History, Current History (history + `labels` (shared) + today + snapshot fallback).
- Transformer Thermal Timeline (timeline[] + thresholds), Insulation Aging & LOL (aging[] + snapshot scalars shared with summary cards).
- electrical Voltage/Current History trends (history envelope + live-queue fallback).
- electrical PQ Distortion+Harmonic / Load Impact (one history `{buckets}` feeding both charts + snapshot limit lines).
- Energy Distribution rail + Flow Diagram (header+incomers+consumers; flow rebuilds its own sankey).

## Implication for V48 per-card Layer 2 (gap #2)

> ⚠️ This section's verdicts are RE-CAST under §B4 / Approach B. The OLD bullets said coupled cards "can't be split" and must stay "frame/composite-scoped" with the snapshot/composite "as the atom." CANON now: every card IS its own atom (one `{data + metadata}` payload, every key once); coupling is handled by a single `shared_context` DATA buffer, not by bundling payloads. The still-correct insight preserved here is "don't duplicate the shared DATA / shared time axis / shared keys" — which is exactly what `shared_context` + de-dup achieve. Mapping each OLD verdict to canon:

- **Card-wise cards** → Layer 2 emits one payload per card (its own `exact_metadata` + `data_instructions`); a stitcher assembles the tab. Works. (Unchanged.)
- **page-wise-shared cards** → still emit **one payload per card** (each carries its own `exact_metadata`), but the truly-shared scalars / time axis live ONCE in `shared_context` and the cards READ them — they are NOT duplicated into each card. (OLD "treat the flat snapshot as the atom / emit one snapshot at tab level" → SUPERSEDED; the anti-duplication / "shared axis must not lie" concern is satisfied by the single `shared_context` DATA buffer, not by collapsing the cards.)
- **cross-card-coupled combos** → still **one lean atom per card**; the shared DATA buffer + interaction seeds live ONCE in `shared_context`, and **the host owns the shared cursor/selection** (`selectedSampleIndex`, `selectedFeederId`, `selTime`, `selectedBucket`, `selectedLabel`). (OLD "treat the whole composite as the atom / members can't be split / emit ONE bundled payload" → SUPERSEDED by Approach B: members ARE separate atoms over one shared_context.)
- **card-spans-multiple-keys** → emittable per card; shared keys (e.g. `labels`) live ONCE in `shared_context` and are **de-duped** (read by reference), not copied per card. (Unchanged in spirit.)
- **Frame-boundary reality:** the per-TAB `AssetPageFrame` / keyed `widgets{}` envelope / `column_row` shapes are NO LONGER Layer 2's OUTPUT — they survive only as the **DATA-FILL (mapper-input) `data_fill_shape`** a helper targets when filling the DATA tier. Layer 2's output is per-card `{exact_metadata, data_instructions}`; "per-card Layer 2" is therefore the REAL emit unit (not a logical slice of a tab frame), and coupled cards are reconciled through `shared_context`, not by staying frame/composite-scoped. (OLD per-tab-frame / "two dialects as Layer 2 output" model → SUPERSEDED.)

## Confidence + gaps

- **HIGH** confidence on the classification (derived from source mappers/viewModels with cited lines).
- Lower-confidence: the widgets-v2 registry family (thin evidence) and the aggregate-widgets-envelope per-card verdicts (stub evidence, but line refs present).
- Whether the backend opens a separate per-card socket vs multiplexing is an implementation choice, not settled here.
- Not every CMD V2 tab was audited (5 families covered the major ones).
