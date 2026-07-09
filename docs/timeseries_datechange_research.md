# Time-series date/window change on the :5188 host preview — FINAL research

**Question:** when a user changes the date/window on a card on the :5188 host preview, does the card
data change — and how do we make it work end-to-end (historical + live, all granularities), the simplest
correct way?

**All claims below were re-verified against real code at the cited `file:line`. Three pre-coding checks the
critics asked to front-load are already answered here (see "Verified pre-conditions").**

---

## Verdict today

**On an INTERACTIVE date pick on :5188, ZERO cards change their data — for every card kind.** The initial,
PROMPT-derived window DOES work (a "last 7 days" prompt renders 7-day trends), because
`build_response` resolves the preset to a concrete `{start,end}` before the run
(`host/server.py:112-115` → `_window_from_preset` `host/server.py:70-96` → `_run_cards`). But the
per-card date control (`onDateChange` → `/api/frame`) is a silent no-op because of a triple contract
break AND a missing renderer branch:

- **Wrong request shape → HTTP 400.** `host/web/src/api.ts:19-24` posts only `{consumer, date_window}`.
  The server requires `exact_metadata` + `asset_table` (`host/server.py:253,255,258`). `exact_metadata`
  is never posted, and `consumer` carries **no** `asset_table` key (verified: consumer key-union is
  `[backend_strategy,end,endpoint,interval_seconds,is_history,metrics,mfm_id,range,resolver_scope,sample_count,sampling,selection,start,window_seconds]`),
  so the server's `consumer.asset_table` fallback is dead. → 400, swallowed by `CmdCard.tsx:54 .catch(()=>{})`.
- **Wrong response key.** `api.ts:27` reads `body.frame`; the server returns `body.payload`
  (`host/server.py:270`). Even a 200 yields `undefined`.
- **Wrong render source.** `CmdCard.tsx:48,54` stores the result in `frame` state, but the renderer fills
  read `card.payload` (`registry.tsx`: `const payload = forceBlank(card.payload,…)` then
  `FILL[id](guardPayload(payload), frame, …)` — data rides on arg-1 `payload`, the `frame` arg is inert
  now that frames are retired). Swapping `frame` changes nothing on screen.
- **No special-renderer branch.** `/api/frame` calls `run_card` unconditionally (`host/server.py:261`),
  but panel-overview trend cards are `handling_class=panel_aggregate` and render via `run_special`
  (member fan-out). These are **is_history=true today** (verified: cards 15/16/17/20 across live dumps),
  so their date control is enabled — a naive run_card-only fix would silently replace correct
  member-summed data with wrong single-table data.

**After the fix, per card kind:**
- `single_asset_series` / `single_asset_derived` is_history cards (44/46/39/40/51/53/58/59/61-77/79/81 …):
  **reslice** — needs Step 1 (contract) + Step 2 (range→start/end; they emit range-only).
- `panel_aggregate` is_history cards (15/16/17/20): **reslice** — needs Step 1's special dispatch; their
  emitter already carries `start/end` (Step 2 not required for them).
- is_history=false snapshot cards: **never change, by design** — `_date_window_for` returns `None`
  (`exec_cards.py:24-27`), date control already `disabled` (`enrich.py:229`).
- **Narrowing** a pick below the card's AI-authored range is silently re-widened until Step 2b
  (`_honor_range` is widen-only, keyed on the stale `consumer.range`).

---

## Verified pre-conditions (front-loaded, so the implementer need not re-check)

1. **is_history census (blast radius).** Across 45 real response dumps / 204 card instances, **38 card
   instances were is_history=true**, spanning feeder / UPS / DG / transformer / panel dashboards on the
   `energy-power` and `voltage-current` domains. So Steps 1+2 light up a meaningful chunk immediately;
   Step 3 is the lever to widen it, not a prerequisite for the feature to feel real.
