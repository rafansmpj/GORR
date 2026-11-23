# GORR Remediation Tracker — Schema & Merge Rules

Read this when running `scripts/tracker.py`, when the user uploads a tracker file, or when
building the Tickets tab / import-export buttons in the HTML.

Contents: 1. Tracking unit · 2. Input for the script · 3. Output files · 4. Columns ·
5. Status vocabulary · 6. Merge & comparison rules · 7. Flags · 8. HTML import/export contract ·
9. Carry-over (schema 1.1) · 10. Owner from Tenable tags (schema 1.2)

---

## 1. Tracking unit

One **item** = one finding on one asset: `item_key = "<plugin_id>:<asset_id>"`. `plugin_id` is the real
Tenable plugin ID from `finding_detection_id` (see plugin-id-resolution.md); for third-party detections it is the
CVE or the source's finding name. Never a GORR-generated ID.
This is the granularity at which Tenable can verify a fix. Many items may share one
`ticket_id` (e.g. a single change ticket to patch MS17-010 on 40 servers) — that's expected.
The By-vulnerability view groups items by `plugin_id`; the By-asset view groups by `asset_id`.

## 2. Input: `current.json` (Claude writes this from MCP data every run)

```json
{
  "run": { "organization": "ACME", "exposure_score": 640 },
  "backlog_min_vpr": 7.0,
  "owner_tag_category": "Owner",
  "asset_tags": { "uuid": ["Owner:Infra SP", "OS:Windows", "Environment:Prod"] },
  "assets_seen": { "<asset_id>": "2026-10-14T08:00:00Z" },
  "findings": [
    { "phase": 1, "plugin_id": "97833", "plugin_name": "MS17-010 ...", "plugin_source": "Nessus",
      "action_id": "GORR-A01", "action_name": "MS17-010 + DOUBLEPULSAR", "cves": ["CVE-2017-0144"],
      "vpr": 9.8, "severity": "Critical", "fix_type": "OS Patch",
      "asset_id": "uuid", "asset_name": "srv-dc01", "asset_type": "DEVICE",
      "locator": "10.0.0.5 · srv-dc01.acme.local", "acr": 9, "crown_jewel": true,
      "suggested_owner_team": "Infra / IT Operations", "est_score_delta": 4.2, "asset_last_seen": "2026-10-14" }
  ]
}
```

- **Baseline run:** include `phase` (1–4) on every prioritized finding. Only phased findings enter the tracker.
- **Tracking run:** `phase` is ignored (phases are locked from the baseline). Pass every *currently open*
  finding for the plugin×asset pairs in the uploaded tracker, plus new open findings with VPR ≥
  `backlog_min_vpr` (or on a Crown Jewel) — those become `Backlog`.
- **`assets_seen` is mandatory on tracking runs** for every asset in the uploaded tracker that no longer
  has the finding. It is how "fixed" is distinguished from "just not scanned". Pull `last_seen` /
  last scan time from the asset details MCP call. An asset missing from `assets_seen` is treated as not re-scanned.
- **`owner_tag_category` + `asset_tags` on every run** — tags for every asset in the plan (baseline) or in the
  uploaded tracker (tracking run). Accepted shapes per asset: `["Cat:Value", …]`, `[{"category":…, "value":…}]` or
  `{"Cat": ["v1","v2"]}`; a per-finding `asset_tags` field also works. See §10.

## 3. Output files (written to `--out-dir`)

| File | Purpose |
|------|---------|
| `gorr_tracker.json` | Full state: `cycle`, `runs` (history for the trend line), `ticket_statuses`, `items`. **Embed this in the HTML** as `const TRACKER = …`. Preferred upload format — keeps full run history. |
| `gorr_tracker.csv` | Same items, one row each, UTF-8 with BOM, comma-delimited. The spreadsheet the team fills. |
| `gorr_comparison.json` | Delta vs. previous run: counts, per-phase rollup, `cycle_complete`, `days_to_next_run`, warnings. |

CSV uploads work fully for tracking but carry only the baseline point of the history
(intermediate run scores are lost). Tell the user JSON keeps the full trend if they care about the line chart.

## 4. Columns

