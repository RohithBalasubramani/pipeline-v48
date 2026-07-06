# V48 — Live Storybook Morph Verification (§B4 sentinel)

> Generated 2026-06-29 by `CMD_V2/sb_verify.mjs` driving the real Storybook (:6008). For each of the 59 EMS card stories it mutates visible-text payload fields one at a time (incl. SVG text) and checks whether the rendered DOM follows. `hits/tested` = how payload-driven (morphed) the card is.
> **Method validated:** the known morph references score high — RTM Main Heatmap 10/12, Total Feeder Consumption 8/9.
> **Caveat:** coarse automated signal. STRONG = confidently payload-driven. weak/zero = needs a manual look (could be genuinely hardcoded chrome, OR a tiny sub-card whose few tested fields aren't visible text).

## Headline

**36 / 59 cards are strongly or moderately payload-driven, across ALL panels — NOT just RTM + HPQ.** The morph has spread well beyond the 2 reference tabs; the static `PAYLOAD_AUDIT_ALL.md` (~7 cards) is stale.

| classification | count |
|---|---|
| STRONG | 14 |
| moderate | 22 |
| weak | 17 |
| zero | 6 |

## Per-card (by panel)

### Equipment Detail/Energy & Power

| card | hits/tested | class |
|---|---|---|
| Input vs Output Energy Card | 10/11 | STRONG |
| Today's Energy Card | 10/12 | STRONG |
| Power Energy Analysis Chart | 9/12 | STRONG |
| Load Anomalies Chart | 7/12 | moderate |
| Load Anomalies · Selected Event Panel | 2/5 | moderate |
| Load Anomalies · Default Legend Rail | 1/12 | weak |
| Load Anomalies · Event Stat Cell | 0/2 | zero |

### Equipment Detail/Power Quality

| card | hits/tested | class |
|---|---|---|
| Power Quality Card | 8/12 | STRONG |
| Spectrum Row — I-THD | 2/4 | moderate |
| Spectrum Row — V-THD | 2/4 | moderate |
| Spectrum Row — H5 | 2/4 | moderate |
| Spectrum Row — H7 | 2/4 | moderate |
| Spectrum X-Axis Rail | 1/2 | moderate |
| Section Divider | 1/2 | moderate |
| Distortion Profile Chart | 4/12 | weak |
| Load Impact Chart | 4/12 | weak |

### Equipment Detail/Real-Time Monitoring

| card | hits/tested | class |
|---|---|---|
| Voltage Monitor · Legend Rail | 4/5 | STRONG |
| Current Monitor · Legend Rail | 4/5 | STRONG |
| Voltage Monitor · Phase Chart | 3/4 | STRONG |
| Current Monitor · Phase Chart | 3/4 | STRONG |
| Power & Energy · Readings Rail | 4/12 | weak |
| Voltage Monitor Panel | 3/12 | weak |
| Current Monitor Panel | 3/12 | weak |
| Power & Energy Panel | 1/12 | weak |
| Power & Energy · Chart | 0/1 | zero |

### Equipment Detail/Voltage & Current

| card | hits/tested | class |
|---|---|---|
| Metric Strip | 3/4 | STRONG |
| History Stats Strip | 3/4 | STRONG |
| Health Summary (value + caption) | 2/3 | STRONG |
| Voltage Health Summary | 7/12 | moderate |
| Current Health Summary | 7/12 | moderate |
| Voltage History | 7/12 | moderate |
| Current History | 6/12 | moderate |
| History Chart | 5/12 | moderate |
| History Legend Rail | 2/12 | weak |
| Deviation Band | 0/3 | zero |
| Phase Rows (rows variant) | 0/4 | zero |
| Phase Rows (bars variant) | 0/4 | zero |

### Panel Overview/Energy & Distribution

| card | hits/tested | class |
|---|---|---|
| KPI Ribbon | 6/7 | STRONG |
| Energy Input & Distribution Card | 5/12 | moderate |
| Energy Flow Diagram Card | 5/12 | moderate |

### Panel Overview/Energy & Power

| card | hits/tested | class |
|---|---|---|
| Energy Trend Card | 5/12 | moderate |
| Cumulative Energy Card | 4/12 | weak |
| Live Power Card | 4/12 | weak |
| Demand Profile Card | 2/12 | weak |

### Panel Overview/Harmonics & PQ

| card | hits/tested | class |
|---|---|---|
| Feeder Pq Table Card | 7/12 | moderate |
| Ai Summary Card | 6/12 | moderate |
| Signature Card | 6/12 | moderate |
| Timeline Card | 3/12 | weak |
| Issue Summary Strip | 2/12 | weak |

### Panel Overview/Real-Time Monitoring

| card | hits/tested | class |
|---|---|---|
| Total Feeder Consumption Card | 8/9 | STRONG |
| Main Heatmap Card | 10/12 | STRONG |
| KPI Tiles | 4/8 | moderate |
| Consumption Trend Card | 2/11 | weak |
| Overview Rail - Full JSON | 2/12 | weak |

### Panel Overview/Voltage & Current

| card | hits/tested | class |
|---|---|---|
| Current Distribution Card | 5/12 | moderate |
| Other Panels Table | 5/12 | moderate |
| Event Timeline Card | 4/12 | weak |
| Events Strip | 1/12 | weak |
| AI Summary Card | 0/12 | zero |
