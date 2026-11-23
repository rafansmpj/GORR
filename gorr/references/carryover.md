# GORR Carry-over — missed items from past phases, impact on targets, recovery plan

Read this on every **tracking run** and before building the Carry-over tab. All numbers come from
`scripts/tracker.py` (`TRACKER.items[*].carryover…` and `COMPARISON.carryover`) — never recompute them by hand
in the HTML, only render them.

Contents: 1. Definition · 2. Classification · 3. Fields added to JSON/CSV · 4. Impact on each phase target ·
5. Recovery plan rules · 6. Dashboard: highlight + Carry-over tab · 7. Executive summary lines

---

## 1. Definition

An item is **carry-over** when its phase due date (or `due_date_override`) is before the run date and it is
**not done**. Done means both halves: Tenable verified the fix **and** the ticket is closed (Resolved /
Risk accepted / False positive). Phases whose due date is still in the future are never carry-over.

Why both halves: the executive target only moves when Tenable stops seeing the finding, and the team's
process only finishes when the ticket is closed. A gap on either side is a missed commitment the next run
has to own.

## 2. Classification (`carryover_type`, first match wins)

| Tenable state | Ticket status | `carryover_type` | Score at risk? | Recovery action |
|---|---|---|---|---|
| Fixed (verified) | not closed | Fixed — ticket still open | No (0 pts) | Close the ticket |
| Not re-scanned | any | Unverified — asset not re-scanned | Yes (conservative) | Credentialed re-scan within 3 days |
| Open / Reopened | Resolved | Claimed resolved — still detected | Yes | Validate fix (reboot, superseding patch, all instances), re-scan |
| Open / Reopened | Risk accepted / False positive | Exception — still counts against target | Yes, but no recovery | Document exception + compensating control; re-plan the target |
| Open / Reopened | Blocked | Not fixed — blocked | Yes | Compensating control now (isolate / segment / disable service) + escalate blocker |
| Open / Reopened | Not started, no ticket | Not fixed — no ticket | Yes | Assign owner and open ticket today |
| Open / Reopened | other | Not fixed — ticket open | Yes | Re-plan into recovery phase and escalate |

An item that stops being carry-over gets `recovered_on = <run date>` and counts in
`COMPARISON.carryover.recovered_since_last_run` — show that number, it is the good news of the run.

## 3. Fields added to the tracker (JSON and CSV, schema `gorr-tracker/1.1`)

System fields (recomputed each run — user edits overwritten):

| Field | Meaning |
|---|---|
| `est_score_delta` | This item's share of its action's estimated Exposure Score reduction (written into `current.json` at baseline) |
| `carryover` | `true` / `false` |
| `carryover_type` | §2 vocabulary |
| `missed_phase` | `F1`…`F4` — the phase whose date was missed |
| `days_past_due` | Run date − effective due date |
| `carryover_runs` | Consecutive tracking runs the item has been carry-over (1 = first miss) |
| `first_missed_on` / `recovered_on` | Dates of the first miss / of recovery |
| `score_delta_at_risk` | Points of reduction not realized because of this item (0 for ticket-only gaps) |
| `recovery_target_phase` | Phase that now absorbs the item (`F3`, `Next cycle F1`, or `—` for exceptions/admin) |
| `recovery_due_date` | Proposed new date (§5) |
| `recovery_action` | Mitigation suggested by type (§2); gets "(recovery date already missed)" appended when applicable |
| `escalation_level` | `L1 — team lead` / `L2 — IT / security manager` / `L3 — CISO` |

User fields (preserved from the upload, editable in the dashboard):

| Field | Meaning |
|---|---|
| `recovery_plan` | The team's mitigation plan in their words (compensating control, change window, vendor ETA…) |
| `recovery_due_override` | Date the team commits to instead of the proposed `recovery_due_date`. If it passes with the item still carry-over, escalation jumps to L3 |

Trackers from `gorr-tracker/1.0` load fine. When `est_score_delta` is missing the script splits each phase's
planned increment evenly across its items and emits a warning — label those numbers "estimated — even split".

## 4. Impact on each phase target (`COMPARISON.carryover.phase_impact[]`)

Cumulative per phase `p` (items in phases ≤ p):

```
planned_reduction = Σ est_score_delta
pts_at_risk       = Σ score_delta_at_risk of carry-over items
projected_score   = baseline − (planned_reduction − pts_at_risk)     # if nothing else slips
target_score      = baseline × (1 − target_pct)
gap_pts           = max(0, projected_score − target_score)
status            = On track | At risk — still reachable | Will miss unless recovered
achievable_pct    = (planned_reduction − pts_at_risk) / baseline     # vs. if_recovered_pct = planned / baseline
```