System columns (recomputed each run — user edits are overwritten):
`item_key, phase, phase_due_date, plugin_id, plugin_name, plugin_source, action_id, action_name, cves, vpr, severity, fix_type, asset_id,
asset_name, asset_type, locator, acr, crown_jewel, suggested_owner_team, est_score_delta, owner_source, owner_tag, tenable_state, flag,
first_seen_run, last_verified_at, carryover, carryover_type, missed_phase, days_past_due, carryover_runs,
first_missed_on, recovered_on, score_delta_at_risk, recovery_target_phase, recovery_due_date, recovery_action,
escalation_level, cycle_id, cycle_start, next_run_date, baseline_exposure_score`

**User columns (always preserved from the upload):**

| Column | Meaning |
|--------|---------|
| `owner` | Accountable owner. **Set from the asset's Tenable tag every run** (§10); the typed value is kept only on assets with no owner tag |
| `assignee` | Who is actually working the ticket right now |
| `ticket_id` | Ticket number (INC/CHG/RITM/Jira key…) — may repeat across rows |
| `ticket_url` | Optional link to the ticket |
| `ticket_status` | See §5 |
| `due_date_override` | Optional; replaces the phase due date for overdue checks (YYYY-MM-DD or DD/MM/YYYY) |
| `notes` | Free text (blocker reason, compensating control, change window…) |
| `recovery_plan` | Mitigation plan for a carry-over item (see carryover.md) |
| `recovery_due_override` | Date the team commits to for recovering a carry-over item |

`plugin_id` and `asset_id` must never be edited — they are the join key. Rows missing either are dropped.

## 5. Ticket status vocabulary

`Not started · Assigned · In progress · Blocked · Resolved · Risk accepted · False positive`

The importer normalizes common EN/PT variants (e.g. `Em andamento`→In progress, `Concluído`/`Done`/`Fixed`
→Resolved, `Bloqueado`→Blocked, `Risco aceito`→Risk accepted, `Falso positivo`→False positive, blank→Not started).
Unknown values are kept verbatim and reported in `warnings` — surface them to the user.

`ticket_status` is the team's **claim**. `tenable_state` is Tenable's **evidence**. The dashboard shows both.

## 6. Merge & comparison rules (implemented in `tracker.py`)

| Previous item is… | …and in this run | `tenable_state` | Counted as |
|---|---|---|---|
| any state except Fixed | finding still present | `Open` | still_open |
| `Fixed (verified)` | finding present again | `Reopened` | reopened |
| not Fixed | finding absent, asset seen **after** previous run | `Fixed (verified)` | fixed_verified |
| not Fixed | finding absent, asset not seen since previous run | `Not re-scanned` | unverified |
| `Fixed (verified)` | still absent | `Fixed (verified)` | fixed_verified |
| — (not in tracker) | open, VPR ≥ threshold or Crown Jewel | `New`, phase `Backlog` | new |

- Phases and due dates are **locked** for the whole 30-day cycle. New findings never get re-phased mid-cycle.
- `cycle_complete = run_date ≥ next_run_date`. When true, after rendering the comparison, build the next
  cycle's 4-phase plan: re-prioritize all open findings (carry-overs + backlog + new), run the script
  **without** `--previous` on the new plan, then copy owner/assignee/ticket fields from the old tracker
  onto carried-over items with the same `item_key` (mark them "Carried over from <old cycle_id>" in notes).
  Also copy `recovery_plan`, `carryover_runs` and `first_missed_on`, and place `Next cycle F1` items in Phase 1.

## 7. Flags (one per item, first match wins)

1. `Claimed resolved but still detected` — status Resolved, Tenable still sees it (Open/Reopened).
2. `Verified fixed — close ticket` — Tenable verified the fix but the ticket isn't closed.
3. `Overdue` — not fixed and run date > (`due_date_override` or `phase_due_date`); Risk accepted/False positive exempt.

## 8. HTML import/export contract (Tickets tab)

The dashboard is standalone HTML opened from disk, so it uses only `Blob` + `URL.createObjectURL` for
downloads and `<input type="file">` + `FileReader` for imports. No network, no browser storage required.

- **Export:** "Download tracker (CSV)" and "Download tracker (JSON)" produce exactly the §4 columns /
  the `gorr_tracker.json` shape, including any edits made in the page. CSV: UTF-8 BOM, comma, quote
  fields containing `,` `"` or newlines.
- **Inline editing:** owner (untagged rows only — read-only with a lock when `owner_source` is a Tenable tag), assignee, ticket_id, ticket_url, ticket_status (dropdown of §5), due_date_override,
  notes are editable in the Tickets table; edits update the in-memory `TRACKER` and re-render counters.
  Show an "Unsaved edits — download the tracker" badge after any edit.