2. **Emitter shapes (`host/web/src/cmd/fill/*/date-wiring.ts`).** For the everyday presets
   (today/yesterday/last-7-days/this-month) the emitters send **range-only** (no start/end):
   `feeder-voltage-current` `samplingToWindow`, `feeder-energy-power` `periodToDateWindow`,
   `transformer-tap-rtcc` `chartParamsToDateWindow`, `dg-operations-runtime` `samplingToWindow`. They
   carry `start/end` **only** for `last-month`/`custom`. The **one** always-start/end emitter is
   `panel-overview-voltage-current` `selectionToWindow`. Confirmed against the dumps: every preset-range
   is_history card has `start=None,end=None`; only `custom-range` cards carry dates. → **Step 2 is
   load-bearing, not optional.**
3. **`is_history` lever.** `consumer.is_history = endpoint in HISTORY_ENDPOINTS`
   (`layer2/emit/data/consumer_binding/builder.py:24`); `HISTORY_ENDPOINTS` derives from
   `layer2/emit/data/endpoint_registry.py:8-24` (energy-power + voltage-current only). `endpoint_policy`
   has **no live reader** (only `db/seed_schema_and_endpoints.py`), so **`endpoint_registry.py` is the
   sole lever** — editing it (if real routes exist) flips is_history; no gating code changes.

---

## Root causes (with evidence)

### RC1 — BLOCKER: `/api/frame` is contract-broken AND run_card-only (no special dispatch)
Triple break (400 / `body.frame` vs `body.payload` / `frame` state vs `card.payload` render) **plus** no
`run_special` branch for `panel_aggregate` cards that are is_history=true today.
- Evidence: `api.ts:19-27`; `server.py:253,255,258,261,270`; `CmdCard.tsx:48,54`; `registry.tsx` FILL tier;
  consumer has no `asset_table` (key-union above); `exec_cards.py:31` `_SPECIAL_KINDS` includes
  `panel_aggregate`, `:90-128` `_fill` dispatches special-vs-run_card, but `/api/frame` does not; live
  dumps show cards 15/16/17/20 `handling_class=panel_aggregate` AND is_history=true.
- Fix: route `/api/frame` through a shared `fill_one_card(...)` extracted from `_fill` (dispatches
  special-vs-run_card, threads harvested `_default_payload` + `shape_ref`); serve a compact `refetch`
  bundle on each card; FE posts `exact_metadata=card.payload` + `data_instructions` + `refetch` and reads
  `body.payload`; `CmdCard` swaps `card.payload` (a `payloadOverride`), not `frame`.

### RC2 — BLOCKER: preset ranges are never resolved to start/end at the seam
`_date_window_for` (`exec_cards.py:21-28`) passes the dict through unchanged; a range-only
`{range:'today',start:None,end:None}` reaches `_window_of` (`window_policy.py:82-95`) as `(None,None)`,
and `_honor_range` short-circuits on `not end` (`:56`) → run_card reads full/latest. Initial run works
only because `_window_from_preset` (`server.py:88-94`) pre-resolves start/end.
- Evidence: `exec_cards.py:24-28`; `window_policy.py:56,82-95`; emitters send range-only (pre-condition 2).
- Fix: in `_date_window_for` (shared by initial run and `/api/frame`), when `range` is present but
  start/end are not, resolve via `config.windows.site_tz()` + `window_policy._range_start` (end=now),
  keeping the FE sampling.

### RC2b — BLOCKER: a NARROWER pick is silently re-widened
`_window_of` keys `_honor_range` off the **L2-authored** `consumer.range` (`window_policy.py:94`), not the
FE pick. `_honor_range` is widen-only: when the pick's `start` is later than the declared-range start
(`cur <= req` false), it **replaces** the pick start with the range start (`:72-79`). So picking "Today"
on a card whose authored range is "this-month" shows the month. (This bites the run_card path;
`panel_aggregate` bypasses it because `panel_aggregate.py:196` calls `_window_of(ctx, None)` →
`consumer.range` is None → no re-widen.)
- Evidence: `window_policy.py:49-79,94`; `panel_aggregate.py:196`.
- Fix: at the `/api/frame` seam, make the pick authoritative — set
  `data_instructions.consumer["range"] = date_window["range"]` before dispatch. `custom-range` →
  `_range_start` returns None → `_honor_range` no-ops → FE start/end used verbatim.

