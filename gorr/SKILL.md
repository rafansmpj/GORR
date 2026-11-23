---
name: "gorr"
metadata:
  version: "1.2.1"
description: "GORR (Game Over Risk Reduction) — 30-day plan to cut the Tenable One Exposure Score in N cumulative phases (2–6, default 4: 10-20-30-40%) of Quick Wins ranked by score drop per effort, with Crown Jewel/chokepoint bonuses, keyed on real plugin IDs. Targets the official score from an Exposure View JSON (uploaded or freshly pulled) and models each module's pull on Global, Identity Exposure IoEs included. Outputs an HTML dashboard (EN/PT) with gauge, phase cards, peer benchmark, board summary, per-asset, per-plugin, per-owner and carry-over views, plus a CSV/JSON ticket tracker (owner from Tenable tag) re-imported on later runs to verify fixes and flag overdue items with a recovery plan. Read-only. ALWAYS use when the user asks for GORR, quick wins, a phased or 30-day risk reduction plan, a remediation roadmap, how to reduce their Exposure Score, which vulnerabilities to close first, owner or ticket tracking, a follow-up, missed or overdue items, or uploads a gorr_tracker or gorr_exposure_view file."
---

# Skill: GORR (Game Over Risk Reduction) — Tenable Quick Wins 30-Day Remediation Cycle

Generates an interactive executive dashboard showing which vulnerabilities to close in order to reduce
the Exposure Score across **N cumulative phases delivered within 30 days of the run** (N is chosen at the
start of every run, 2–6; default 4 = 10% → 20% → 30% → 40%), ranked by maximum impact with minimum effort — and a ticket tracker that lets the team record owner,
ticket number, assignee and status, then feed it back into the next run to see what was really fixed.
Audience: C-Level, Board, CISO, VP of IT, and the remediation teams executing the plan.

The skill is **read-only toward Tenable**: it never creates tickets or changes anything in the tenant.
Ticket data lives in the CSV/JSON tracker the user maintains.

**Owner = Tenable tag.** The accountable owner of every asset (and therefore of every plugin × asset item on it)
is the value of that asset's tag in the **owner tag category** in Tenable (e.g. `Owner:Infra SP`,
`Business Unit:Finance`). Tenable is the source of truth: the owner is re-read from the tags on every run, so
re-tagging an asset in Tenable re-assigns its items on the next run. The `owner` column in the tracker is only
honored for assets that have no owner tag. Details in "Owner from Tenable tags" below and
`references/tracker-schema.md` §10.

---

## Start of every run — ask two questions first

Every execution (baseline or tracking) starts by checking `/mnt/user-data/uploads/` and then asking the user
**two questions in one AskUserQuestion call**, before any data collection. Skip a question only when the
user's message already answers it (e.g. "run GORR with 5 phases, here is the JSON"). In an unattended run
(scheduled, nobody to answer), don't ask: use the newest uploaded score file if there is one, otherwise the
computed score, keep the cycle's phase count (4 on a baseline), and say at the top of the reply what was assumed.

**Q1 — Risk Score file (Exposure View JSON).** Say which file is present, if any: the newest
`gorr_exposure_view_YYYYMMDD_HHMMSS.json` (or `gorr_exposure_view.json` / `exposure_view_*.json`), with its
`pulled_at`, flagged as stale if older than 2 days. Options:
- **Use the uploaded file** (only when one is present) → S0 source ladder step 1.
- **I'll upload a file** → stop and wait for the upload; don't collect data until it arrives.
- **Generate a new file** → a fresh pull: run Appendix A on the user's computer if `device_bash` and a
  connected folder are available (S0 step 2), otherwise deliver Appendix A as `gorr_exposure_view_pull.py`
  and wait for the new timestamped file (S0 step 3).
- **Continue without it** → computed score (S1); a typed Exposure View value also lands here (S0 step 4).

**Q2 — Number of phases.**
- *Baseline run (no tracker):* "How many phases should the 30-day plan have?" Options: 3 (−30%),
  **4 (−40%, recommended)**, 5 (−50%), 6 (−60%). The default is 10% per phase. Free text such as
  "5 phases to 40%" sets a total instead (8 / 16 / 24 / 32 / 40%). Allowed range: 2–6 phases.
- *Tracking run:* read the phase count from the tracker (`cycle.phase_count`; older trackers without it have
  `len(cycle.phase_due_dates)` = 4) and show the current plan in the question — e.g. "This cycle uses
  **4 phases** (F1 −10% due 26 Nov · F2 −20% due 3 Dec · F3 −30% due 10 Dec · F4 −40% due 19 Dec). Keep it?"
  Options: **Keep N phases (recommended)** plus two or three other counts. If the user changes it, re-phase
  the open cycle (section 3, "Changing the phase count mid-cycle") before running the tracker.
- *Tracking run + new cycle:* the closing cycle keeps its count; ask Q2 for the next cycle as on a baseline,
  with the previous count as the recommended option.

Record the answers in `current.json` → `run.phase_count`, `run.phase_targets_pct` and
`run.score_source_choice`, and state them in the reply, in the dashboard (Section A2) and in Section G.

---

## Run modes — decide this first

Look at the conversation and `/mnt/user-data/uploads/` before collecting any data:

| Situation | Mode | What happens |
|-----------|------|--------------|
| No tracker file uploaded | **Baseline run** | Build the N-phase plan (Q2), start a new 30-day cycle, emit dashboard + empty tracker (CSV + JSON) for the team to fill |
| User uploaded `gorr_tracker.json` / `.csv` (or a legacy `gore_tracker.*` from before the rename) (or any CSV with `item_key` / `plugin_id` + `asset_id` + ticket columns) | **Tracking run** | Keep the cycle's phases locked, re-check every tracked item in Tenable, merge the user's ticket data, render fixed / still open / new / reopened / overdue |
| Tracking run after any phase due date | **+ Carry-over check** | Items of past-due phases that are not fixed in Tenable **or** whose ticket is not closed are flagged, their score impact on every phase target is computed and a recovery plan is proposed (see references/carryover.md) |
| Tracking run on or after the cycle's `next_run_date` | **Tracking run + new cycle** | Render the comparison for the closing cycle, then plan the next cycle (phase count from Q2) with carried-over items (see references/tracker-schema.md §6) |

If the user mentions a previous run or tracking but no file is attached, ask them to upload the tracker
(JSON preferred — it keeps the full score history; CSV works too) rather than silently doing a baseline run.

**Every mode also checks for the official Exposure Score** (Scoring model S0), driven by the Q1 answer: look
for an uploaded `gorr_exposure_view_YYYYMMDD_HHMMSS.json` (newest timestamp wins; `gorr_exposure_view.json` and
`exposure_view_*.json` also count) before collecting data. The run waits only when the user chose "I'll upload a
file"; otherwise follow the S0 source ladder.

All tracker logic is deterministic and lives in `scripts/tracker.py`. **Read `references/tracker-schema.md`
before a tracking run or before building the Tickets tab** — it defines the input file, columns, status
vocabulary, merge rules and the HTML import/export contract. **On tracking runs also read
`references/carryover.md`** — it defines the carry-over classification, the impact-on-target model, the
recovery plan fields and the Carry-over tab.

---

## Core Concept: The Quick Win Algorithm

A "Quick Win" is a remediation action that maximizes the ratio:

```
Quick Win Score = (Exposure Score points the action removes) / relative_effort
                  × crown_jewel_bonus × chokepoint_bonus
```

The points an action removes are modeled the way Tenable One builds its own score (see **Scoring model**
below): VPR-band severity drives each asset's AES, and the organization score is the average AES. VPR and
breadth still matter, but only through that model, never as a separate weight.

| Weight | Factor | How to measure |
|--------|--------|---------------|
| 1st | High VPR (exploitability) | VPR ≥ 9.0 = maximum weight; decreasing scale down to VPR 4.0 |
| 2nd | Breadth (assets affected) | Vulns affecting N assets = multiplier N |
| 3rd | Low effort (single patch) | Single plugin/patch for multiple assets = effort 1; individual remediation = effort N |
| 4th | Crown Jewels impacted | +30% weight if vuln affects a Crown Jewel |
| 5th | Attack path chokepoint | +20% if the asset is an attack path chokepoint |

The bonuses change the order of the plan only. They never increase an action's projected score drop.

---

## Scoring model: matching the Tenable One Exposure Score

**How Tenable computes it** (Tenable One "Scoring Explained"): every weakness has a VPR (0.1–10). Per asset,
Tenable computes a *Vulnerability Density* from the number of weaknesses and their VPR-based severity
(critical 9–10, high 7–8.9, medium 4–6.9, low 0.1–3.9; distinct CVEs are counted, informational plugins are excluded,
and critical/high weigh much more than medium/low). The density is combined with the ACR (1–10) and scaled
to the **AES** (0–1000). The **CES / Exposure Score** (0–1000) is the **average AES** of the licensed assets in
scope: per exposure class, or the Global CES as the average of Global AES. Assets not seen in 90 days are
excluded. Tenable does not publish the exact weights, so GORR reproduces the structure and calibrates it
against the tenant.

Three consequences drive the whole plan:
1. A fix lowers the score only through the AES of the assets it sits on, and the organization score moves by
   **ΔAES ÷ N**, where N is the number of assets in scope (often tens of thousands). A host dropping from 950
   to 0 moves a 30,000-asset CES by about 0.03 points.
2. AES is not linear in the number of findings. A host with 40 criticals stays high after 5 are fixed, and it
   only falls sharply once its severe weaknesses are gone. Clearing a host matters more than nibbling at many.
3. The VPR **band** is enough. Tenable's density uses band severity, so the MCP's band-only VPR is not a
   handicap for scoring.

### S0. Official Exposure Score from the Exposure View API (every run, before S1)
The Tenable MCP has no tool for the tenant-level Exposure Score, so the official number comes from the
Tenable One **Exposure View API** (beta), called outside the MCP:
- `GET https://cloud.tenable.com/api/v1/t1/exposure-view/cards` — list cards (`is_global_card=true|false`,
  `text_query`, `limit` ≤ 25, `offset`, `sorting_order`)
- `GET https://cloud.tenable.com/api/v1/t1/exposure-view/cards/{card_id}` — card details: score, trend
  (default 30 days), SLA efficiency; optional timeframe params (pyTenable names: `trend_timeframe`,
  `sla_efficiency_timeframe`, `include_trend_events`)
- Auth `X-ApiKeys: accessKey=…;secretKey=…`; needs Basic role or `EXPOSURE_MANAGEMENT.ANALYTICS.EXPOSURE_VIEW.READ`.
- The response schema is beta. The collector (Appendix A) normalizes it and keeps the raw responses. The
  field paths below were confirmed on a live tenant (Nov 2026); if a path is missing, fall back to
  `score_path` / `score_like_fields` and say which path you used.

**Source ladder — take the first that works, and never ask for API keys in chat:**
1. **Uploaded file.** `gorr_exposure_view_YYYYMMDD_HHMMSS.json` (Appendix A output; several uploads → the
   newest timestamp), `gorr_exposure_view.json` or a raw `exposure_view_*.json` in `/mnt/user-data/uploads/` →
   parse it (below). Name the file and its `pulled_at` in Section G.