- **Import in browser:** "Load tracker file" accepts .csv (`,` or `;`, BOM tolerant) or .json and overlays
  **only user columns** onto items by `item_key` (`owner` only where `owner_source` is not a Tenable tag). Label the result "Ticket data loaded — Tenable
  verification happens on the next skill run" — the browser cannot verify fixes.
- **Bulk assign:** in the By-vulnerability view, the action header sets assignee/ticket_id/status for every
  item of the remediation action (one change ticket per rollup), there is a per-owner variant inside each action
  ("one ticket per owner"), and each plugin row has "Assign all assets". Bulk assign never overwrites a
  tag-derived owner.

## 9. Carry-over (schema `gorr-tracker/1.1`)

On every tracking run the script marks items of past-due phases that are not (fixed in Tenable **and** ticket
closed) as `carryover = true`, classifies them, measures the points not realized against each cumulative phase
target, and proposes a recovery phase, date, action and escalation level. It adds `COMPARISON.carryover`
(`total`, `pts_at_risk`, `recovered_since_last_run`, `by_type`, `by_owner`, `recovery_load`, `phase_impact[]`)
and `COMPARISON.counts.carryover` / `carryover_pts_at_risk` / `recovered_since_last_run`.
Full rules and the dashboard spec: `references/carryover.md`. 1.0 trackers load unchanged.

## 10. Owner from Tenable tags (schema `gorr-tracker/1.2`)

The accountable owner of an item is the owner of its asset, and the owner of an asset is its Tenable tag in the
**owner tag category** (`owner_tag_category`, e.g. `Owner`, `Business Unit`, `Diretoria`). Implemented in
`apply_owners()` in `tracker.py`; recomputed on every run, baseline and tracking.

| Situation on this run | `owner` | `owner_source` | `owner_tag` |
|---|---|---|---|
| Asset has one value in the owner category | that value | `Tenable tag` | `Owner:Infra SP` |
| Asset has several values in the owner category | values sorted, joined with " / " | `Tenable tag (multiple)` | all, `; `-separated |
| Asset has tags, none in the owner category, user typed an owner | kept | `Manual (no owner tag)` | — |
| Asset has tags, none in the owner category, no typed owner | empty | `Untagged` | — |
| Owner tag removed in Tenable since the last run | cleared (then Manual/Untagged as above) | — | — |
| Asset absent from `asset_tags` this run (e.g. not returned) | previous tag owner kept | unchanged | unchanged |

- A typed owner on an asset that **has** an owner tag is replaced by the tag; the old value goes to `notes`
  ("Manual owner 'X' replaced by Tenable tag") and a warning is emitted. Tenable is the source of truth.
- Category matching is case- and accent-insensitive. `owner_tag_category` may be a string, a list (several
  categories, e.g. `["Owner", "Business Unit"]`) or `"*"` (every tag is an owner — only on explicit request).
- If `owner_tag_category` is missing, the script auto-detects one by name (Owner, Dono, Responsável, Team/Time,
  Squad, Department, Business Unit/BU, Área, Diretoria, Gerência, 事業部…) and warns "Confirm with the user".
  Claude should resolve the category before running the script (SKILL.md, "Owner from Tenable tags").
- `suggested_owner_team` is a hint only; it is never copied into `owner`.
- Carry-over `by_owner` and the new `COMPARISON.owners` group by `owner`; empty owners go to **"No owner tag"**.

Outputs added to `gorr_comparison.json`:
- `owner_coverage`: `owner_tag_category`, `auto_detected`, `assets_total`, `assets_tagged`, `assets_untagged`,
  `assets_multi_owner`, `assets_no_tag_data`, `pct_tagged`, `manual_owner_items`, `overridden_manual_owners`,
  `untagged_assets[]` and `multi_owner_assets[]` (asset_id, asset_name, owners).
- `owners`: `owner → {source, items, assets, fixed_verified, open, overdue, carryover, pts_at_risk,
  est_score_delta, pct_fixed, by_phase}`, sorted by items with "No owner tag" last.

1.0 / 1.1 trackers load unchanged: their `owner` values are treated as manual, so on the first 1.2 run any asset
with an owner tag takes the tag and the old typed owner is preserved in `notes`.