### RC3 — MAJOR (partly by design): whole domains have no history endpoint
`HISTORY_ENDPOINTS` is derived only from `energy-power` + `voltage-current`
(`endpoint_registry.py:11-14`, `builder.py:24`). `overview` / `real-time-monitoring` /
`energy-distribution` / `power-quality` expose zero history variants → their trend cards can never be
is_history → honest `date_control:'disabled'`.
- Fix: DB/registry FIRST (if ems_backend really serves history routes for those domains, append to
  `endpoint_registry.py`), then PROMPT (`user_message.py` `_ep_hint` + data_instructions hard-rule:
  temporal intent MUST pick the history variant when one exists). No new gating code (`endpoint_policy`
  is dead).

### RC4 — MAJOR: `yesterday` is unresolved
Four emitters send `{range:'yesterday'}` (range-only), but `_range_start` (`window_policy.py:12-46`) has
no `yesterday` branch → returns None → window untouched → reads latest.
- Fix: in the RC2 resolver special-case `yesterday`: `end = _site_calendar_start(now,'day')`,
  `start = end - 1d` (anchors at midnight-today so it does not leak into today's partial day). `last-month`
  already arrives as `custom-range` with start/end from the FE.

### RC5 — MAJOR (requirement-gated): no sub-hour granularity
`_SAMPLING` (`neuract.py:263`) = `{hourly:hour, 2hour:hour, shift:hour, day:day, week:week, month:month}`
— no minute/15-min key, and `2hour`/`shift` collapse to `hour` (so those picker options do not actually
change bucket size). A 30-min "live" window buckets to 0-1 points. 24h/7d/30d/month are real.
- Fix (only if intraday minutes are required): add `'minute':'minute'` to `_SAMPLING`; map minute/'15 min'
  presets to it; pair with a slot-budget coarsen so long windows do not over-refine.

### RC6 — MAJOR (mode-gated): no live-rolling window
`end` is frozen at request time; there is no polling / SSE / WebSocket in `host/web/src`. "live" is a
one-shot 30-min lookback.
- Fix (FE-only, staged): a client `setInterval` for a "live" range re-posts the SAME `/api/frame` with
  `start=now-width,end=now`. Backend unchanged once RC1 lands.

### RC7 — MINOR: degenerate span not guarded at runtime
`ensure_nonzero_span` runs only at emit time (`config/windows.py:54`); a same-day custom pick
(`start==end`) reaches `bucketed()` empty.
- Fix: call `ensure_nonzero_span(start,end)` inside `_window_of` before returning (`window_policy.py:95`).

### RC8 — MINOR: picker `sampling` ignored for a plain series
Plain series read `field.sampling`, not the picker's `window.sampling` (`series_fill.py:38,132`); only
indexed families auto-fit. So the resolution picker cannot change bucket size for a plain trend.
- Fix (optional): prefer `ctx.window.sampling` over `field.sampling` in the shared series readers.

### RC9 — MINOR (mostly by design, refined): raw-scalar tiles read latest, window-ignored
`fill.py:204-206` reads a plain `raw` scalar via `latest()` regardless of window — an "as-of latest"
value. **Windowed leaves already reslice correctly**: series/bucketed (`fill.py:183`), derived over the
ctx window (`:160`), and cumulative energy registers as a windowed delta (`:200-203`). So the only
window-blind leaf on a history card is a plain-raw scalar — usually a "current value" tile, which is
acceptable, but can look inconsistent next to a resliced series.
- Fix: none needed for correctness; if windowed as-of scalars are wanted, add optional (start,end) to
  `neuract.latest`, gated by is_history. **Tests must assert value-level correctness on the WINDOWED
  leaves, not on as-of-latest raw scalars.**

---

## Ordered implementation steps

> **MVP = Step 1 + Step 2 together.** Step 1 alone changes nothing for the range-only majority (their
> picks arrive with start/end None). Step 1 also MUST carry the special-renderer dispatch because
> `panel_aggregate` cards are is_history=true today. Step 3 is the widen-the-coverage lever. Step 4 is a
> cheap guard. Steps 5-7 are gated/optional.

### Step 1 — Interactive re-fetch through a shared per-card fill seam (RC1 + special dispatch + default)
Files: `host/exec_cards.py:90-128`; `host/enrich.py:201-236` + `host/assemble.py:25-40`;
`host/server.py:251-273`; `host/web/src/api.ts:19-28`; `host/web/src/components/CmdCard.tsx:48-63`;
`host/web/src/cmd/registry.tsx` (FILL/COMPONENTS tiers).
- 1a. Extract `fill_one_card(*, cid, render_card_id, handling_class, exact_metadata, data_instructions,
  asset_table, db_link, window, requested_window, default_payload, mfm_id=None, asset_name=None,
  member_scope="outgoing", page_key=None, metric=None, intent=None)` from the `_fill` closure — dispatch
  `run_special` for `_SPECIAL_KINDS` else `run_card`, threading `default_payload` + `shape_ref=
  _raw_default_payload(render_card_id)`. `_run_cards._fill` becomes a thin caller (byte-identical behavior).
- 1b. `enrich.py`: serve a compact `refetch` bundle per card:
  `{render_card_id, asset_table, asset_name, member_scope, _default_payload}` (asset_table + member_scope
  threaded from `assemble_cards`' `asset`; harvested `_default_payload` from the L2 output — needed so the
  panel path is chrome-safe, NOT the raw default which over-blanks order/layout `exec_cards.py:116-118`).
- 1c. `server.py /api/frame`: read `refetch`; `handling_class` via `_special_handling_map([rid])`;
  `mfm_id` via `_registry_mfm_id({"table":asset_table,"name":asset_name})` (the lt_mfm id member
  resolution needs — NOT `consumer.mfm_id`, a different id-space); resolve `window` via `_date_window_for`
  (Step 2); apply the narrow-fix (Step 2b); call `fill_one_card(...)`; return `{"payload": …}`.
- 1d. `api.ts fetchCardFrame(card, dw)`: POST
  `{exact_metadata:card.payload, data_instructions:card.data_instructions, refetch:card.refetch, date_window:dw}`
  and `return body.payload`.
- 1e. `CmdCard`: `payloadOverride` state; reset on card change (`useEffect`); `onDateChange` sets it from
  the returned payload; render `renderCmd({...card, payload: payloadOverride ?? card.payload}, frame, onDateChange, pageFrame)`.
- Keeps simple: ONE shared seam collapses the shape fix, the special dispatch, and the default-payload
  divergence; zero fills touched (all read `card.payload`); no neuract change.
- Verify on :5188 (after Step 2): a `single_asset` is_history card (e.g. 44/79) AND a `panel_aggregate`
  is_history card (15/16/17/20) each: change window → `/api/frame` 200 (not 400), series reslices, no
  console error; the panel card's member-summed values stay plausible (not blank/single-table).

### Step 2 — Resolve range→start/end (+yesterday) and make the pick authoritative (RC2 + RC4 + RC2b)
Files: `host/exec_cards.py:21-28`; `ems_exec/executor/window_policy.py:12-46`; `host/server.py` /api/frame.
- 2a. `_date_window_for`: after the is_history gate, if `range` is set but start/end are not, resolve
  `end=now(site_tz)`, `start=_range_start(range, now)`, special-case `yesterday`
  (`end=_site_calendar_start(now,'day')`, `start=end-1d`), keep FE sampling. Shared by initial run and
  `/api/frame`.
- 2b. Narrow-fix at `/api/frame`: before dispatch, set
  `data_instructions.consumer["range"] = date_window["range"]` so `_honor_range` anchors to the pick
  (`req == resolved start` → no re-widen; `custom-range` → None → FE start/end verbatim).
- Keeps simple: one resolver reused by both date paths; reuses `_range_start`'s existing vocabulary;
  the narrow-fix is one line on the object `_window_of` already reads.
- Verify on :5188: a range-only feeder/DG/transformer is_history card — Today → Week → Month → Yesterday
  each yields a different bucket count AND a first/last ts inside the picked window; picking a range
  NARROWER than the card's authored range (e.g. Today on card 39) moves the first bucket FORWARD (not
  re-widened); the initial "last 7 days" prompt still reslices (regression).