2. **User's computer.** If a working `mcp__remote-devices__device_bash` tool is present, write Appendix A to a
   connected folder and run it there. It reads keys from `TIO_ACCESS_KEY`/`TIO_SECRET_KEY` or a local
   `tenable_keys.txt`; if neither exists, tell the user to create the keys file themselves (never type keys
   into the chat). The collector writes `gorr_exposure_view_<timestamp>.json` next to itself; stage that file
   back to the workspace.
3. **Hand over the collector.** Otherwise save Appendix A as `gorr_exposure_view_pull.py`, deliver it, and tell
   the user: "run it with `--all`, then upload the `gorr_exposure_view_<timestamp>.json` it writes next to the
   script — or just tell me the score Exposure View shows".
   Continue the run with the computed score meanwhile and say the official value is pending.
4. **Typed value.** A score the user types is `CES_reported` with `source = Exposure View (typed)`.
5. **None.** Computed score only (S1), labelled as computed.
The workspace shell usually cannot reach cloud.tenable.com — do not try to call the API from there.

**Parsing the file — use ALL cards, not just one.** Every run reads the Global card and every module card.
Confirmed paths inside `raw.details[card_id]`:

| What | Path |
|------|------|
| Card scope (module) | `exposures[]` — one class (VM, CLOUD, IDENTITY, WAS, OT, CODE, AI) = module card; several = Global |
| Card score | `ces_scores.total.score` / `.grade` (= normalized `score`, `score_path`) |
| Every module score inside Global | Global card `ces_scores.per_exposure[]` → `{exposure_class, ces_score.score, .grade}`; `ALL` = Global score |
| Score per tag | `ces_scores.per_tag[]` → `tag.name`, `tag.category_name`, `tag.asset_count`, `ces_score.score` |
| Daily trend (~32 days) | `ces_trend[]` → `{date, ces_score}`; per class: `exposure_classes_details.<CLASS>.score_trend_metric.ces_trend[]` |
| Tenant score target | `exposure_classes_details.<CLASS>.score_trend_metric.target_score` (Global `ALL` target is the customer's own goal) |
| Industry / population benchmark | `exposure_classes_details.<CLASS>.score_benchmark.industry_benchmark.ces_score.score` and `.population_benchmark.score` |
| Asset risk mix | `exposure_classes_details.<CLASS>.asset_risk_breakdown` → `{critical, high, medium_low}` fractions of assets |
| SLA | `exposure_classes_details.<CLASS>.sla_efficiency[]`, `sla_breakdown` |
| Freshness | `last_data_update_date` |

- **Baselines.** `CES_reported` (Global) = Global card `ces_scores.total.score`. Module baselines
  `S_c` = Global card `ces_scores.per_exposure[class]` (same snapshot as Global); cross-check with each
  module card's `ces_scores.total.score` and flag a difference > 2 pts.
- **Do not use** `sla_breakdown.exposure_category_breakdown[].contribution_percentage` as a score weight: it
  is the module's share of SLA risks, not of the score (on the reference tenant it gave Cloud 75% while Cloud
  holds ~3% of the Global score).
- **Benchmarks** come from the Global card's `exposure_classes_details` (one industry_id for all classes;
  module cards can carry a different industry_id). Section E uses `ALL`; the module panel uses each class.
  Never infer percentiles — the API gives industry and population averages only.
- **Trend events.** Read the Global trend for jumps and explain them with the module trends of the same day
  (e.g. Global +12 on the day Cloud started scoring 0 → 546). Put this in Section G.
- Keep everything in `exposure_cards` (one entry per card: id, name, class, score, grade, trend, benchmark,
  target, risk mix). Stale check: if `pulled_at` or `last_data_update_date` is more than 2 days before the
  run date, say so and prefer a fresh pull.

**Store it** in `current.json` → `meta.score_model.official` = `{source, card_id, card_name, score_path,
score, pulled_at, benchmark{…}, official_trend[…], exposure_cards[…]}` and set `meta.exposure_score =
CES_reported` so `scripts/tracker.py` records the official value in `TRACKER.runs` and the cycle baseline.
Tracking runs pull the **same card_id** again; if it no longer exists, match by name and say so.

### S0b. Module → Global model (every run with an API file)
The Global card is an average of asset scores across all modules, so each module moves Global in
proportion to how many of the Global assets it holds.

1. **Asset counts.** `N_G` = `tenable_one_search_assets(limit=1)` total for `is_licensed = true` + `aes exists`;
   `N_c` = same filter + `exposure_classes = <class>`, one call per module card (7 calls, one batch).
2. **Share and calibration.** `share_c = N_c ÷ N_G`. `Global_raw = Σ (N_c × S_c) ÷ N_G`.
   `k_G = CES_reported ÷ Global_raw` (pooled Global AES, multi-class assets and the 90-day window make
   Global_raw differ from the official value; reference tenant: 313 vs 255, k_G = 0.815). If |k_G − 1| > 0.3,
   say the population differs and show k_G in Section G.
3. **Lever per module.** `lever_c = k_G × share_c` = Global points per module point.
   `max_c = lever_c × S_c` = how much Global would drop if that module reached 0. The `max_c` values sum to
   `CES_reported` — check it. This is the feasibility ceiling per module.
4. **Module projection.** For each plan item, look up the asset's `exposure_classes` (filter
   `tenable_one_search_assets` by `asset_id` list + class). `ΔModule_c = Σ ΔAES(plan items on class-c assets)
   ÷ N_c` (Global AES is the proxy for module AES; credit a multi-class asset to every class it belongs to).
5. **Global impact.** `ΔGlobal = Σ_c lever_c × ΔModule_c`, counting each multi-class asset once
   (equivalently `k_G × Σ ΔAES ÷ N_G`). This replaces `ΔCES_action` in S3 when an API file exists.
6. **Back-test.** Pick a day in the trend where one module jumped; predicted Global change =
   `lever_c × module jump` (sum over modules that moved that day). Show predicted vs. actual in Section G —
   on the reference tenant, 05 Nov: predicted +10.5, actual +12.
7. **Targeting.** Default: phase targets on **Global** (−10/20/30/40% of `CES_reported`), and every phase
   shows the module scores that get it there. If the user says "target the VM card" (or any module), the
   phase targets are on that module's score and each phase shows the resulting Global drop. Either way, if
   the modules with retrieved findings cannot reach a target (`Σ max_c` of those modules < target drop), say
   which module has to carry the plan (on the reference tenant, VM alone can move Global by at most 7.6 pts =
   3%, while Identity can move it 169 pts) and offer to collect that module's findings.

Store `N_G`, `N_c`, `share_c`, `k_G`, `lever_c`, `max_c` and the back-test in `meta.score_model.modules`.
Tracking runs reuse `N_c` only if they changed < 5%; otherwise recompute and say so.

### S0c. Identity module — collection and model (whenever Identity carries the Global score)
When `max_IDENTITY` is the largest lever (typical when Identity Exposure is licensed), collect identity
findings before VM; a VM-only plan cannot reach the targets. Proven on a 34k-asset tenant (Nov 2026):

1. **Find the IoEs.** `tenable_one_search_findings` with `product = TENABLE:IE`, `state = ACTIVE`,
   `finding_severity ∈ {CRITICAL, HIGH}`. The search lists one row per finding (tens of thousands), so
   discover the distinct IoE names by adding `finding_name != <name>` filters for every name already seen and
   re-querying (`limit` 40–60, `sort = finding_name:asc|desc`). Five or six rounds usually cover all names.
   String `<`/`>` operators on `finding_name` are ignored — don't use them.
2. **Count each IoE** with one `limit=1` call per `finding_name` (send them in one batch) and read `total`.
3. **Population buckets, not per-asset lists.** `tenable_one_search_assets(limit=1)` with the S1 filter +
   `exposure_classes = IDENTITY` and: `critical_weakness_count = 0 / 1 / >= 2`, `high_weakness_count >= 1..4`,
   `medium_weakness_count >= 1 / 3`, `acr >= 8`, AES thresholds (300 / 500 / 600 / 700 / 800 / 900), and
   `asset_class = ACCOUNT / IDENTITY`. Read totals only; listing thousands of identities floods the context.
4. **Persons inherit their accounts' weaknesses.** An IDENTITY (person) asset carries the IoEs of its linked
   ACCOUNT, so the affected asset count is about 2 × the finding count (2,912 PANPAD findings → 5,742
   identity-class assets with exactly one critical). Check it with `asset_class = ACCOUNT` vs `IDENTITY` counts.
5. **Groups and resources have no AES** (`AES: N/A`): IoEs on GROUP / RESOURCE objects (Too many privileged
   accounts, Too many members in a privileged group, Unsafe permissions on AdminSDHolder / DC container)
   earn no direct score credit. Show them as risk items, never as score movers.
6. **Model the population as groups** (`n`, `crit`, `high`, `med`, `AES`, privileged flag) and apply S2 to
   each group with a dynamic greedy (re-rank after every action). Allocate each IoE's highs to the privileged
   group in proportion to its finding total.
7. **Empirical AES floor — AES is anchored by ACR.** Don't let S2 drive identity AES towards 0. Read the
   floor from the tenant: AES of `acr >= 8`, `critical = 0`, `high >= 1` identities (reference: 507–700 →
   floor 500) and of ACR-2 accounts with highs (reference: 300–399 → floor 300). Validate S2's first step the
   same way: removing the single critical should land near the floor-group AES (reference: 787 → 629 modeled,
   600–700 observed). Actions that only push a group below its floor get 0 score credit — say so.
8. **Privileged-membership lever.** De-privileging an account drops its ACR (9 → 2), removes its
   privileged-only IoEs (delegation, Entra sync, SPN) and moves its AES to the de-privileged floor. Model it
   as an action "Cut privileged group membership" with an explicit share of privileged accounts
   (default 50%), state the share as an assumption to confirm with the customer, and tag it Extended effort.
   It is often the second-largest lever.
9. **Identity tracker rows.** One item per IoE action, tracked against the AD domain object
   (`asset_type = RESOURCE`, e.g. `DC=CORP,DC=LOCAL`), `plugin_id` = the IoE name, `plugin_source =
   Tenable IE (IoE)`, `locator` = "AD domain … – N findings on M identity assets", `est_score_delta` = the
   action's ΔGlobal. Say in Section G that the account list lives in Tenable Identity Exposure; on tracking
   runs, compare each IoE's finding total with the baseline count and report the % reduction in `notes`.
10. **SLA.** Identity hardening is 45–60 days: tag every identity action "Extended effort — start now, may
    carry over", even when it is a scripted bulk change, because privileged-account changes need approval
    (Protected Users can break service accounts).

Store the group profile, floors, the de-privileged share and the IoE totals in
`meta.score_model.identity` so tracking runs reuse the same model.

### S1. Baseline Exposure Score (every run)
- **Reported value.** `CES_reported` comes from S0 (API file, device pull or typed value). It is
  authoritative: the phase targets are computed from it. Without it, use the computed value below.
- **Computed value, always.** Define the population: `is_licensed = true`, `last_observed_at within last
  ["90"]`, `aes exists`, plus `exposure_classes` or a tag when the user means a specific card. Call
  `tenable_one_search_assets(limit=1)` and read `total` for `aes exists`, `aes > 0` and every 50-point
  threshold `aes >= 50`, `>= 100` … `>= 950` (about 21 calls, all independent, so send them in one batch).
  Band counts are differences between consecutive totals (band 1–49 = `aes > 0` minus `aes >= 50`). Then
  `CES_est = Σ(band_count × band_midpoint) ÷ N_population`, where assets with AES 0 count as 0.
  50-point bands matter: on a 34k-asset tenant, 100-point bands gave 227 and 50-point bands gave 232.
  Also compute the variant without AES-0 assets (`÷ count(aes > 0)`).