"At risk — still reachable" happens when the phase was over-planned (surplus Δ covers the miss).
Future phases inherit the gap from earlier ones because targets are cumulative — say so in the tab.
For past-due phases `actual_score_now` (this run's Exposure Score) is also present: show it next to
`projected_score`. The projection is the plan model; the actual score also moves with new findings,
asset changes and VPR drift — never present one as the other.

## 5. Recovery plan rules (implemented in the script)

- **Recovery phase** = the phase still running today (first phase with due ≥ run date). If the cycle is over,
  `Next cycle F1` — and when you build the next cycle (tracker-schema.md §6) these items go into Phase 1
  first, keeping `carryover_runs`, `first_missed_on` and `recovery_plan`.
- **Recovery due date** = that phase's due date; for urgent items (Crown Jewel, VPR ≥ 9, or missed ≥ 2 runs)
  the earlier of that date and run date + 7. Unverified items: run date + 3 (a re-scan is cheap).
- **Escalation** = by days past due (≤7 L1, 8–14 L2, >14 L3); missed 2+ runs → L3; Crown Jewel bumps one level.
- Phases stay locked: carry-over items keep their original `phase` (history), and
  `COMPARISON.carryover.recovery_load` tells you how many items / points each recovery phase now absorbs.
  Show that load on the receiving phase card so its owners see the extra work.

## 6. Dashboard

**Highlight everywhere (tracking runs):**
- Section A2 tile **"Missed from past phases"** (`#FF4B4B`): `COMPARISON.counts.carryover` items ·
  `carryover_pts_at_risk` pts at risk, plus a small `#71FFC6` "Recovered since last run: N". Click → Carry-over tab.
- Phase cards of past-due phases: a red strip "⚠ N missed · −X pts not realized · status". The receiving phase
  card shows "+N carried in (+X pts)".
- In Tabs 1–3, carry-over rows get a left border `#FF4B4B` and a badge `Missed F1 · 9d` (tooltip: type,
  escalation). Ticket-only gaps (`Fixed — ticket still open`) use `#E7FF00` instead — process, not risk.
- Section D chart: add a dashed red **"Projected with carry-over"** line from `phase_impact[].projected_score`
  alongside planned and actual.

**Carry-over tab** — a 4th tab in every phase detail (filtered to items missed in that phase) and a global
"All past phases" view reachable from the A2 tile. Top to bottom:

1. **Impact on targets** table, one row per phase from `phase_impact`:
   Phase · Due · Target score · Planned score · Projected with carry-over · Actual now · Gap (pts) · Status chip
   (On track `#71FFC6`, At risk `#E7FF00`, Will miss `#FF4B4B`) · "If recovered: −P%".
   Under it one sentence per phase that misses, e.g. *"F2 target 480 — projected 565: 85 pts short unless the
   3 carried-over items are closed by 22 Sep."*
2. **Breakdown** chips by `carryover_type` and a small bar per owner (`by_owner` — the Tenable-tag owner, "No owner tag" last: items, pts at risk) — who
   holds the gap.
3. **Items table**, sorted by `score_delta_at_risk` desc then `days_past_due` desc:
   Plugin ID · Plugin name · Asset · Locator · Missed phase · Days past due · Runs missed · Type · Tenable state ·
   Ticket # / status · Owner · Pts at risk · Recovery phase · Recovery due · Escalation · Recovery action ·
   **Recovery plan** (editable) · **Recovery due override** (editable).
   Crown Jewel rows `#FF8837` name; runs missed ≥ 2 shown in bold red.
4. Export: "Download carry-over (CSV)" with the table columns; the main tracker downloads already include the
   carry-over and recovery fields (tracker-schema.md §8 — add `recovery_plan` and `recovery_due_override` to the
   editable/imported user columns).

On baseline runs the tab shows "No past-due phases yet — first check on [F1 due date]".

## 7. Executive summary lines (Section F, tracking runs)

- "[N] items from past phases were not closed, holding back [X] points ([P]% of the baseline). [R] were
  recovered since the last run."
- For the first phase that misses: "Phase [k] ([date]) will land at [projected] vs. target [target] unless the
  carried-over items are closed by [recovery due]." If all phases are on track, say so plainly.
- Name the biggest holder from `by_owner` and the dominant `carryover_type` (e.g. "mostly blocked OT changes").
- Items at L3 escalation: list up to 3 by asset name and plugin — these are the ones the CISO should ask about.