### Step 3 — Widen which cards are date-navigable (RC3) — DB/registry then prompt, no gating code
Files: `layer2/emit/data/endpoint_registry.py:11-14`; `layer2/emit/user_message.py` + data_instructions.md.
- 3a. Confirm ems_backend serves date-capable PQ / energy-distribution history routes; if yes, append
  them to `endpoint_registry.py` (is_history + AI hint follow automatically). If none, honest `disabled`
  is correct.
- 3b. Prompt hard-rule: temporal intent MUST pick the history variant when one exists.
- Keeps simple: `endpoint_registry.py` is the single is_history fact; no new branches.
- Verify on :5188: a temporal energy/voltage prompt → served is_history:true + date_control:'enabled',
  Steps 1+2 reslice it; PQ/energy-distribution honestly disabled until a real route is registered.

### Step 4 — Span-guard the runtime window (RC7)
Files: `ems_exec/executor/window_policy.py:95`; `config/windows.py:54`.
- Call `ensure_nonzero_span(start,end)` inside `_window_of` before returning (one line + import).
- Verify on :5188: a same-day custom range renders a non-empty trend, not honest-blank.

### Step 5 — Sub-hour granularity (RC5) — ONLY if intraday minutes are required
Files: `ems_exec/data/neuract.py:263`; `host/server.py:92-93`.
- Add `'minute':'minute'` to `_SAMPLING`; map the minute/'15 min' presets to it; pair with a slot-budget
  coarsen. hour/day/week/month untouched.