- **Range check.** Every asset could sit at the bottom or the top of its band, so also compute
  `CES_floor = Σ(band_count × band_low) ÷ N` and `CES_ceil = Σ(band_count × band_high) ÷ N`, and show the
  score as `CES_est (CES_floor–CES_ceil)`. With `CES_reported`, say whether it falls inside the range:
  - **Inside:** the population matches Exposure View, and any gap is band rounding.
  - **Outside:** the population differs, because Exposure View averages over more or fewer assets than the
    filter above. Estimate how many AES-0 assets it leaves out (`N − Σ AES ÷ CES_reported`, where
    `Σ AES ≈ CES_est × N`). Then break the AES-0 assets down by `asset_class`: on large tenants, unscanned
    APPLICATION assets discovered by ASM are usually most of them. Name the likely cause in Section G and
    keep k. Scaling every delta by k is still correct, as long as the gap is a population difference and
    not a different scoring method.
- **Calibration.** With `CES_reported`, keep whichever variant is closer and set `k = CES_reported ÷ CES_est`.
  Apply k to every modeled delta. If |k − 1| > 0.15, the scope probably differs (exposure class, card filter,
  stale assets): say so and ask which card the user is targeting. Without `CES_reported`, use the variant that
  includes AES-0 assets, set k = 1 and say the score is computed.
- **Label.** Use "Exposure Score (Exposure View)" or "Exposure Score (computed from N assets' AES)". This
  replaces the old top-25-AES proxy listed in `references/mcp-collection.md`. A mean over the 25 worst assets
  sits near 950 on most tenants, which overstates the score and makes every fix look far bigger than
  Tenable will show it.
- Record `N_population`, the band counts, `CES_floor`/`CES_ceil`, the variant, k and `CES_reported` in `current.json` → `meta.score_model`
  so tracking runs reuse exactly the same method.

### S2. Per-asset AES model
For each asset touched by the plan, take `AES_now` and `critical/high/medium/low_weakness_count` from
`tenable_one_search_assets`.
```
D = 1.0·critical + 0.5·high + 0.1·medium + 0.02·low        # default band weights
AES_after = AES_now × ln(1 + D_after) ÷ ln(1 + D_now)        # 0 when D_after = 0
ΔAES = AES_now − AES_after
```
The log keeps AES high until most severe weaknesses are gone, which matches how Tenable's AES behaves. An
action removes, per asset, the distinct CVEs (weaknesses) it clears in each band. When only plugin counts
are known, count one weakness per plugin. Superseded rollups usually share CVEs, so count CVEs rather than
plugins wherever possible. List the weights in Section G as defaults.

### S3. Action → Exposure Score delta, phasing and feasibility
- Rank greedily. Apply each selected action to the assets' remaining counts before scoring the next one, so
  two actions on the same host are not both credited with its full drop.
  `ΔCES_action = k × ΣΔAES ÷ N_population`.
  `est_score_delta` per tracker item = ΔCES_action split across its plugin × asset items in proportion to each
  item's ΔAES.
- **Feasibility first.** The most the plan can achieve is `k × Σ AES_now(assets in the retrieved findings) ÷
  N_population`. Reaching −10% needs `0.10 × CES × N` AES points removed. For example, CES 227 on 34,399 assets
  needs about 780,000 AES points, the equivalent of roughly 820 hosts going from 950 to 0. Put this in the
  executive summary. If the VPR ≥ 9 slice cannot reach a target, also collect VPR 7.0–8.9 findings
  (`vpr_min="7.0"`) before declaring the target out of reach. Then apply the existing "show the achievable
  figure" rule.
- **Tracking runs.** Pull the official score again (S0, same card_id) and recompute the computed score with
  the same population and variant. The official value is the Actual point and refreshes k; the computed value
  is shown next to it so a model drift is visible. Without a new official value, keep the previous k so the
  Actual line compares like with like. Tenable recalculates daily, so a fix shows
  up only after a rescan and the next recalculation. Say this when Actual lags Planned by a few days.

---

## Execution Flow

### 1. Collect data from Tenable MCP

```
EXPOSURE SCORE BASELINE (Scoring models S0 + S1)
- Official Exposure View score from the Exposure View API (S0 source ladder: uploaded
  gorr_exposure_view.json → collector on the user's computer → typed value), plus the computed CES
  from AES band counts (licensed, seen in the last 90 days), the calibration factor k and the
  classification (High 650–1000 / Medium 350–649 / Low 0–349)
- Official daily trend and other Exposure View cards from the same file
- Industry benchmark (percentile and average score for the sector) — from the card details when present
- Goal: calculate target score for each phase (10/20/30/40% reduction)

VULNERABILITIES FOR PRIORITIZATION
- All findings with: CVE/Plugin ID, VPR, severity, affected assets (list),
  public exploit (bool), plugin family (to infer effort)
- For each finding: which assets it affects (ACR per asset)
- Estimated score reduction per finding (use Lumin/Exposure View data if available)

ASSET DETAILS (required — powers the By-asset view and the tracker, see Section C)
For every asset that appears in any prioritized finding, collect the identifying and
operational fields the remediation team needs to actually locate and fix it. Tenant assets
are NOT all devices — in a Tenable One inventory most licensed objects are frequently
Identity Exposure objects (DEVICE, RESOURCE, ACCOUNT, IDENTITY, GROUP). An IDENTITY, ACCOUNT
or GROUP has no IP and no OS, so DO NOT force device columns onto it. Instead, first read the
asset's **type** and then collect the identifying fields that make sense for that type.

ALWAYS collect (every asset type):
- asset_id (UUID) and asset **type** (DEVICE / RESOURCE / ACCOUNT / IDENTITY / GROUP / WEBAPP / …)
- Display name (device hostname, identity display name, account name, group name, resource name)
- ACR (Asset Criticality Rating), AES, and `critical/high/medium/low_weakness_count` (inputs to Scoring model S2)
- Last seen / last observed timestamp
- Tags — **all** of them, as `Category:Value` (e.g. `Owner:Infra SP`, `OS:Windows`, `Environment:Prod`).
  The owner tag drives the owner of the asset (see "Owner from Tenable tags"); keep the full list for the Tags column
- Crown Jewel flag and chokepoint flag (from the two sections below)
- The specific finding(s)/plugin(s) on that asset that place it in each phase

For DEVICE-type assets, ALSO collect (the "fix the box" fields):
- FQDN if available
- IPv4 address (and IPv6 if present)
- Operating system + OS version / build (e.g. "Windows Server 2008 R2", "RHEL 9.3", "Cisco IOS 15.2")
- Last authenticated scan timestamp
- Source (agent vs. network scan) and, if agent, agent name/status

For IDENTITY / ACCOUNT / GROUP / RESOURCE-type assets, ALSO collect the identity-appropriate
locators (whatever the MCP exposes for that object — render "—" for any that are absent):
- Identity source / provider (e.g. Active Directory, Entra ID, Okta) and the source domain/tenant
- UPN / SAM account name / email / login (the string an admin searches on to find the object)
- Distinguished Name (DN) or object path / OU when present
- Account/object state: enabled vs. disabled, privileged/admin flag, stale (last logon), MFA status
- For GROUP: member count and whether it is a privileged/nested group
- For RESOURCE: resource kind (e.g. GPO, service principal, cloud resource) and owner

Retrieve these via the Tenable asset/workbench/inventory MCP calls (asset info / asset details /
Tenable One inventory search) keyed by the asset IDs referenced in each finding. Keep a lookup of
asset_id → {type, …details} so each remediation task can render its exact affected assets with the
right context regardless of whether the object is a device or an identity object.

CROWN JEWELS
- List of Crown Jewels (business-critical assets)
- Which findings affect Crown Jewels → flag for weight bonus

ATTACK PATH CHOKEPOINTS
- Graph nodes with the highest number of paths passing through
- Which assets are chokepoints → flag for weight bonus

BENCHMARK
- Average score for the configured industry/sector
- Organization's percentile vs. peers
```

#### Owner from Tenable tags (every run)

1. **Pick the owner tag category once per tenant.** Call `tagging_list_tag_categories_and_values`. If the user
   named the category (e.g. "use the tag Owner", "o dono é a tag Diretoria"), use it. Otherwise look for a category
   whose name means owner/accountability — Owner, Dono, Responsável, Team/Time, Squad, Department/Departamento,
   Business Unit/BU, Área, Diretoria, Gerência, 事業部. If exactly one matches, use it and **say which one in the
   reply**; if several match or none does, **ask the user which category holds the owner** (list the categories
   with a few values each) before building the tracker. `"*"` = every tag on the asset counts as owner — only when
   the user asks for that. Technical categories (Operating System, Software, ASM, scan dates) are never owners.
2. **Collect each asset's tags** in the asset-resolution step (Tenable One inventory search / workbench asset
   info — see `references/mcp-collection.md`), for every asset in the plan and, on tracking runs, every asset in the
   uploaded tracker (including ones whose finding is gone, so ownership stays current).
3. **Write them into `current.json`** as `owner_tag_category` + `asset_tags` (`asset_id → ["Category:Value", …]`).
   `scripts/tracker.py` derives `owner`, `owner_source` and `owner_tag` from them — never type the owner yourself.
4. Rules the script applies (tracker-schema.md §10): one tag value → that value; several values in the owner
   category → joined with " / " and `owner_source = Tenable tag (multiple)` (flag it); no owner tag → keep a
   manually typed owner (`Manual (no owner tag)`) or leave it `Untagged`; a manually typed owner on a tagged asset is
   replaced by the tag and the old value is kept in `notes`.
5. `suggested_owner_team` (Section 7) stays as a **hint only** — it tells an untagged asset which team probably
   owns it; it is never used as the owner.
6. Report the coverage from `COMPARISON.owner_coverage` (tagged %, untagged assets, multi-owner assets) in the
   reply, the dashboard and Section G. Untagged assets are a finding in their own right: recommend tagging them
   in Tenable (a dynamic tag rule by IP range / OS / AD OU is usually the fastest fix) — but **never create or
   apply tags yourself**; the skill is read-only.

**Finding instances (required for the tracker):** keep every prioritized finding at the
plugin × asset level (`plugin_id`, `asset_id`), not only the per-plugin aggregate — the tracker,
the By-asset view and the fix verification all work on that pair.

**Proven call sequence and known MCP gaps:** read `references/mcp-collection.md`. In short: page
`tenable_one_search_findings` with `vpr_min` + `sort=finding_vpr_score:desc`; resolve assets in one
`tenable_one_search_assets` call filtered by `asset_id`; enrich devices with `workbenches_get_asset_info`.

**Plugin IDs — always the real Tenable plugin ID.** `plugin_id` in the tracker and dashboard is the ID Tenable
attached to the finding (`finding_detection_id`): Nessus, NNM, WAS or OT. Never create GORR/synthetic plugin IDs.
The search output hides this field, so resolve each ID in the plugin database and confirm it against the tenant —
follow `references/plugin-id-resolution.md` (token-based lookups, Nessus-vs-NNM same-title check, verification
filter). Findings from third-party connectors carry no Tenable plugin: keep the CVE (or the source's finding
name) as `plugin_id`, set `plugin_source = Third-party`, and label them "3rd-party" — never invent an ID.
Record `plugin_source` and a `verified` flag for every plugin.

**Plugin-ID pitfalls seen on live tenants:** a token search can return a sibling plugin (e.g. `KB4011205`
returns 104558 "Office Compatibility SP3", while the finding "Security Updates for Microsoft Office Products
(November 2017)" is 104557), and a guessed neighbour ID can be a different check (156032 is "Log4j
Unsupported Version", 156103 is "Log4j 1.2 JMSAppender"). Always confirm with `finding_detection_id contains
<id>` and compare the returned finding title; if no ID resolves, leave that finding out of the tracker and
name it in Section G rather than guessing.

**Tracking runs — extra collection:** for every `item_key` in the uploaded tracker, check whether the
finding is still open, and fetch the asset's `last_seen` / last scan time even when the finding is gone.
Without `last_seen`, a missing finding cannot be told apart from an asset that simply wasn't scanned —
the script marks those `Not re-scanned` instead of fixed. Also collect the current Exposure Score so the
trend line gets its next point.

If the MCP is unavailable: notify the user and generate a dashboard with demo data (mock),
making it clear that the data is fictional.

---

### 2. Calculate Quick Win Score for each finding

```python
# Prioritization logic pseudocode
for finding in all_findings:
    vpr_weight = finding.vpr / 10  # normalize 0–1
    breadth_weight = len(finding.affected_assets) / total_assets  # normalize 0–1
    
    # Effort: single plugin with many assets = low effort
    if finding.is_single_patch_multi_asset:
        effort = 0.2  # low effort
    elif finding.affected_assets_count > 5:
        effort = 0.5  # medium effort
    else:
        effort = 1.0  # standard effort
    
    # Impact = Exposure Score points this action removes (Scoring model S2–S3),
    # computed on top of the actions already selected (greedy, marginal)
    delta_ces = marginal_ces_delta(finding)
    qw_score = delta_ces / effort
    
    # Crown Jewel bonus
    if finding.affects_crown_jewel:
        qw_score *= 1.30
    
    # Chokepoint bonus
    if finding.asset_is_chokepoint:
        qw_score *= 1.20
    
    # The bonuses reorder the plan; they never inflate the projected drop
    finding.estimated_score_delta = delta_ces
    finding.qw_score = qw_score
```

**Data-gap adjustments (apply when the MCP limits in `references/mcp-collection.md` hold):**
- *VPR band only* → no adjustment needed. Scoring model S2 works on band counts, as Tenable's density does;
  display "≥ 9.0" in tables.
- *Estimated Δ without Lumin data* → Scoring model S2–S3. The asset's own weakness counts are the
  denominator, so findings the plan did not retrieve still hold the asset's AES up and the plan cannot
  over-claim.
- *No Crown Jewel tags* → ×1.30 for ACR ≥ 9 as the critical-asset proxy.
- *No chokepoint data* → no chokepoint bonus; show "—".

**Priority override — active compromise:** a backdoor/implant detection (e.g. DOUBLEPULSAR) or any
indicator of existing compromise is pinned to the top of Phase 1 regardless of score, flagged "isolate and open
an incident before patching", and shown as a red alert banner under the header.

**Risk pin — exploited in the wild:** single-fix actions with active exploitation (Zerologon, MS17-010 /
EternalBlue, Log4Shell and similar) go to Phase 1 even when their score effect is negligible (common when
the hosts carry ≥ 10 criticals each, or when VM is a small share of Global). Badge them "exploited in the wild
— risk-driven, negligible score effect" and say so in the executive summary, so nobody reads the plan as
"the score says skip it".

---

### 2b. Group plugins into remediation actions

Rank and phase **remediation actions**, not individual plugins — one change ticket usually clears many plugins:
- Superseded OS rollups/KBs/bulletins on the same OS family → "apply latest cumulative rollup" (one action).
- EOL software (Flash) → "uninstall"; old Reader/IE versions → "upgrade to current".
- Same CVE family on a fleet of endpoints → "Windows cumulative update — endpoints".
- Container images sharing a base → "rebuild on patched base image"; repo dependencies → "upgrade dependencies".
- EOL OS (Win7/2008 R2, 2012 R2 past ESU, macOS 10.14) → mark "Extended effort" and say an upgrade is needed.
Every plugin keeps its real `plugin_id`; `action_id` / `action_name` are grouping labels only (tracker columns).

---

### 3. Assemble the N cumulative phases inside the 30-day cycle

The run date is **D0**. The cycle closes at **D30**, which is also the next recommended run date. **N** is the
phase count from Q2 (2–6). Each phase has a fixed calendar window and a cumulative reduction target:

- **Targets:** 10% per phase by default (`target_pct_i = 10 × i`), or a user total spread evenly
  (`total × i ÷ N`, e.g. 5 phases to 40% → 8/16/24/32/40%).
- **Windows:** the 30 days split evenly, `due_i = D0 + floor(30 × i ÷ N)`, last phase due D30. Four phases keep
  the classic 7 / 14 / 21 / 30 days. Examples: 3 phases → D10 / D20 / D30; 5 → D6 / D12 / D18 / D24 / D30;
  6 → D5 / D10 / D15 / D20 / D25 / D30.
- **Colors:** F1 `#71FFC6`, F2 `#4EA5FF`, F3 `#BB8FF2`, F4 `#FF8837`, F5 `#E7FF00`, F6 `#FFFFFF`.

| Phase | Target (cumulative, default) | Due date (4 phases) | Color |
|-------|------------------------------|---------------------|-------|
| Phase 1 | −10% | D0 + 7 | `#71FFC6` |
| Phase 2 | −20% | D0 + 14 | `#4EA5FF` |
| Phase 3 | −30% | D0 + 21 | `#BB8FF2` |
| Phase 4 | −40% | D0 + 30 | `#FF8837` |
| Phase 5 / 6 (when chosen) | −50% / −60% | evenly split (see above) | `#E7FF00` / `#FFFFFF` |

Sort actions by `qw_score` descending (after the compromise override) and accumulate `estimated_score_delta`
until each threshold is reached. Advance **at most one phase per action**, so no phase is left empty when a
single large action crosses two thresholds; show the achieved cumulative % on each card (e.g. −12.1%).
If the actions run out before the last phase, leave the trailing phases empty rather than pushing work later:
their cards say "No actions left — the plan tops out at −X%" and the executive summary says so.
Actions not needed to reach the final target go to a **"Beyond the −[final]% — next cycle"** list (not in the
tracker), with a note on any cheap, high-value item worth doing anyway (e.g. a single-fix Zerologon).

```
current_score = CES_reported if given, else CES_est (Scoring model S1)
target_i      = current_score × (1 − target_pct_i ÷ 100)   for i = 1 … N   (Phase i, cumulative)
```

**Changing the phase count mid-cycle (tracking run, Q2 answered with a new N).** Never rebuild the cycle
from scratch: re-phase it with `gorr_phases.py rephase` (Appendix B), then run the tracker on the re-phased file.
- Phases whose due date has already passed stay **locked** (items, due dates, targets unchanged), so missed
  work stays missed. The new N must be larger than the number of locked phases.
- The remaining days (run date → D30) are split evenly across the open phases; targets run from the last locked
  target up to the new final target.
- Items of open phases are re-assigned in their original order, each action kept whole, with the same greedy
  rule (advance when a target is met, at most one phase per action). Ticket fields, owners and history carry over.
- Report the change in the reply and the dashboard: old → new count, the new due dates and targets, which
  items moved (from → to), empty trailing phases, and any item whose due date moved earlier. The tracker keeps
  the change in `cycle.phase_history`.

Fitting the work into 30 days:
- Phase 1 should be dominated by actions with a public exploit and a single patch across many assets —
  they match the 7-day SLA. If a top-ranked action is structural (IAM/AD/RBAC, 60-day SLA), keep it in its
  phase by score but tag it **"Extended effort — start now, may carry over"** so nobody is surprised at D30.
- If the available findings cannot reach a target (e.g. only −34% is achievable), show the achievable
  figure on that phase card instead of inventing actions, and say so in the executive summary.
- Each phase shows: target score, incremental actions, accumulated actions, predominant fix categories,
  due date, and the phase's workload per owner (Tenable tag), with untagged items counted separately.

### 4. Build the tracker (every run)

Write `current.json` from the collected data (format in references/tracker-schema.md §2). `scripts/tracker.py`
is built for 4 phases, so **always run it through the phase wrapper**: write Appendix B verbatim to the working
directory as `gorr_phases.py` (it loads tracker.py unchanged and swaps in the chosen phase plan), then:

```bash
T=/mnt/skills/plugins/gorr/scripts/tracker.py      # use the skill's actual install path
# Baseline run (N phases from Q2; add --total 40 when the user gave a total instead of 10% per phase)
python3 gorr_phases.py run --tracker $T --phases N -- --current current.json --out-dir /mnt/user-data/outputs
# Tracking run, same phase count (the wrapper reads the plan stored in the tracker)
python3 gorr_phases.py run --tracker $T -- --current current.json \
        --previous /mnt/user-data/uploads/<uploaded tracker> --out-dir /mnt/user-data/outputs
# Tracking run with a new phase count: re-phase first, then track against the re-phased file
python3 gorr_phases.py rephase --previous /mnt/user-data/uploads/<uploaded tracker> --phases N \
        --run-date YYYY-MM-DD --out prev_rephased.json
python3 gorr_phases.py run --tracker $T -- --current current.json --previous prev_rephased.json \
        --out-dir /mnt/user-data/outputs
```

On a baseline, give every phased finding a `phase` between 1 and N. The wrapper stops with an error if the
tracker and `--phases` disagree (re-phase first) and if tracker.py's phase constants ever change shape. It
stamps `cycle.phase_count`, `cycle.phase_plan` and `cycle.phase_history` into `gorr_tracker.json`, so the next
run knows the plan. Trackers from before this change load as 4 phases. The script prints a summary with the cycle dates,
counts, carry-over summary, per-phase impact and warnings; it writes `gorr_tracker.json`, `gorr_tracker.csv` and
`gorr_comparison.json` (with `COMPARISON.carryover`).
Surface any `warnings` (e.g. unrecognized status values, untagged or multi-owner assets, auto-detected owner
category) to the user. Pass `owner_tag_category` and `asset_tags` so the script fills `owner` from Tenable tags;
pre-fill `suggested_owner_team` from the table in Section 7 as a hint only. `assignee`, `ticket_id` and
`ticket_status` are for the user (and `owner` only on untagged assets).
Fill `plugin_source`, `action_id` and `action_name` on every finding in `current.json`, and on baseline runs
`est_score_delta` — the item's share of its action's estimated Δ (action Δ split across its plugin×asset items,
weighted like the Δ model). Carry-over impact is measured from it; without it the script falls back to an even
split and warns. Also embed a
`PLAN.plugins` map in the HTML: `plugin_id → {name, source, verified, action, phase, delta, assets}`.
If plugin IDs change between runs (e.g. a mistaken earlier baseline), tell the user to discard the old tracker —
item keys will not match.

### 5. Generate the Interactive Dashboard

Generate a **standalone HTML file** (inline CSS + vanilla JS — never React/JSX), saved to
`/mnt/user-data/outputs/gorr_quick_wins_<YYYYMMDD>.html`, and deliver it together with `gorr_tracker.csv`
and `gorr_tracker.json` via `present_files`. Embed the full tracker as `const TRACKER = {...}` and the
comparison as `const COMPARISON = {...}`; every view below renders from those objects.

Mandatory palette:
- **Background**: `#44494B` — page and cards (cards: `rgba(255,255,255,0.06)` over it). Never use dark
  backgrounds like #0a0e14, #1E2426, #192124.
- **Titles / highlight**: `#E7FF00` · **Body text**: `#FFFFFF` · **Charts / links**: `#4EA5FF`
- **Positive / fixed**: `#71FFC6` · **Secondary / benchmark**: `#BB8FF2` · **Alerts / Crown Jewels**: `#FF8837`
- **Overdue / blocked / claimed-but-still-detected**: `#FF4B4B`
- Phase colors: F1 `#71FFC6`, F2 `#4EA5FF`, F3 `#BB8FF2`, F4 `#FF8837`, F5 `#E7FF00`, F6 `#FFFFFF`. Every
  phase-based view (cards, gauge markers, chart, module panel, progress bars) renders the cycle's N phases
  from `TRACKER.cycle.phase_due_dates` / `phase_targets_pct` — never a hard-coded four.
- Borders `1px solid rgba(255,255,255,0.12)`, radius `12px`, Helvetica Neue, sentence case, weights 300/500
- Gauge: `#44494B` background, green→yellow→orange arc, white needle

#### Section A — Executive Header
```
[GORR emblem] | GORR (Game Over Risk Reduction)
               | Quick Wins — 30-day cycle · [N] phases · [Organization]
Current score: [X]/1000 — [Classification] · source: Exposure View API ([card name], as of [pulled_at])
               | Exposure View (typed) | computed from [N] assets' AES
Computed check: [CES_est] ([floor]–[ceil]) · k = [k]   ← muted line, only when an official value exists
Target score ([final]% reduction by [D30 date], [N] phases): [Y]/1000
Industry benchmark [Sector]: [Z] — you are [above/below/at] market average
```

**GORR emblem — top left of every report (mandatory).** The header always starts with the GORR
risk-reduction emblem, never the Tenable logo or any other brand logo. Paste this inline SVG verbatim (no
image file, no data URI, no external URL — it must work offline):

```html
<div class="hdr" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
 <svg viewBox="0 0 64 64" width="52" height="52" role="img" aria-label="GORR risk reduction emblem" style="display:block;flex:none"><path d="M32 4 L54 12 V30 C54 45 44 55 32 60 C20 55 10 45 10 30 V12 Z" fill="rgba(231,255,0,.08)" stroke="#E7FF00" stroke-width="3" stroke-linejoin="round"/><rect x="19" y="20" width="6" height="22" rx="2" fill="#FF4B4B"/><rect x="29" y="27" width="6" height="15" rx="2" fill="#FF8837"/><rect x="39" y="34" width="6" height="8" rx="2" fill="#71FFC6"/><path d="M17 15 L45 37" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/><path d="M37 38 L46 38 L46 29" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M24 48 L30 53 L41 45" stroke="#71FFC6" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
 <div style="border-left:1px solid rgba(255,255,255,.12);padding-left:14px">
  <h1 style="margin:0;font-size:24px">GORR <span style="color:#fff;font-weight:300">(Game Over Risk Reduction)</span></h1>
  <div class="muted">Quick Wins — 30-day cycle · [N] phases · [Organization]</div>
 </div>
</div>
```

The emblem is a yellow shield with three shrinking bars (red → orange → green), a white downward arrow and a
green check: risk going down. The page `<title>` is `GORR (Game Over Risk Reduction) — Quick Wins · [cycle_id]`.
The footer reads `GORR v[version] · read-only toward Tenable · generated [timestamp]`.

**Compromise alert (conditional):** directly under the header, a red-bordered banner naming the host, IP,
ACR and plugin of any implant/backdoor detection, with "isolate and investigate before patching".

#### Section A2 — Run cycle & tracking (always visible, directly under the header)

```
Executed on: 25 Sep 2026        Cycle: GORR-20260925 (D0 → D30)
Next run:    25 Oct 2026        [10 days left]  ← countdown; turns #FF8837 at ≤5 days, #FF4B4B when past due
Phase due dates:  F1 02 Oct · F2 09 Oct · F3 16 Oct · F4 25 Oct   (current phase highlighted)
Phase plan:  4 phases (−10/−20/−30/−40%) · kept since 25 Sep        ← or "changed 4 → 5 on 12 Oct · 3 items moved"
Exposure Score source:  Exposure View file gorr_exposure_view_20260925_101500.json   ← the Q1 answer
```

Include a one-line instruction: *"Run this skill again on [next run date] and upload gorr_tracker (JSON or
CSV) to verify which vulnerabilities were fixed."* Also add a small **"Add to calendar"** button that
downloads an `.ics` event for the next run date (built client-side with a Blob).