- Verify on :5188: a 30-min window renders multiple sub-hour buckets, not one flat point.

### Step 6 — Live-rolling advancing window (RC6) — ONLY if desired
Files: `host/web/src/components/CmdCard.tsx:48-63`.
- Client `setInterval` for a "live" range re-posts the SAME `/api/frame` with `start=now-width,end=now`;
  any non-live range stops it. Backend unchanged (reuses Step 1's path).
- Verify on :5188: a live card advances its right edge each tick without a manual pick.

### Step 7 — Picker sampling overrides field default for plain series (RC8) — optional polish
Files: `ems_exec/executor/series_fill.py:38,132`.
- Prefer `ctx.window.sampling` over `field.sampling` when present.
- Verify on :5188: changing a plain trend's resolution changes its bucket count.

---

## Granularity plan

Four granularities → neuract `date_trunc` via `_SAMPLING` (`neuract.py:263`):
- **INTRADAY (hour):** hourly/2hour/shift → `hour`. Works. Caveat: 2hour & shift both fold to hour, so
  those picker options do not change bucket size (cosmetic; only a true `minute` key would).
- **INTRADAY (sub-hour, minute/15-min):** no token + no `minute` key → folds to hour; a 30-min window =
  0-1 buckets. BROKEN → Step 5 only if required.
- **DAILY:** `day` → `date_trunc('day')`. Works.
- **MONTHLY:** `week`/`month` → works at SQL; note the panel emitter maps "monthly" to `week` (no host
  `month` token), so long spans render weekly buckets.
- **CUSTOM (arbitrary start/end):** `WHERE ts BETWEEN … GROUP BY date_trunc(sampling)` works, but needs
  Step 2 (range-only presets carry no start/end) and Step 4 (same-day empty buckets).

Bucket size for a PLAIN series is chosen from the FIELD's `sampling` (`series_fill.py:38`), not the
picker's `window.sampling`, until Step 7; indexed sparkline families already auto-fit
(`indexed_families.py` `_choose_granularity`). Windowed leaves that DO reslice: series/bucketed
(`fill.py:183`), derived over the ctx window (`:160`), energy-register windowed delta (`:200-203`).

## Live-mode plan

- **HISTORICAL (default, one-shot):** served correctly once RC1+RC2 land — window → run_card/run_special
  → `_window_of` → `bucketed()` `WHERE ts BETWEEN start AND end GROUP BY date_trunc(gran)`
  (`neuract.py:266-288`). Toggle = the card's OWN CMD_V2 date control (per-card infra; there is NO page
  DateBar and none is added).
- **LIVE-ROLLING (advancing):** NOT built — `end` frozen at request time; no polling/SSE/WebSocket. Add
  Step 6: a client `setInterval` re-posts the SAME `/api/frame` with a rolling `end`. A live tick is just
  another windowed `/api/frame`; the backend is identical to historical once Step 1 lands. Mode toggle =
  the range value ("live" → interval on; calendar/custom → one-shot).