On **tracking runs**, this section also shows the comparison vs. the previous run from `COMPARISON.counts`:

| Tile | Meaning | Color |
|------|---------|-------|
| Fixed (verified) | Tenable no longer sees it on a re-scanned asset | `#71FFC6` |
| Still open | Still detected | `#FFFFFF` |
| Reopened | Was verified fixed, detected again | `#FF8837` |
| New (backlog) | High-VPR findings that appeared since the baseline | `#BB8FF2` |
| Not re-scanned | Can't verify — asset not seen since last run | `#E7FF00` |
| Claimed resolved, still detected | Ticket says Resolved, Tenable disagrees | `#FF4B4B` |
| Overdue | Past phase (or override) due date, not fixed | `#FF4B4B` |
| Missed from past phases | `counts.carryover` items · `carryover_pts_at_risk` pts not realized, plus "Recovered since last run" | `#FF4B4B` |

Plus a per-phase progress bar (% fixed verified, from `COMPARISON.phases`) and a
"Previous run: [date] → This run: [date]" caption. Clicking a tile filters the Tickets tab to those items.
On baseline runs show the tiles area as "Baseline — first comparison available on [next run date]".

**Owner coverage strip (always, under the tiles):** from `COMPARISON.owner_coverage` —
"Owner = Tenable tag `<category>` · X% of assets tagged · N untagged · M with multiple owners". Clicking "untagged"
filters the Tickets tab to `owner_source ∈ {Untagged, Manual (no owner tag)}`. Color the % `#71FFC6` at 100%,
`#E7FF00` at ≥ 80%, `#FF8837` below. Add an **"Owners"** mini-table from `COMPARISON.owners` (owner · assets · items ·
% fixed verified · overdue · pts at risk), sorted by items, with "No owner tag" last in `#FF8837`.

#### Section B — Central Gauge / Speedometer
- Current score (needle), one marker per phase target (N markers), industry benchmark reference line,
  green zone at the 40% target. On tracking runs, a ghost needle for the baseline score.
- Under the gauge, a small "Official" / "Computed" badge stating which score drives the needle.
- **Module → Global panel (when S0 returned module cards), directly under the gauge.** One row per module,
  sorted by `max_c` desc:

  | Module | Score now (grade) | Industry avg | Assets (share of Global) | Global pts per module pt | Max Global drop | After F1 → … → FN | Global effect |
  |--------|-------------------|--------------|--------------------------|--------------------------|-----------------|---------------------------|---------------|

  - *After F1 → F4* = the module's projected score at each phase due date (S0b step 4).
  - *Global effect* = `lever_c × ΔModule_c` at the last phase (FN), shown as "−3.0 pts (−1.2%)".
  - A stacked bar under the table splits the Global score (`CES_reported`) into `max_c` per module, then shows
    the planned FN Global score and which module removed how much — the "where Global comes from" view.
  - Mini sparkline per row from the module's `ces_trend`; the tenant target line (`target_score`) on the
    Global row.
  - Clicking a row filters the phase tabs to assets of that exposure class.

#### Section C — Remediation Phases (clickable cards)

N horizontal cards, one per phase (a grid of N columns; wrap to two rows above 4):

```
┌──────────────────────────────────────┐
│  PHASE 1 — −10%   due 02 Oct         │
│  Score: 580 → 522  (official base)   │  ← targets from CES_reported (S0)
│  VM 326 → 290 · Identity 566 → 540   │  ← module scores at this phase due date (S0b)
│  Global effect: −1.0 (VM) −11.0 (Id.) │  ← lever_c × ΔModule_c, per module
│  Quick Wins: 12 actions · 34 assets  │
│  Predominant: Patch (8), Misconfig (4)│
│  Tickets: 9/34 assigned · 5 fixed ✓  │  ← tracking progress from TRACKER
│  Owners: Infra SP 18 · AppSec 9 · +2 │  ← items per Tenable-tag owner (untagged in orange)
│  [View details ▼]                    │
└──────────────────────────────────────┘
```

On tracking runs, past-due phase cards also show a red strip "⚠ N missed · −X pts not realized · [status]" and the
phase receiving recovery work shows "+N carried in" (references/carryover.md §6).

Clicking a card expands the phase detail with **four tabs** (vanilla JS; Tab 4 appears on tracking runs). All three share a filter bar:
search box, asset type, **owner (Tenable tag)**, owner source (tag / multiple / manual / untagged), ticket status,
Tenable state, "Crown Jewels only", "Flags only".

**Tab 1 — By vulnerability** (default). **One row per Tenable plugin applicable to the phase**, grouped under
its remediation action (action header rows in plan order, the compromise action first):

| Plugin ID | Plugin name | Source | VPR | Assets | Score Δ | Critical asset? | Owner(s) | Progress |
|-----------|-------------|--------|-----|--------|---------|-----------------|----------|----------|

- *Plugin ID* is the real Tenable ID (highlighted); third-party rows show the CVE, muted, with a "3rd-party" badge.
  *Source* badge: Nessus / NNM / WAS / OT / 3rd-party, plus "✓ verified" when confirmed on the tenant.
- Under the plugin name, list the asset names it applies to; expanding the row shows every affected asset
  (name, type, locator, OS, ACR, owner, ticket, assignee, status, Tenable state, flag).
- *Owner(s)* = the distinct Tenable-tag owners of the plugin's assets (e.g. "Infra SP (12) · AppSec (3)"), with
  "No owner tag (n)" in `#FF8837`. When one plugin spans several owners, the bulk-assign hint says so — one ticket
  per owner is usually cleaner than one ticket for all.
- **Three bulk-assign levels:** the action header ("one ticket for the whole action": assignee / ticket / status for
  all items of the action), per owner inside the action ("one ticket per owner"), and per plugin ("Assign all
  assets"). Bulk assign never overwrites a tag-derived owner; it only fills `owner` on untagged items.
- *Progress* = mini bar of fixed-verified / total items, plus ticket ID(s) in use.
- Show 10 plugins per action, then "View all N plugins in this action". Header line: "Phase N: X plugins on Y assets".

**Tab 2 — By asset**. One row per asset touched in the phase, expandable to that asset's vulnerabilities:

This table MUST render usefully for identity objects (IDENTITY / ACCOUNT / GROUP / RESOURCE) as well as
devices — never show a phase's assets as a wall of "—" just because they are not devices. Achieve this
with a **type-aware column set**: a shared spine of columns for all types, plus a single adaptive
"Locator" column that carries the identifying string appropriate to the asset's type.

Shared columns (all asset types):

| Asset (name) | Type | Locator | OS / version | ACR | **Owner (tag)** | Related action(s) / Plugin ID | Severity | Last seen | Tags | Crown Jewel? |
|--------------|------|---------|--------------|-----|-----------------|-------------------------------|----------|-----------|------|--------------|

How to fill the adaptive columns per asset type:
- **DEVICE** → *Locator* = IPv4 (and FQDN if present); *OS / version* = the OS build.
- **IDENTITY / ACCOUNT** → *Locator* = UPN / SAM / email + identity source (e.g. `jdoe@corp.local ·
  Active Directory`); *OS / version* = the identity source/provider + object state (enabled/disabled,
  privileged, stale). Put DN/OU in a tooltip or expandable detail.
- **GROUP** → *Locator* = group name + source; *OS / version* = member count + privileged/nested flag.
- **RESOURCE** → *Locator* = resource kind + identifier (e.g. `GPO · Default Domain Policy`);
  *OS / version* = owner or scope.
- **Owner (tag)** → the owner value with a small tag badge showing `owner_tag` in a tooltip; "Multiple" badge when
  `owner_source = Tenable tag (multiple)`; "No owner tag" in `#FF8837` plus the `suggested_owner_team` hint in muted
  text when untagged.
- Any field the MCP does not return → render "—" (never leave blank), but choose the column mapping so
  the row still carries a usable identifier for its type.

Alternative allowed layout: if a single adaptive table is awkward, split Tab 2 into **sub-sections by
asset type** ("Devices", "Identities & Accounts", "Groups", "Resources"), each with the column set that
fits that type. Default to the single adaptive table; use sub-sections only when a phase mixes many
types and the columns would otherwise fight each other.

Add to the shared columns: **# vulns in phase**, **Plugin IDs** (count split "N Tenable · M 3rd-party"),
**worst VPR**, and **Progress** (fixed / total for that asset). Expanding an asset **lists every vulnerability
on that asset in the phase** — one row per plugin: Plugin ID, plugin name, source badge, remediation action,
VPR, severity, ticket, assignee, status, Tenable state — sorted by estimated Δ. Sort by ACR desc, then worst VPR; flag Crown Jewel rows
(`#FF8837`) and chokepoints; count header with type breakdown, e.g. "Phase 1 touches 34 assets —
21 devices, 9 identities, 3 groups, 1 resource". Show 15 rows, then "View all N".

**Tab 3 — Tickets** (the tracker, filtered to the phase; a global "All phases + Backlog" toggle).
One row per item (plugin × asset):

| Plugin ID | Plugin name | Asset | Locator | Owner (tag) | Assignee | Ticket # | Ticket URL | Status | Due | Tenable state | Flag | Notes |
|-----------|-------------|-------|---------|-------------|----------|----------|------------|--------|-----|---------------|------|-------|

- Assignee, ticket #, ticket URL, status (dropdown), due override and notes are **editable inline**.
- **Owner is read-only when it comes from a Tenable tag** (lock icon + tooltip "From Tenable tag `<owner_tag>` —
  change the tag in Tenable"). It is editable only on untagged rows (`owner_source` Untagged / Manual), where it
  saves as `Manual (no owner tag)`.
- Buttons: **Download tracker (CSV)**, **Download tracker (JSON)**, **Load tracker file** (in-browser
  overlay of ticket columns only), exactly per references/tracker-schema.md §8.
- Status chips: Not started (gray), Assigned (`#4EA5FF`), In progress (`#E7FF00`), Blocked (`#FF4B4B`),
  Resolved (`#71FFC6`), Risk accepted / False positive (`#BB8FF2`).
- Ticket # renders as a link when `ticket_url` is present.

**Tab 4 — Carry-over** (missed from past phases). Impact-on-targets table per phase (target vs. planned vs.
projected-with-carry-over vs. actual, gap, status), breakdown by type and owner team, and the items table with
recovery phase, recovery due, escalation, suggested action and the editable `recovery_plan` /
`recovery_due_override`. Also reachable as a global "All past phases" view from the A2 tile. Layout, columns
and colors: references/carryover.md §6. Carry-over rows are highlighted (red left border + "Missed F1 · 9d"
badge) in Tabs 1–3 too.

Every tab also offers a per-phase CSV export of what it shows (the Tickets export is the tracker itself).

A **Backlog** strip under the phase cards lists `New` items discovered after the baseline (tracking runs
only); they are tracked but not re-phased until the next cycle.

#### Section D — Cumulative Progression Chart
- X axis: Baseline → F1 → … → FN (with due dates under each label); Y axis: score
- Projected score per phase (solid), industry benchmark (dashed), shaded improvement zone
- **Projected with carry-over** (dashed `#FF4B4B`) from `COMPARISON.carryover.phase_impact[].projected_score`
  on tracking runs.
- **Actual** line from `TRACKER.runs` (each run's Exposure Score plotted at its date) — the planned vs.
  actual gap is the key executive signal on tracking runs.
- **Exposure View (official, daily)** line in `#E7FF00` from `meta.score_model.official.official_trend`,
  covering the days before D0 and every day between runs, so progress shows up between monthly runs. Phase
  due dates are marked on the X axis; a planned target the daily line crosses early is marked ✓.
- When both an official and a computed score exist on a run, plot the computed point as a small muted marker
  so the model drift is visible.

#### Section E — Benchmark vs. Peers ("Where you stand")
This is the card rendered under the **"Where you stand"** heading. Comparative card:
```
Your organization:    [Score] — [Percentile]th percentile
Industry average:     [Score]
Top quartile (25%):   [Score]
Target after 40% reduction: [Score] — [New percentile]th percentile
Interpretation: "By reaching Phase [N] on [D30 date], you will move from [X]th to [Y]th percentile in the [Sector] industry"
```

**Sizing / layout (must fit all content — DO NOT CLIP). These are hard requirements, not suggestions:**
- The card container MUST use `height: auto` and MUST NOT set any fixed `height` or `max-height`.
  If a `min-height` is used, treat it as a floor only (`min-height` + `height:auto`), never a cap.
- The card and every element inside it MUST NOT use `overflow: hidden`, `overflow: clip`, or a fixed
  height with `overflow` on the text — these are the usual causes of the interpretation sentence being
  cut off. If you need rounded corners, achieve them with `border-radius` on an auto-height box, not by
  clipping a fixed-height box.
- Render this as a full **standalone row** by default (its own grid/flex row at full container width).
  Do **not** place it in a cramped multi-column grid cell where the interpretation sentence gets squeezed.
  If it must share a row with the progression chart, give Section E at least ~40% width AND keep
  `height:auto`; the moment content risks overlap, drop it to its own full-width row — visibility wins
  over compactness, every time.
- The interpretation sentence is long and MUST wrap fully: `white-space: normal`, `overflow-wrap:
  anywhere` (or `word-break: normal`), `line-height: 1.5`, and it must span the full card width on its
  own line(s) beneath the benchmark rows — never truncated with an ellipsis.
- Lay out the four benchmark rows as a two-column label/value structure (e.g. CSS grid
  `grid-template-columns: max-content 1fr` or a definition list) with a clear gap (≥16px) so values
  never collide with labels; let each row be `height:auto`.
- Comfortable internal padding: ≈20–24px on all sides.
- Responsive: at container widths below ~640px, stack each label above its value (single column) and
  let the whole card grow taller — never introduce an inner scrollbar.
- Quick self-check before finalizing: with the longest realistic interpretation sentence and the
  largest four scores, every one of the four benchmark lines AND the full interpretation sentence must
  be visible at once with no scrollbar and no cut-off text. If not, the card is still too small — grow it.

**Benchmark source:** use the benchmark / industry / percentile fields from the Exposure View API file (S0)
when present and label them "Exposure View benchmark, as of [pulled_at]".

**When the benchmark is not available (no API file, or no benchmark fields in it):** keep the card, show "n/a" for industry average, top
quartile and percentile, still show the target score and date, and say in the interpretation sentence to read
the benchmark from Lumin / Exposure View before the board readout. Never invent percentiles.

#### Section F — Executive Summary (for the board)
Plain business language, no jargon:
- 3–4 lines explaining the 30-day roadmap.
- "By closing [N] high-priority vulnerabilities by [F1 due date], we estimate reducing our risk by 10%."
- "A [final]% reduction in [N] phases requires [N_total] actions, to be completed by [D30 date]." (say if the plan tops out earlier)
- Tracking runs: "[X] of [N] actions verified fixed ([P]%); score moved from [baseline] to [current];
  [K] items overdue, mostly owned by [owner from Tenable tag]." Name the biggest blocker honestly.
- One line on accountability: "[P]% of the plan's assets have an owner tag in Tenable; [N] assets (worth
  [Δ] pts) have no owner and need tagging." Omit only when coverage is 100%.
- Tracking runs: carry-over lines per references/carryover.md §7 — items and points held back, first phase
  that will miss and by how much, who holds the gap, L3 escalations.
- Benchmark comparison: impact on positioning vs. peers (or say it is unavailable).
- If a compromise indicator exists, the first action line is "isolate <host> and investigate today".
- State where most of the reduction comes from (e.g. "two-thirds from three OT machines") and the realistic
  blocker (e.g. OT change windows) — check each claim against the plan numbers.

#### Section G — Method & data limits (always)
A short list covering: data source and coverage (e.g. "400 of 552 VPR ≥ 9 findings retrieved"), every proxy used
(score source — Exposure View API card name/id, `score_path`, `pulled_at`, or typed/computed — and population N, AES band counts (50-point), floor–ceiling range and whether the Exposure View value falls inside it, variant, calibration k, VPR band, Crown Jewel), the Δ model
(S2 band weights and log curve, greedy marginal crediting) and the feasibility ceiling, how plugin IDs were resolved (✓ = confirmed on the tenant),
third-party findings without plugins, named gaps (assets with high AES but no findings returned), and **owner
coverage** — which tag category defines the owner (and whether it was auto-detected), % of assets tagged, the
untagged assets by name, and assets with more than one owner tag.

---

### 6. SLA reference (used to flag feasibility inside the 30-day cycle)

- Patch with active public exploit → 7 days (fits Phase 1)
- Standard patch / simple misconfiguration → 30 days
- Identity/Cloud hardening → 45 days · Structural misconfiguration (IAM, AD, RBAC) → 60 days
Anything with an SLA longer than the remaining window of its phase gets the "Extended effort" tag.

---

### 7. Suggested Owners by Action Type (hint only — pre-fills `suggested_owner_team`)

The real owner is the asset's Tenable tag (see "Owner from Tenable tags"). This table only produces a hint shown
next to untagged assets, so the team knows who to ask while the tag is being fixed.

| Fix type | Suggested owner |
|----------|----------------|
| OS/Firmware Patch | Infra / IT Operations |
| Application Patch | AppSec / Dev Team |
| Identity/AD Misconfiguration | IAM / Active Directory |
| Cloud Misconfiguration | Cloud Ops / DevSecOps |
| OT/ICS | OT Security / Engineering |
| Containers/K8s | Platform Engineering |
| Certificates/Permissions | IT Governance / SecOps |

---

## Supported Customizations

| User request | Adaptation |
|--------------|-----------|
| "Only phases 1 and 2" / "3 phases" / "5 phases" | That is the Q2 answer: plan N phases (2–6) inside the 30-day cycle |
| "Go to 50%" / "5 phases to 40%" | Q2 with a total: `--phases 5` (10% each) or `--phases 5 --total 40` |
| "Change the number of phases" (mid-cycle) | Re-phase the open cycle (section 3) — past-due phases stay locked |
| "Weekly cycle" / "60-day cycle" | Scale the phase windows proportionally; `next_run_date` = end of cycle |
| "Focus on Cloud / Identity / OT" | Filter Quick Wins by the requested domain |
| "Portuguese version" | Dashboard in Portuguese; technical terms (VPR, findings, attack path) stay in English |
| "For the board" | Expand Section F; collapse Tabs 2–3 by default |
| "Include regulatory context" | Map actions to LGPD, ISO 27001, NIST CSF, PCI-DSS |
| "Show only Crown Jewels" | Filter quick wins affecting Crown Jewels |
| "Group by owner" | Group Tabs 1–3 by the Tenable-tag owner (untagged group last) |
| "Owner is tag X" / "use category X as owner" | Set `owner_tag_category` = X for this run |
| "Every tag is an owner" | `owner_tag_category = "*"` |
| "One dashboard per owner" | Add an owner selector that filters every section to one tag owner (same file) |
| "Only show identities" / "Only show devices" | Pre-set the asset-type filter |
| "Tracker in Excel" | Deliver the same columns as .xlsx (read the xlsx skill) with a Status dropdown validation |
| "Target the VM card" / "use card X" | Phase targets on module X's score (S0b step 7); every phase still shows the Global effect |
| "Give me the Exposure View script" | Deliver Appendix A as `gorr_exposure_view_pull.py` with run instructions |
| "De-privilege X% of admins" / "change the privileged share" | Set the S0c step 8 share to X and re-phase |
| "Include Web App / Cloud findings" | Collect that module's findings (S0b lever) and add its actions to the greedy |

---

## Important Notes

- **Quick Win Score is not CVSS** — it prioritizes real impact + execution feasibility.
- **Breadth is the executive differentiator** — one patch closing 50 assets beats 50 individual fixes.
- **Crown Jewels have moral priority** — always visually emphasized even when not top-ranked.
- **Phases are cumulative and locked for the cycle** — Phase 2 includes Phase 1 + the increment; tracking
  runs never re-rank the current cycle. The only exception is a phase-count change chosen in Q2: it re-phases
  the open phases (section 3) and leaves past-due phases untouched.
- **Ticket status is a claim; Tenable state is evidence** — show both and highlight disagreements.
- **Carry-over needs both halves** — an item from a past-due phase is done only when Tenable verified the fix
  *and* the ticket is closed; show ticket-only gaps apart from real risk (0 pts at risk).
- **Never infer "fixed" from absence alone** — require the asset to have been seen after the previous run.
- **Tracker columns `plugin_id` and `asset_id` are the join key** — tell users not to edit them.
- **Owner lives in Tenable, not in the spreadsheet** — to change who owns an asset, change its tag in Tenable;
  a typed owner on a tagged asset is overwritten on the next run (old value kept in `notes`). Tell users this when
  handing over the tracker.
- **`plugin_id` is always Tenable's own plugin ID** (or the CVE/finding name for third-party detections) —
  never a GORR-generated ID. Actions group plugins; they don't replace them.
- **Label every proxy** (score, VPR band, Crown Jewel) and every unavailable input (benchmark, chokepoints)
  in the dashboard itself — the executive must not mistake a proxy for Tenable's number.
- **Check the benchmark direction before writing any sentence about it.** Lower is better: a score below the
  industry average is "N points below (better than)", never "above". Compute the sign in code
  (`ces > industry ? 'above' : 'below'`) instead of writing it by hand, and also compare with the population
  average and the tenant's own `target_score`.
- **Score feasibility honestly.** If the targets are out of reach, show the achievable figure on each phase
  card and the chart, name the module that would have to carry the rest (remaining `lever_c × module score`),
  and offer to collect that module's findings (often Web Application medium/low or Cloud) for the next run.
- **Official beats computed.** When the Exposure View API value exists it drives targets, gauge and Actual
  line; the computed score is the cross-check. This supersedes the "Tenable One Exposure Score (CES)" fallback
  row in `references/mcp-collection.md` (top-25-AES proxy), which is no longer used.
- **API keys never go through the chat.** The collector reads them from env vars or a local file on the
  user's machine. The Exposure View endpoints are beta: if a pull fails (404 = not enabled on the tenant,
  403 = missing privilege), say so and fall back down the S0 ladder.
- **If `estimated_score_delta` is not available in the MCP**, use the estimation table from the
  tenable-security-manager-report skill as a fallback.
- **Demo mode**: if the MCP is unavailable, use realistic fictional data with a "DEMO — illustrative data"
  watermark; the tracker files are still produced so the workflow can be demonstrated end to end.

---

## Usage Context

Used by a **Tenable Channel SE** to:
- Show C-Level and Board the shortest path to measurable risk reduction, with dates attached
- Help CISOs run a monthly remediation cadence with owners, tickets and verified outcomes
- Show MSSPs/Resellers how to package a recurring 30-day Exposure Management service
- Turn raw vulnerability data into "close this, by this date, owned by this person — and prove it"
- Make ownership auditable: the owner comes straight from Tenable tags, so tagging hygiene becomes part of the cycle

---

## Appendix A — Exposure View collector (`gorr_exposure_view_pull.py`)

Write this file verbatim when S0 needs it (device run or hand-over). Python 3.8+, standard library only,
read-only. The user runs `python3 gorr_exposure_view_pull.py` (options: `--all` adds custom cards,
`--card NAME` filters by name, `--param trend_timeframe=…` passes extra detail params, `--base URL` for
FedRAMP hosts) and uploads the `gorr_exposure_view_YYYYMMDD_HHMMSS.json` it writes next to the script (each run
keeps a new timestamped file, so the folder doubles as an execution history).

```python
#!/usr/bin/env python3
"""GORR - pull the official Exposure Score from the Tenable One Exposure View API (read-only).
Keys: env TIO_ACCESS_KEY/TIO_SECRET_KEY, else tenable_keys.txt in the script's folder (then the current folder) (access_key=..., secret_key=...),
else hidden prompt. Output: gorr_exposure_view_YYYYMMDD_HHMMSS.json in the same folder as this script
(normalized cards + raw responses); each run writes a new file, so earlier pulls are kept as a history.
Usage: python3 gorr_exposure_view_pull.py [--all] [--card NAME] [--param k=v] [--base URL]"""
import argparse, datetime as dt, getpass, json, os, sys, time, urllib.error, urllib.parse, urllib.request

HINTS = ("score", "ces", "grade", "benchmark", "industry", "percentile", "target", "peer")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def keys(path):
    a, s = os.environ.get("TIO_ACCESS_KEY"), os.environ.get("TIO_SECRET_KEY")
    if a and s: return a, s
    # look next to this script first, then in the current folder (or the exact --keys-file path)
    paths = [path] if os.path.isabs(path) else [os.path.join(SCRIPT_DIR, path), os.path.abspath(path)]
    path = next((x for x in paths if os.path.isfile(x)), None)
    if path:
        print(f"Using keys file: {path}")
        kv = dict(l.split("=", 1) for l in open(path, encoding="utf-8") if "=" in l and not l.startswith("#"))
        kv = {k.strip().lower(): v.strip() for k, v in kv.items()}
        if kv.get("access_key") and kv.get("secret_key"): return kv["access_key"], kv["secret_key"]
        print(f"{path} has no access_key/secret_key lines")
    else:
        print("tenable_keys.txt not found in: " + " | ".join(dict.fromkeys(paths)))
    return getpass.getpass("Access key: ").strip(), getpass.getpass("Secret key: ").strip()

def get(base, path, k, params=None):
    url = base + path + ("?" + urllib.parse.urlencode({a: b for a, b in (params or {}).items() if b is not None}) if params else "")
    req = urllib.request.Request(url, headers={"X-ApiKeys": f"accessKey={k[0]};secretKey={k[1]}", "Accept": "application/json",
                                               "User-Agent": "Integration/1.0 (Tenable SE; GORR; Build/1.3)"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 2: time.sleep(int(e.headers.get("Retry-After", "5"))); continue
            hint = {401: "bad API keys", 403: "needs EXPOSURE_VIEW.READ / Tenable One", 404: "beta endpoint not on tenant"}.get(e.code, "")
            sys.exit(f"HTTP {e.code} {path} {hint}\n{e.read()[:400].decode('utf-8','replace')}")
        except urllib.error.URLError as e: sys.exit(f"Network error: {e.reason}")

def as_list(o):
    if isinstance(o, list): return o
    for k in ("cards", "data", "items", "results", "values"):
        if isinstance(o, dict) and isinstance(o.get(k), list): return o[k]
    return []

def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items(): yield from walk(v, f"{p}.{k}" if p else k)
    elif isinstance(o, list):
        if o and all(isinstance(x, dict) for x in o) and len(o) > 3: yield p, o      # series
        else:
            for i, v in enumerate(o): yield from walk(v, f"{p}[{i}]")
    else: yield p, o

def normalize(card, det):
    fields = {p: v for p, v in walk(det) if not isinstance(v, list) and any(h in p.lower() for h in HINTS)}
    nums = {p: v for p, v in fields.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1000}
    bad = ("benchmark", "industry", "peer", "target", "trend", "delta", "change", "sla", "percentile", "previous")
    cand = sorted((p for p in nums if "score" in p.lower() and not any(b in p.lower() for b in bad)), key=len)
    series = {p: v for p, v in walk(det) if isinstance(v, list)}
    trend_path = next((p for p in series if "trend" in p.lower()), None)
    return {"id": card.get("id") or card.get("card_id"), "name": card.get("name") or card.get("card_name"),
            "is_global": card.get("is_global", card.get("is_global_card")),
            "score": nums[cand[0]] if cand else None, "score_path": cand[0] if cand else None,
            "score_like_fields": fields, "trend_path": trend_path,
            "trend": series.get(trend_path, [])}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys-file", default="tenable_keys.txt"); ap.add_argument("--card"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--param", action="append", default=[]); ap.add_argument("--base", default="https://cloud.tenable.com")
    a = ap.parse_args(); base = a.base.rstrip("/"); k = keys(a.keys_file)
    extra = dict(p.split("=", 1) for p in a.param if "=" in p) or None
    cards, off = [], 0
    while True:
        page = as_list(get(base, "/api/v1/t1/exposure-view/cards", k,
                           {"is_global_card": None if a.all else "true", "text_query": a.card, "limit": 25, "offset": off}))
        cards += page
        if len(page) < 25: break
        off += 25
    out = {"source": "Tenable One Exposure View API (beta)", "pulled_at": dt.datetime.now().astimezone().isoformat(),
           "base": base, "params": extra or {}, "cards": [], "raw": {"list": cards, "details": {}}}
    for c in cards:
        cid = c.get("id") or c.get("card_id")
        if not cid: continue
        d = get(base, f"/api/v1/t1/exposure-view/cards/{cid}", k, extra)
        out["raw"]["details"][cid] = d
        n = normalize(c, d); out["cards"].append(n)
        print(f"{str(n['name']):<40} score={n['score']}  ({n['score_path']})  trend_points={len(n['trend'])}")
    # always next to this script, timestamped so every execution is kept (e.g. gorr_exposure_view_20261123_121005.json)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(SCRIPT_DIR, f"gorr_exposure_view_{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n{len(out['cards'])} card(s) -> {out_path}  (upload it to the GORR run)")

if __name__ == "__main__": main()
```

Note: with `--all`, `is_global_card` is omitted so both global and custom cards are returned; per-card
projection (S0) needs the exposure-class cards, so prefer `--all` when the user wants per-card views.

---

## Appendix B — Phase wrapper (`gorr_phases.py`)

Write this file verbatim to the working directory on every run (section 4). Python 3.8+, standard library
only. It reads `scripts/tracker.py`, replaces only its phase constants (`CYCLE_DAYS`, `PHASE_WINDOWS`,
`PHASE_TARGETS` and the hard-coded `{"1", "2", "3", "4"}` phase sets) for the chosen plan, runs it, and stamps
the plan into the tracker. `rephase` re-plans an open cycle when the phase count changes. Tested on the
reference tenant's tracker: 4 phases give output identical to tracker.py; 3, 5 and 6 phases, 4 → 5 on day 4
and 4 → 3 after F1 was past due all behave as section 3 describes.

```python
#!/usr/bin/env python3
"""GORR - run scripts/tracker.py with a chosen number of phases, and re-phase a cycle when that number changes.

tracker.py is built for 4 phases (7/14/21/30 days, 10/20/30/40 %). This wrapper loads it unchanged, swaps the
phase constants for the plan the user chose, runs it, and stamps the plan into the tracker's cycle.

  # run tracker.py (baseline or tracking) with N phases; everything after "--" goes to tracker.py
  python3 gorr_phases.py run --tracker <skill>/scripts/tracker.py --phases 5 [--step 10 | --total 40] [--cycle-days 30] \
          -- --current current.json [--previous prev.json] --out-dir OUT [--run-date YYYY-MM-DD]

  # change the phase count of an open cycle (tracking run): writes a re-phased copy of the previous tracker
  python3 gorr_phases.py rephase --previous gorr_tracker.json --phases 3 [--step 10 | --total 40] \
          --run-date YYYY-MM-DD --out prev_rephased.json

Targets are cumulative: default 10 % per phase (N phases -> N x 10 %); --total spreads a total over N phases.
Phase windows split the cycle evenly (4 phases over 30 days keeps the classic 7/14/21/30). Read-only.
"""
import argparse, json, math, os, re, sys
from datetime import date, datetime, timedelta

LEGACY = {"windows": {1: 7, 2: 14, 3: 21, 4: 30}, "targets": {1: 10, 2: 20, 3: 30, 4: 40}}


def day(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def plan(n, step=None, total=None, cycle_days=30):
    if not 2 <= n <= 6:
        sys.exit("phases must be between 2 and 6")
    if total is not None:
        targets = {i: round(total * i / n, 1) for i in range(1, n + 1)}
    else:
        s = 10.0 if step is None else step
        targets = {i: round(s * i, 1) for i in range(1, n + 1)}
    if targets[n] >= 100:
        sys.exit(f"final target {targets[n]}% is not achievable; lower --step or --total")
    if n == 4 and cycle_days == 30 and step in (None, 10) and total in (None, 40):
        return dict(LEGACY["windows"]), dict(LEGACY["targets"])
    windows = {i: max(1, math.floor(cycle_days * i / n)) for i in range(1, n + 1)}
    windows[n] = cycle_days
    return windows, targets


def patched_tracker(path, windows, targets, cycle_days):
    src = open(path, encoding="utf-8").read()
    phase_set = "{" + ", ".join(f'"{p}"' for p in sorted(windows)) + "}"
    subs = [
        (r"^CYCLE_DAYS = \d+", f"CYCLE_DAYS = {cycle_days}"),
        (r"^PHASE_WINDOWS = \{[^}]*\}", f"PHASE_WINDOWS = {windows!r}"),
        (r"^PHASE_TARGETS = \{[^}]*\}", f"PHASE_TARGETS = {targets!r}"),
    ]
    for pat, rep in subs:
        src, n = re.subn(pat, rep, src, count=1, flags=re.M)
        if n != 1:
            sys.exit(f"tracker.py changed: could not find {pat!r} - update gorr_phases.py")
    src = src.replace('{"1", "2", "3", "4"}', phase_set)
    if '{"1", "2", "3", "4"}' in src and len(windows) != 4:
        sys.exit("tracker.py still has a hard-coded 4-phase set")
    ns = {"__name__": "gorr_tracker_phased", "__file__": path}
    exec(compile(src, path, "exec"), ns)
    return ns


def stamp(out_dir, windows, targets, cycle_days, history=None):
    p = os.path.join(out_dir, "gorr_tracker.json")
    t = json.load(open(p, encoding="utf-8"))
    cyc = t["cycle"]
    cyc["phase_count"] = len(windows)
    cyc["phase_plan"] = {"cycle_days": cycle_days, "windows_days": {str(k): v for k, v in windows.items()},
                         "targets_pct": {str(k): v for k, v in targets.items()}}
    cyc.setdefault("phase_history", history or [{"date": cyc.get("cycle_start"), "phases": len(windows),
                                                  "event": "baseline plan"}])
    json.dump(t, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return cyc


def cmd_run(a, rest):
    prev_cycle = None
    if "--previous" in rest:
        pp = rest[rest.index("--previous") + 1]
        if pp.lower().endswith(".json"):
            prev_cycle = json.load(open(pp, encoding="utf-8-sig")).get("cycle", {})
    cycle_days = a.cycle_days
    if prev_cycle and prev_cycle.get("phase_plan"):                 # tracking run: honour the cycle's own plan
        pl = prev_cycle["phase_plan"]
        windows = {int(k): v for k, v in pl["windows_days"].items()}
        targets = {int(k): v for k, v in pl["targets_pct"].items()}
        cycle_days = pl.get("cycle_days", cycle_days)
        if a.phases and a.phases != len(windows):
            sys.exit(f"previous tracker has {len(windows)} phases but --phases {a.phases}: run 'rephase' first")
    elif prev_cycle:                                                # tracker from before phase plans = 4 phases
        n = len(prev_cycle.get("phase_due_dates") or {}) or 4
        if a.phases and a.phases != n:
            sys.exit(f"previous tracker has {n} phases but --phases {a.phases}: run 'rephase' first")
        windows, targets = plan(n, cycle_days=cycle_days)
        targets = {int(k): float(v) for k, v in (prev_cycle.get("phase_targets_pct") or targets).items()}
    else:
        windows, targets = plan(a.phases or 4, a.step, a.total, cycle_days)
    ns = patched_tracker(a.tracker, windows, targets, cycle_days)
    sys.argv = ["tracker.py"] + rest
    rc = ns["main"]()
    out_dir = rest[rest.index("--out-dir") + 1] if "--out-dir" in rest else "/mnt/user-data/outputs"
    cyc = stamp(out_dir, windows, targets, cycle_days, (prev_cycle or {}).get("phase_history"))
    print(json.dumps({"phase_count": cyc["phase_count"], "phase_due_dates": cyc["phase_due_dates"],
                      "phase_targets_pct": cyc["phase_targets_pct"]}, ensure_ascii=False))
    return rc


def cmd_rephase(a):
    t = json.load(open(a.previous, encoding="utf-8-sig"))
    cyc, items = t["cycle"], t["items"]
    run = day(a.run_date) if a.run_date else date.today()
    start, end = day(cyc["cycle_start"]), day(cyc["next_run_date"])
    old_due = {int(p): day(d) for p, d in cyc["phase_due_dates"].items()}
    old_tg = {int(p): float(v) for p, v in cyc["phase_targets_pct"].items()}
    old_n = len(old_due)
    locked = sorted(p for p, d in old_due.items() if d < run)        # windows already closed stay as they were
    k = len(locked)
    if a.phases <= k:
        sys.exit(f"{k} phase(s) already past due; the new plan needs more than {k} phases")
    _, new_tg = plan(a.phases, a.step, a.total, (end - start).days)
    due = {p: old_due[p] for p in locked}
    tg = {p: old_tg[p] for p in locked}
    span = (end - max(run, start)).days
    for j in range(k + 1, a.phases + 1):
        due[j] = max(run, start) + timedelta(days=max(1, math.floor(span * (j - k) / (a.phases - k))))
        tg[j] = new_tg[j] if not k else round(old_tg[locked[-1]] + (new_tg[a.phases] - old_tg[locked[-1]]) * (j - k) / (a.phases - k), 1)
    due[a.phases] = end
    # re-assign items of open phases, keeping each action whole and in its original order
    base = float(cyc.get("baseline_exposure_score") or 0) or None
    done = sum(float(i.get("est_score_delta") or 0) for i in items if str(i.get("phase")).isdigit() and int(i["phase"]) in locked)
    order, acts = [], {}
    for i in sorted((i for i in items if str(i.get("phase")).isdigit() and int(i["phase"]) not in locked),
                    key=lambda i: int(i["phase"])):
        aid = i.get("action_id") or i["item_key"]
        if aid not in acts:
            acts[aid] = []; order.append(aid)
        acts[aid].append(i)
    p, cum, moved = k + 1, done, []
    for aid in order:
        for i in acts[aid]:
            if str(i["phase"]) != str(p):
                moved.append({"item_key": i["item_key"], "from": i["phase"], "to": p})
            i["phase"] = p
            i["phase_due_date"] = due[p].isoformat()
        cum += sum(float(i.get("est_score_delta") or 0) for i in acts[aid])
        if p < a.phases and (base is None or cum >= base * tg[p] / 100):
            p += 1                     # same rule as the baseline: advance when the target is met, at most one phase per action
    cyc["phase_due_dates"] = {str(q): due[q].isoformat() for q in sorted(due)}
    cyc["phase_targets_pct"] = {str(q): tg[q] for q in sorted(tg)}
    cyc["phase_count"] = a.phases
    cyc["phase_plan"] = {"cycle_days": (end - start).days,
                         "windows_days": {str(q): (due[q] - start).days for q in sorted(due)},
                         "targets_pct": {str(q): tg[q] for q in sorted(tg)}}
    hist = cyc.get("phase_history") or [{"date": cyc["cycle_start"], "phases": old_n, "event": "baseline plan"}]
    hist.append({"date": run.isoformat(), "phases": a.phases, "event": f"re-phased {old_n} -> {a.phases}",
                 "locked_phases": locked, "items_moved": len(moved)})
    cyc["phase_history"] = hist
    cyc["phase_planned_delta"] = {}
    for i in items:
        if str(i.get("phase")).isdigit():
            q = str(i["phase"]); cyc["phase_planned_delta"][q] = round(cyc["phase_planned_delta"].get(q, 0) + float(i.get("est_score_delta") or 0), 2)
    json.dump(t, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    empty = [q for q in range(k + 1, a.phases + 1) if not any(str(i.get("phase")) == str(q) for i in items)]
    print(json.dumps({"old_phases": old_n, "new_phases": a.phases, "locked": locked, "moved": moved,
                      "phase_due_dates": cyc["phase_due_dates"], "phase_targets_pct": cyc["phase_targets_pct"],
                      "empty_phases": empty}, ensure_ascii=False, indent=1))


def main():
    argv = sys.argv[1:]
    rest = argv[argv.index("--") + 1:] if "--" in argv else []
    own = argv[:argv.index("--")] if "--" in argv else argv
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--tracker", required=True); r.add_argument("--phases", type=int)
    r.add_argument("--step", type=float); r.add_argument("--total", type=float); r.add_argument("--cycle-days", type=int, default=30)
    q = sub.add_parser("rephase"); q.add_argument("--previous", required=True); q.add_argument("--phases", type=int, required=True)
    q.add_argument("--step", type=float); q.add_argument("--total", type=float); q.add_argument("--run-date"); q.add_argument("--out", required=True)
    a = ap.parse_args(own)
    return cmd_run(a, rest) if a.cmd == "run" else cmd_rephase(a)


if __name__ == "__main__":
    sys.exit(main())
```