---

## Test plan

1. **RC1 + special dispatch:** a `single_asset` is_history card (44/79) AND a `panel_aggregate` is_history
   card (15/16/17/20) each → `/api/frame` 200 (not 400), series reslices, no console error; the panel card
   stays member-summed (not blank / single-table).
2. **RC2 + RC4 (range-only presets):** a feeder/DG/transformer is_history card → Today → Week → Month →
   Yesterday each different bucket count AND first/last ts inside the picked window.
3. **RC2b (narrowing, VALUE-level):** on a card whose authored range is wider (e.g. card 39 `this-month`),
   pick Today → the first bucket ts moves FORWARD (not re-widened to month start) — a narrow, not just a
   widen.
4. **Value-level re-slice correctness:** after a window change, the series' first AND last ts fall inside
   the new window, and any WINDOWED scalar (energy-register delta / derived mean/peak) changes; explicitly
   exclude plain-raw "as-of latest" tiles (RC9) so a stale scalar is not mistaken for a pass.
5. **Negative (snapshot):** an is_history=false card (power-quality-summary) → date control disabled +
   byte-identical across 24h vs 30d.
6. **Regression:** the initial "last 7 days" prompt still reslices history cards on `/api/run`.
7. **Multi-asset compare:** each compare-card's `refetch` bundle carries its OWN lane `asset_table`
   (threaded per lane by `multi_asset.build_response_multi` → `assemble_cards`), so a per-card date change
   re-slices the RIGHT lane's meter.
8. **RC7:** a same-day custom range renders a non-empty trend.
9. **Backend unit** on `_date_window_for`: concrete start/end for a range-only dict when is_history=true
   (incl. yesterday), None when is_history=false.
10. **(If Step 5)** a 30-min window renders multiple sub-hour buckets. **(If Step 6)** a live card advances
   its right edge each tick.

---

## Risks

- Re-running from the FILLED `card.payload` (not the raw skeleton): series/derived/register leaves are
  re-read; chrome kept. Matches the server's existing `req.payload` fallback and the live probe. Mitigate a
  stale non-re-read leaf by threading the HARVESTED `_default_payload` in the `refetch` bundle (NOT the raw
  default, which over-blanks panel order/layout — `exec_cards.py:116-118`).
- `panel_aggregate` at `/api/frame` needs the lt_mfm `mfm_id` (member resolution) — derive it server-side
  from `asset_table` via `_registry_mfm_id`, NOT `consumer.mfm_id` (different id-space, `exec_cards.py:49-64`).
  `member_scope` must be served on the card (default `outgoing`) or an incomer panel re-fetches the wrong
  side.
- The narrow-fix mutates `data_instructions.consumer.range` on the `/api/frame` request object only (the
  response is just the payload) — no served-card side effect. Do NOT extend the mutation to the initial run
  without deciding prompt-vs-L2-range precedence (see residual unknowns).
- `yesterday` must anchor `end` at midnight-today, not `now`, or it leaks into today's partial day.
- RC3 depends on REAL ems_backend routes — do NOT invent history endpoints; honest `disabled` is correct if
  none exist.
- Sub-hour (Step 5) multiplies bucket counts — pair with a slot-budget/auto-coarsen.
- Live-rolling (Step 6) adds recurring load per live card — cap cadence + scope to visible "live" cards.

## Residual unknowns

- Does ems_backend expose date-capable history routes for power-quality / energy-distribution? If yes,
  register in `endpoint_registry.py:11-14`; if no, `date_control:'disabled'` is correct (RC3).
- Is sub-hour (minute/15-min) intraday resolution a real requirement, or is hour-resolution acceptable?
  Decides Step 5.
- Is an advancing live-rolling window desired, or is the one-shot "live 30-min lookback" sufficient?
  Decides Step 6.
- Should the initial PROMPT window also be authoritative over an AI-authored `consumer.range` (same
  narrow-fix at `build_response`)? Currently the initial run honors the L2 range; extending 2b there would
  make "show me today" always render today even when the card authored a week. Out of scope for the
  interactive fix; flagged for a follow-up decision.
