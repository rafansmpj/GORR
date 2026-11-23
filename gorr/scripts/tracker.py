#!/usr/bin/env python3
"""
GORR remediation tracker — builds and merges the ticket tracker (JSON + CSV)
that links each prioritized finding (plugin x asset) to an owner, ticket and status.

Usage
-----
Baseline run (first execution, no tracker uploaded):
    python tracker.py --current current.json --out-dir /mnt/user-data/outputs

Tracking run (user uploaded a filled tracker .json or .csv):
    python tracker.py --current current.json --previous /mnt/user-data/uploads/gorr_tracker.csv \
                      --out-dir /mnt/user-data/outputs

Carry-over: on tracking runs, every item whose phase due date has passed but that is not
(fixed in Tenable AND ticket closed) is marked carryover=true, classified, given a recovery phase/date
and an escalation level, and its Exposure Score delta is counted "at risk" against each phase target.
See references/carryover.md.

Outputs (in --out-dir):
    gorr_tracker.json      full state: cycle metadata, run history, items  (embed this in the HTML)
    gorr_tracker.csv       one row per item, UTF-8 with BOM (opens cleanly in Excel)
    gorr_comparison.json   delta vs. previous run (fixed / still open / new / reopened / unverified / flags)

Owner: the accountable owner of every item is taken from the asset's Tenable tag in the owner tag
category (current.json "owner_tag_category" + "asset_tags"), recomputed every run. The tracker's
"owner" column is only used for assets that carry no owner tag. See tracker-schema.md §10.

The script never talks to Tenable. It only reshapes data Claude already collected (read-only).
See references/tracker-schema.md for the full input/output contract.
"""
import argparse
import csv
import io
import json
import os
import sys
from datetime import date, datetime, timedelta

SCHEMA_VERSION = "gorr-tracker/1.2"   # 1.2 adds owner-from-Tenable-tag fields; 1.1 carry-over; 1.0/1.1 files still load
CYCLE_DAYS = 30
PHASE_WINDOWS = {1: 7, 2: 14, 3: 21, 4: 30}          # due = cycle_start + N days
PHASE_TARGETS = {1: 10, 2: 20, 3: 30, 4: 40}         # cumulative % reduction

# Columns the user fills in (always preserved from the uploaded tracker)
USER_FIELDS = ["owner", "assignee", "ticket_id", "ticket_url", "ticket_status", "due_date_override", "notes",
               "recovery_plan", "recovery_due_override"]

# Carry-over (missed from a past-due phase) — recomputed every tracking run, see references/carryover.md
CARRYOVER_FIELDS = ["carryover", "carryover_type", "missed_phase", "days_past_due", "carryover_runs",
                    "first_missed_on", "recovered_on", "score_delta_at_risk", "recovery_target_phase",
                    "recovery_due_date", "recovery_action", "escalation_level"]

CSV_COLUMNS = [
    "item_key", "phase", "phase_due_date",
    "plugin_id", "plugin_name", "plugin_source", "action_id", "action_name", "cves", "vpr", "severity", "fix_type",
    "asset_id", "asset_name", "asset_type", "locator", "acr", "crown_jewel",
    "suggested_owner_team", "est_score_delta",
    "owner", "owner_source", "owner_tag",
    "assignee", "ticket_id", "ticket_url", "ticket_status", "due_date_override", "notes",
    "tenable_state", "flag", "first_seen_run", "last_verified_at",
    "carryover", "carryover_type", "missed_phase", "days_past_due", "carryover_runs", "first_missed_on",
    "recovered_on", "score_delta_at_risk", "recovery_target_phase", "recovery_due_date", "recovery_action",
    "escalation_level", "recovery_plan", "recovery_due_override",
    "cycle_id", "cycle_start", "next_run_date", "baseline_exposure_score",
]

# Owner from Tenable tags (tracker-schema.md §10)
OWNER_FIELDS = ["owner_source", "owner_tag"]
OWNER_FROM_TAG = "Tenable tag"
OWNER_MULTI = "Tenable tag (multiple)"
OWNER_MANUAL = "Manual (no owner tag)"
OWNER_UNTAGGED = "Untagged"
NO_OWNER_LABEL = "No owner tag"
# Category names auto-detected as the owner category when none is configured (lower-case, accent-free match)
OWNER_CATEGORY_KEYWORDS = ["owner", "dono", "responsavel", "responsible", "accountable", "custodian",
                           "team", "time", "squad", "department", "departamento", "business unit", "unidade de negocio",
                           "bu", "area", "diretoria", "gerencia", "事業部", "部署"]

TICKET_STATUSES = ["Not started", "Assigned", "In progress", "Blocked",
                   "Resolved", "Risk accepted", "False positive"]

# Lenient mapping so hand-filled spreadsheets (EN/PT, any case) normalize cleanly
STATUS_SYNONYMS = {
    "": "Not started", "not started": "Not started", "new": "Not started", "open": "Not started",
    "todo": "Not started", "to do": "Not started", "nao iniciado": "Not started", "não iniciado": "Not started",
    "aberto": "Not started", "pendente": "Not started",
    "assigned": "Assigned", "atribuido": "Assigned", "atribuído": "Assigned",
    "in progress": "In progress", "in-progress": "In progress", "wip": "In progress", "working": "In progress",
    "em andamento": "In progress", "em progresso": "In progress", "andamento": "In progress",
    "blocked": "Blocked", "on hold": "Blocked", "bloqueado": "Blocked", "impedido": "Blocked",
    "resolved": "Resolved", "done": "Resolved", "fixed": "Resolved", "closed": "Resolved", "completed": "Resolved",
    "resolvido": "Resolved", "concluido": "Resolved", "concluído": "Resolved", "corrigido": "Resolved",
    "fechado": "Resolved",
    "risk accepted": "Risk accepted", "accepted": "Risk accepted", "risco aceito": "Risk accepted",
    "false positive": "False positive", "fp": "False positive", "falso positivo": "False positive",
}

CLOSED_BY_USER = {"Resolved", "Risk accepted", "False positive"}


# ----------------------------------------------------------------------------- helpers
def parse_day(value):
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def iso(d):
    return d.isoformat() if d else ""


def item_key(plugin_id, asset_id):
    return f"{str(plugin_id).strip()}:{str(asset_id).strip()}"


def normalize_status(raw):
    s = (raw or "").strip()
    mapped = STATUS_SYNONYMS.get(s.lower())
    if mapped:
        return mapped, None
    for canon in TICKET_STATUSES:
        if s.lower() == canon.lower():
            return canon, None
    return s, f"Unrecognized ticket_status '{s}' kept as-is"


def load_previous(path):
    """Accept the tracker JSON produced by this script or the CSV (possibly edited in Excel)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig", errors="replace")
    if path.lower().endswith(".json") or text.lstrip().startswith("{"):
        data = json.loads(text)
        return data.get("cycle", {}), data.get("runs", []), data.get("items", [])

    # CSV: sniff delimiter (Excel pt-BR saves with ';')
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";" if sample.count(";") > sample.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows]
    rows = [r for r in rows if r.get("plugin_id") and r.get("asset_id")]
    cycle = {}
    if rows:
        r0 = rows[0]
        cycle = {"cycle_id": r0.get("cycle_id", ""), "cycle_start": r0.get("cycle_start", ""),
                 "next_run_date": r0.get("next_run_date", ""),
                 "baseline_exposure_score": _num(r0.get("baseline_exposure_score"))}
    # CSV carries no run history; the comparison still works from item rows
    return cycle, [], rows


def _float(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _truthy(v):
    return str(v).strip().lower() in ("true", "1", "yes", "sim", "y")


def _num(v):
    try:
        return float(v) if "." in str(v) else int(v)
    except (TypeError, ValueError):
        return None


def phase_due(cycle_start, phase):
    try:
        p = int(phase)
    except (TypeError, ValueError):
        return ""
    if p not in PHASE_WINDOWS or not cycle_start:
        return ""
    return iso(cycle_start + timedelta(days=PHASE_WINDOWS[p]))


def base_item(f):
    return {
        "item_key": item_key(f["plugin_id"], f["asset_id"]),
        "phase": f.get("phase", ""),
        "plugin_id": str(f["plugin_id"]),
        "plugin_name": f.get("plugin_name", ""),
        "plugin_source": f.get("plugin_source", ""),      # Nessus / NNM / WAS / OT / Third-party
        "action_id": f.get("action_id", ""),              # remediation action grouping (not an ID replacement)
        "action_name": f.get("action_name", ""),
        "cves": ",".join(f["cves"]) if isinstance(f.get("cves"), list) else f.get("cves", ""),
        "vpr": f.get("vpr", ""),
        "severity": f.get("severity", ""),
        "fix_type": f.get("fix_type", ""),
        "asset_id": str(f["asset_id"]),
        "asset_name": f.get("asset_name", ""),
        "asset_type": f.get("asset_type", ""),
        "locator": f.get("locator", ""),
        "acr": f.get("acr", ""),
        "crown_jewel": bool(f.get("crown_jewel", False)),
        "suggested_owner_team": f.get("suggested_owner_team", ""),
        "est_score_delta": f.get("est_score_delta", ""),  # this item's share of the action's Exposure Score delta
        **{k: "" for k in USER_FIELDS},
        **{k: "" for k in OWNER_FIELDS},
        **{k: "" for k in CARRYOVER_FIELDS},
    }


# ----------------------------------------------------------------------------- owner from Tenable tags
def _fold(text):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode() or str(text)
    return t.strip().lower()


def _parse_tags(raw):
    """Accept ["Cat:Value", ...], [{"category":..,"value":..}, ...] or {"Cat": ["v1","v2"]} -> [(cat, value)]."""
    out = []
    if isinstance(raw, dict):
        for cat, vals in raw.items():
            for v in (vals if isinstance(vals, list) else [vals]):
                out.append((str(cat).strip(), str(v).strip()))
        return out
    if isinstance(raw, str):
        raw = [t for t in raw.replace(";", ",").split(",") if t.strip()]
    for t in raw or []:
        if isinstance(t, dict):
            cat = t.get("category") or t.get("category_name") or t.get("key") or ""
            val = t.get("value") or t.get("value_name") or ""
            out.append((str(cat).strip(), str(val).strip()))
        elif ":" in str(t):
            cat, val = str(t).split(":", 1)
            out.append((cat.strip(), val.strip()))
    return [(c, v) for c, v in out if c and v]


def detect_owner_category(asset_tags):
    """Pick the owner category by keyword when none is configured. Returns (category or None, candidates)."""
    cats = {}
    for tags in asset_tags.values():
        for c, _ in tags:
            cats[c] = cats.get(c, 0) + 1
    ranked = []
    for c, n in cats.items():
        fc = _fold(c)
        for rank, kw in enumerate(OWNER_CATEGORY_KEYWORDS):
            if fc == kw or kw in fc.replace("-", " ").replace("_", " ").split() or (len(kw) > 4 and kw in fc):
                ranked.append((rank, -n, c))
                break
    ranked.sort()
    return (ranked[0][2] if ranked else None), [c for _, _, c in ranked]


def apply_owners(items, current, warnings):
    """Owner = value(s) of the asset's tag in the owner category. Recomputed every run (tags are the source of truth).
    Returns a summary dict for COMPARISON.owner_coverage."""
    asset_tags = {}
    for aid, raw in (current.get("asset_tags") or {}).items():
        asset_tags[str(aid)] = _parse_tags(raw)
    for f in current.get("findings", []):          # per-finding tags are accepted too
        if f.get("asset_id") and f.get("asset_tags") and str(f["asset_id"]) not in asset_tags:
            asset_tags[str(f["asset_id"])] = _parse_tags(f["asset_tags"])

    cfg = current.get("owner_tag_category")
    cats = [cfg] if isinstance(cfg, str) and cfg else list(cfg or [])
    detected, candidates = None, []
    if not cats:
        detected, candidates = detect_owner_category(asset_tags)
        if detected:
            cats = [detected]
            warnings.append(f"owner_tag_category not set - auto-detected '{detected}' "
                            f"(candidates: {', '.join(candidates)}). Confirm with the user.")
        elif asset_tags:
            warnings.append("owner_tag_category not set and no owner-like tag category found - "
                            "ask the user which Tenable tag category holds the owner. Owners left untagged.")
    wanted = {_fold(c) for c in cats if c != "*"}
    any_cat = "*" in cats

    cov = {"owner_tag_category": ", ".join(cats) if cats else "", "auto_detected": bool(detected),
           "assets_total": 0, "assets_tagged": 0, "assets_untagged": 0, "assets_multi_owner": 0,
           "assets_no_tag_data": 0, "manual_owner_items": 0, "overridden_manual_owners": 0,
           "untagged_assets": [], "multi_owner_assets": []}
    by_asset = {}
    for it in items:
        aid = str(it.get("asset_id"))
        if aid not in by_asset:
            if aid in asset_tags:
                vals = sorted({v for c, v in asset_tags[aid] if any_cat or _fold(c) in wanted})
                tags = [f"{c}:{v}" for c, v in asset_tags[aid] if any_cat or _fold(c) in wanted]
                by_asset[aid] = ("data", vals, sorted(set(tags)))
            else:
                by_asset[aid] = ("missing", [], [])
        kind, vals, tags = by_asset[aid]
        prev_owner, prev_src = it.get("owner", ""), it.get("owner_source", "")

        if kind == "missing":
            # tags not collected this run (e.g. asset fixed/not returned): keep last tag-derived owner
            if prev_src in (OWNER_FROM_TAG, OWNER_MULTI):
                continue
            it["owner_source"] = OWNER_MANUAL if prev_owner else OWNER_UNTAGGED
            continue
        if vals:
            new_owner = " / ".join(vals)
            if prev_owner and prev_src not in (OWNER_FROM_TAG, OWNER_MULTI) and _fold(prev_owner) != _fold(new_owner):
                cov["overridden_manual_owners"] += 1
                note = f"Manual owner '{prev_owner}' replaced by Tenable tag"
                if note not in (it.get("notes") or ""):
                    it["notes"] = (it.get("notes", "") + " | " if it.get("notes") else "") + note
            it["owner"] = new_owner
            it["owner_source"] = OWNER_MULTI if len(vals) > 1 else OWNER_FROM_TAG
            it["owner_tag"] = "; ".join(tags)
        else:
            if prev_src in (OWNER_FROM_TAG, OWNER_MULTI):   # tag was removed in Tenable since last run
                it["owner"] = ""
            it["owner_tag"] = ""
            it["owner_source"] = OWNER_MANUAL if it.get("owner") else OWNER_UNTAGGED
        if it["owner_source"] == OWNER_MANUAL:
            cov["manual_owner_items"] += 1

    names = {str(i.get("asset_id")): i.get("asset_name", "") for i in items}
    for aid, (kind, vals, _) in by_asset.items():
        cov["assets_total"] += 1
        if kind == "missing":
            cov["assets_no_tag_data"] += 1
        elif not vals:
            cov["assets_untagged"] += 1
            cov["untagged_assets"].append({"asset_id": aid, "asset_name": names.get(aid, "")})
        else:
            cov["assets_tagged"] += 1
            if len(vals) > 1:
                cov["assets_multi_owner"] += 1
                cov["multi_owner_assets"].append({"asset_id": aid, "asset_name": names.get(aid, ""), "owners": vals})
    denom = cov["assets_total"] - cov["assets_no_tag_data"]
    cov["pct_tagged"] = round(100 * cov["assets_tagged"] / denom, 1) if denom else 0.0
    if cov["assets_untagged"]:
        warnings.append(f"{cov['assets_untagged']} asset(s) have no owner tag in '{cov['owner_tag_category']}' - "
                        "tag them in Tenable (or fill the owner column) so every item has an accountable owner.")
    if cov["assets_multi_owner"]:
        warnings.append(f"{cov['assets_multi_owner']} asset(s) carry more than one owner tag - owners joined with ' / '.")
    if cov["overridden_manual_owners"]:
        warnings.append(f"{cov['overridden_manual_owners']} manually typed owner(s) were replaced by the Tenable tag "
                        "(previous value kept in notes).")
    return cov


# ----------------------------------------------------------------------------- core
def build(current, previous_path, run_date):
    meta = current.get("run", {})
    findings = current.get("findings", [])
    assets_seen = current.get("assets_seen", {})          # asset_id -> last_seen ISO (for verification)
    backlog_min_vpr = float(current.get("backlog_min_vpr", 7.0))
    warnings = []

    cur_by_key = {}
    for f in findings:
        if not f.get("plugin_id") or not f.get("asset_id"):
            continue
        cur_by_key[item_key(f["plugin_id"], f["asset_id"])] = f
        assets_seen.setdefault(str(f["asset_id"]), f.get("asset_last_seen", run_date.isoformat()))

    # ---------------- baseline run
    if not previous_path:
        cycle_start = run_date
        cycle = {
            "cycle_id": f"GORR-{cycle_start.strftime('%Y%m%d')}",
            "cycle_start": iso(cycle_start),
            "next_run_date": iso(cycle_start + timedelta(days=CYCLE_DAYS)),
            "phase_due_dates": {str(p): phase_due(cycle_start, p) for p in PHASE_WINDOWS},
            "phase_targets_pct": {str(p): v for p, v in PHASE_TARGETS.items()},
            "baseline_exposure_score": meta.get("exposure_score"),
            "organization": meta.get("organization", ""),
        }
        items = []
        for key, f in cur_by_key.items():
            if str(f.get("phase", "")) not in {"1", "2", "3", "4"}:
                continue                       # baseline tracker only carries the 4-phase plan
            it = base_item(f)
            it.update({"ticket_status": "Not started", "tenable_state": "Open", "flag": "",
                       "first_seen_run": iso(run_date), "last_verified_at": iso(run_date)})
            it["phase_due_date"] = phase_due(cycle_start, it["phase"])
            items.append(it)
        planned = {}
        for it in items:
            planned[str(it["phase"])] = round(planned.get(str(it["phase"]), 0.0) + (_float(it["est_score_delta"]) or 0.0), 2)
        cycle["phase_planned_delta"] = planned
        comparison = {"mode": "baseline", "run_date": iso(run_date), "counts": {"total": len(items)}}
        comparison["owner_coverage"] = apply_owners(items, current, warnings)
        runs = [{"run_date": iso(run_date), "mode": "baseline", "exposure_score": meta.get("exposure_score"),
                 "open": len(items), "fixed_verified": 0}]
        return finalize(cycle, runs, items, comparison, run_date, warnings)

    # ---------------- tracking run
    cycle, runs, prev_items = load_previous(previous_path)
    cycle_start = parse_day(cycle.get("cycle_start"))
    if not cycle_start:
        warnings.append("Previous tracker had no cycle_start; using earliest first_seen_run or today.")
        firsts = [parse_day(i.get("first_seen_run")) for i in prev_items if parse_day(i.get("first_seen_run"))]
        cycle_start = min(firsts) if firsts else run_date
        cycle["cycle_start"] = iso(cycle_start)
    cycle.setdefault("cycle_id", f"GORR-{cycle_start.strftime('%Y%m%d')}")
    cycle["next_run_date"] = cycle.get("next_run_date") or iso(cycle_start + timedelta(days=CYCLE_DAYS))
    cycle.setdefault("phase_due_dates", {str(p): phase_due(cycle_start, p) for p in PHASE_WINDOWS})
    cycle.setdefault("phase_targets_pct", {str(p): v for p, v in PHASE_TARGETS.items()})
    synthetic = not runs
    if synthetic:  # CSV upload carries no history: rebuild the baseline point from the cycle
        runs = [{"run_date": iso(cycle_start), "mode": "baseline",
                 "exposure_score": cycle.get("baseline_exposure_score"),
                 "open": len(prev_items), "fixed_verified": 0}]
    last_run = None if synthetic else parse_day(runs[-1]["run_date"])
    if last_run is None:
        vals = [parse_day(i.get("last_verified_at")) for i in prev_items if parse_day(i.get("last_verified_at"))]
        last_run = max(vals) if vals else cycle_start

    counts = {k: 0 for k in ["fixed_verified", "still_open", "new", "reopened", "unverified",
                              "claimed_resolved_still_detected", "verified_fixed_ticket_open", "overdue"]}
    items, seen_keys = [], set()

    for p in prev_items:
        key = p.get("item_key") or item_key(p.get("plugin_id"), p.get("asset_id"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        it = {c: p.get(c, "") for c in CSV_COLUMNS
              if c not in ("cycle_id", "cycle_start", "next_run_date", "baseline_exposure_score")}
        it["item_key"] = key
        it["crown_jewel"] = str(p.get("crown_jewel", "")).lower() in ("true", "1", "yes", "sim")
        status, warn = normalize_status(p.get("ticket_status"))
        it["ticket_status"] = status
        if warn:
            warnings.append(f"{key}: {warn}")
        prev_state = p.get("tenable_state", "Open")

        if key in cur_by_key:
            f = cur_by_key[key]
            # refresh Tenable-side facts, keep user fields and the locked phase
            for fld in ("plugin_name", "vpr", "severity", "asset_name", "asset_type", "locator", "acr"):
                if f.get(fld) not in (None, ""):
                    it[fld] = f[fld]
            if it.get("est_score_delta") in (None, "") and f.get("est_score_delta") not in (None, ""):
                it["est_score_delta"] = f["est_score_delta"]
            if prev_state == "Fixed (verified)":
                it["tenable_state"] = "Reopened"
                counts["reopened"] += 1
            else:
                it["tenable_state"] = "Open"
                counts["still_open"] += 1
            it["last_verified_at"] = iso(run_date)
        else:
            seen = parse_day(assets_seen.get(str(it["asset_id"])))
            if prev_state == "Fixed (verified)":
                it["tenable_state"] = "Fixed (verified)"
                counts["fixed_verified"] += 1
            elif seen and seen > last_run:
                it["tenable_state"] = "Fixed (verified)"
                it["last_verified_at"] = iso(seen)
                counts["fixed_verified"] += 1
            else:
                it["tenable_state"] = "Not re-scanned"
                counts["unverified"] += 1
        items.append(it)

    # new findings since baseline -> Backlog (not re-phased mid-cycle)
    for key, f in cur_by_key.items():
        if key in seen_keys:
            continue
        try:
            vpr = float(f.get("vpr") or 0)
        except ValueError:
            vpr = 0.0
        if vpr < backlog_min_vpr and not f.get("crown_jewel"):
            continue
        it = base_item(f)
        it.update({"phase": "Backlog", "ticket_status": "Not started", "tenable_state": "New",
                   "first_seen_run": iso(run_date), "last_verified_at": iso(run_date)})
        items.append(it)
        counts["new"] += 1

    comparison = {"mode": "tracking", "run_date": iso(run_date), "previous_run_date": iso(last_run),
                  "counts": counts}
    comparison["owner_coverage"] = apply_owners(items, current, warnings)
    runs = list(runs) + [{"run_date": iso(run_date), "mode": "tracking",
                          "exposure_score": meta.get("exposure_score"),
                          "open": counts["still_open"] + counts["reopened"] + counts["new"],
                          "fixed_verified": counts["fixed_verified"]}]
    return finalize(cycle, runs, items, comparison, run_date, warnings)


# ----------------------------------------------------------------------------- carry-over
URGENT_VPR = 9.0
ADMIN_ONLY = "Fixed — ticket still open"


def _classify(it):
    """Why an item from a past-due phase is not done. None = done (fixed AND ticket closed)."""
    state, status = it.get("tenable_state"), it.get("ticket_status")
    if state == "Fixed (verified)":
        return None if status in CLOSED_BY_USER else ADMIN_ONLY
    if state == "Not re-scanned":
        return "Unverified — asset not re-scanned"
    # Open / Reopened from here on
    if status == "Resolved":
        return "Claimed resolved — still detected"
    if status in ("Risk accepted", "False positive"):
        return "Exception — still counts against target"
    if status == "Blocked":
        return "Not fixed — blocked"
    if not it.get("ticket_id") and status in ("Not started", ""):
        return "Not fixed — no ticket"
    return "Not fixed — ticket open"


ACTIONS = {
    ADMIN_ONLY: "Close the ticket — Tenable verified the fix",
    "Unverified — asset not re-scanned": "Run a credentialed re-scan of the asset to verify, then close",
    "Claimed resolved — still detected": "Validate the fix (reboot / superseding patch / all instances), re-scan with credentials",
    "Exception — still counts against target": "Document the exception and compensating control; excluded from recovery, re-plan the target",
    "Not fixed — blocked": "Apply a compensating control now (isolate, segment, disable service) and escalate the blocker",
    "Not fixed — no ticket": "Assign an owner and open a ticket today",
    "Not fixed — ticket open": "Re-plan into the recovery phase and escalate",
}
NO_RECOVERY = {ADMIN_ONLY, "Exception — still counts against target"}


def _escalation(days, runs_missed, crown_jewel):
    level = 1 if days <= 7 else 2 if days <= 14 else 3
    if runs_missed >= 2:
        level = max(level, 3)
    if crown_jewel:
        level = min(3, level + 1)
    return {1: "L1 — team lead", 2: "L2 — IT / security manager", 3: "L3 — CISO"}[level]


def compute_carryover(items, cycle, runs, run_date, comparison, warnings):
    """Mark items of past-due phases that are not fixed/closed, plan their recovery and measure the impact."""
    due = {int(p): parse_day(d) for p, d in (cycle.get("phase_due_dates") or {}).items() if parse_day(d)}
    pct = {int(p): float(v) for p, v in (cycle.get("phase_targets_pct") or PHASE_TARGETS).items()}
    baseline = _float(cycle.get("baseline_exposure_score"))
    open_phase = next((p for p in sorted(due) if due[p] >= run_date), None)   # phase still running today
    open_due = due.get(open_phase)

    # fill missing per-item deltas (trackers from gorr-tracker/1.0) with an even split of the phase increment
    missing = [it for it in items if str(it.get("phase")) in {"1", "2", "3", "4"} and _float(it.get("est_score_delta")) is None]
    if missing:
        per_phase = {}
        for it in items:
            if str(it.get("phase")) in {"1", "2", "3", "4"}:
                per_phase[str(it["phase"])] = per_phase.get(str(it["phase"]), 0) + 1
        planned = cycle.get("phase_planned_delta") or {}
        for it in missing:
            ph = str(it["phase"])
            inc = _float(planned.get(ph))
            if inc is None and baseline:
                inc = baseline * 0.10               # each phase target is a 10-point-% increment of the baseline
            it["est_score_delta"] = round((inc or 0.0) / max(per_phase.get(ph, 1), 1), 3)
        warnings.append(f"{len(missing)} items had no est_score_delta; used an even split of the phase increment "
                        "(label it 'estimated — even split' in the dashboard).")

    summary = {"total": 0, "pts_at_risk": 0.0, "recovered_since_last_run": 0, "by_type": {},
               "by_owner": {}, "open_phase": open_phase, "cycle_complete": open_phase is None,
               "phase_impact": [], "recovery_load": {}}

    for it in items:
        was_co = it.get("carryover") is True or _truthy(it.get("carryover"))
        prev_runs = int(_float(it.get("carryover_runs")) or 0)
        eff_due = parse_day(it.get("due_date_override")) or parse_day(it.get("phase_due_date"))
        in_plan = str(it.get("phase")) in {"1", "2", "3", "4"}
        kind = _classify(it) if (in_plan and eff_due and run_date > eff_due) else None

        if kind is None:
            if was_co:
                it["recovered_on"] = iso(run_date)
                summary["recovered_since_last_run"] += 1
            for k in CARRYOVER_FIELDS:
                if k != "recovered_on":
                    it[k] = ""
            it["carryover"] = False
            continue

        runs_missed = prev_runs + 1 if was_co else 1
        days = (run_date - eff_due).days
        at_risk = 0.0 if kind == ADMIN_ONLY else (_float(it.get("est_score_delta")) or 0.0)
        cj = it.get("crown_jewel") is True or _truthy(it.get("crown_jewel"))
        urgent = cj or (_float(it.get("vpr")) or 0) >= URGENT_VPR or runs_missed >= 2

        if kind in NO_RECOVERY:
            target, rdue = "—", None
        elif open_phase is None:                    # cycle over -> Phase 1 of the next cycle
            target, rdue = "Next cycle F1", run_date + timedelta(days=7)
        else:
            target = f"F{open_phase}"
            rdue = min(open_due, run_date + timedelta(days=7)) if urgent else open_due
        if kind == "Unverified — asset not re-scanned":
            rdue = run_date + timedelta(days=3)      # a re-scan is cheap: verify within 3 days
            target = target if target != "—" else f"F{open_phase}" if open_phase else "Next cycle F1"

        it.update({
            "carryover": True, "carryover_type": kind, "missed_phase": f"F{it['phase']}",
            "days_past_due": days, "carryover_runs": runs_missed,
            "first_missed_on": it.get("first_missed_on") or iso(run_date), "recovered_on": "",
            "score_delta_at_risk": round(at_risk, 3), "recovery_target_phase": target,
            "recovery_due_date": iso(rdue), "recovery_action": ACTIONS[kind],
            "escalation_level": "" if kind == ADMIN_ONLY else _escalation(days, runs_missed, cj),
        })
        # user-set recovery due date that already passed -> recovery itself slipped
        rov = parse_day(it.get("recovery_due_override"))
        if rov and rov < run_date and kind != ADMIN_ONLY:
            it["escalation_level"] = "L3 — CISO"
            it["recovery_action"] += " (recovery date already missed)"

        summary["total"] += 1
        summary["pts_at_risk"] = round(summary["pts_at_risk"] + at_risk, 2)
        summary["by_type"][kind] = summary["by_type"].get(kind, 0) + 1
        team = it.get("owner") or NO_OWNER_LABEL
        o = summary["by_owner"].setdefault(team, {"items": 0, "pts_at_risk": 0.0})
        o["items"] += 1
        o["pts_at_risk"] = round(o["pts_at_risk"] + at_risk, 2)
        if target not in ("—",):
            rl = summary["recovery_load"].setdefault(target, {"items": 0, "pts": 0.0})
            rl["items"] += 1
            rl["pts"] = round(rl["pts"] + at_risk, 2)

    # ---- impact on each phase target (cumulative)
    actual = _float(runs[-1].get("exposure_score")) if runs else None
    for p in sorted(pct):
        cum = [i for i in items if str(i.get("phase")) in {str(q) for q in range(1, p + 1)}]
        planned = round(sum(_float(i.get("est_score_delta")) or 0.0 for i in cum), 2)
        risk = round(sum(_float(i.get("score_delta_at_risk")) or 0.0 for i in cum if i.get("carryover") is True), 2)
        row = {"phase": p, "due_date": iso(due.get(p)), "past_due": bool(due.get(p) and due[p] < run_date),
               "target_pct": pct[p], "planned_reduction": planned, "pts_at_risk": risk,
               "carryover_items": sum(1 for i in cum if i.get("carryover") is True)}
        if baseline:
            tgt = round(baseline * (1 - pct[p] / 100), 1)
            proj = round(baseline - (planned - risk), 1)
            row.update({"target_score": tgt, "planned_score": round(baseline - planned, 1),
                        "projected_score": proj, "gap_pts": round(max(0.0, proj - tgt), 1),
                        "achievable_pct": round(100 * (planned - risk) / baseline, 1),
                        "if_recovered_pct": round(100 * planned / baseline, 1)})
            if risk == 0:
                row["status"] = "On track"
            elif proj <= tgt:
                row["status"] = "At risk — still reachable"
            else:
                row["status"] = "Will miss unless recovered"
            if row["past_due"] and actual is not None:
                row["actual_score_now"] = actual
        summary["phase_impact"].append(row)
    return summary


def finalize(cycle, runs, items, comparison, run_date, warnings):
    cycle_start = parse_day(cycle["cycle_start"])
    next_run = parse_day(cycle["next_run_date"])
    counts = comparison["counts"]
    for it in items:
        it["phase_due_date"] = it.get("phase_due_date") or phase_due(cycle_start, it.get("phase"))
        due = parse_day(it.get("due_date_override")) or parse_day(it.get("phase_due_date"))
        state, status = it.get("tenable_state"), it.get("ticket_status")
        flag = ""
        if state in ("Open", "Reopened") and status == "Resolved":
            flag = "Claimed resolved but still detected"
            counts["claimed_resolved_still_detected"] = counts.get("claimed_resolved_still_detected", 0) + 1
        elif state == "Fixed (verified)" and status not in CLOSED_BY_USER:
            flag = "Verified fixed — close ticket"
            counts["verified_fixed_ticket_open"] = counts.get("verified_fixed_ticket_open", 0) + 1
        elif state in ("Open", "Reopened", "New", "Not re-scanned") and due and run_date > due \
                and status not in ("Risk accepted", "False positive"):
            flag = "Overdue"
            counts["overdue"] = counts.get("overdue", 0) + 1
        it["flag"] = flag

    comparison["carryover"] = compute_carryover(items, cycle, runs, run_date, comparison, warnings)
    counts["carryover"] = comparison["carryover"]["total"]
    counts["carryover_pts_at_risk"] = comparison["carryover"]["pts_at_risk"]
    counts["recovered_since_last_run"] = comparison["carryover"]["recovered_since_last_run"]

    # per-phase rollup for the dashboard
    phases = {}
    for it in items:
        ph = str(it.get("phase") or "Backlog")
        r = phases.setdefault(ph, {"total": 0, "fixed_verified": 0, "open": 0, "not_rescanned": 0,
                                   "with_ticket": 0, "with_owner": 0, "overdue": 0, "carryover": 0,
                                   "pts_at_risk": 0.0,
                                   "by_status": {s: 0 for s in TICKET_STATUSES}})
        r["total"] += 1
        st = it.get("tenable_state")
        if st == "Fixed (verified)":
            r["fixed_verified"] += 1
        elif st == "Not re-scanned":
            r["not_rescanned"] += 1
        else:
            r["open"] += 1
        r["with_ticket"] += 1 if it.get("ticket_id") else 0
        r["with_owner"] += 1 if it.get("owner") else 0
        r["overdue"] += 1 if it.get("flag") == "Overdue" else 0
        if it.get("carryover") is True:
            r["carryover"] += 1
            r["pts_at_risk"] = round(r["pts_at_risk"] + (_float(it.get("score_delta_at_risk")) or 0.0), 2)
        r["by_status"][it.get("ticket_status")] = r["by_status"].get(it.get("ticket_status"), 0) + 1
    for r in phases.values():
        r["pct_fixed"] = round(100 * r["fixed_verified"] / r["total"], 1) if r["total"] else 0.0

    # per-owner rollup (owner = Tenable tag) for the phase-card workload and the By-owner view
    owners = {}
    for it in items:
        o = owners.setdefault(it.get("owner") or NO_OWNER_LABEL,
                              {"source": it.get("owner_source") or OWNER_UNTAGGED, "items": 0, "assets": set(),
                               "fixed_verified": 0, "open": 0, "overdue": 0, "carryover": 0, "pts_at_risk": 0.0,
                               "est_score_delta": 0.0, "by_phase": {}})
        o["items"] += 1
        o["assets"].add(str(it.get("asset_id")))
        if it.get("tenable_state") == "Fixed (verified)":
            o["fixed_verified"] += 1
        elif it.get("tenable_state") != "Not re-scanned":
            o["open"] += 1
        o["overdue"] += 1 if it.get("flag") == "Overdue" else 0
        if it.get("carryover") is True:
            o["carryover"] += 1
            o["pts_at_risk"] = round(o["pts_at_risk"] + (_float(it.get("score_delta_at_risk")) or 0.0), 2)
        o["est_score_delta"] = round(o["est_score_delta"] + (_float(it.get("est_score_delta")) or 0.0), 3)
        ph = str(it.get("phase") or "Backlog")
        o["by_phase"][ph] = o["by_phase"].get(ph, 0) + 1
    for o in owners.values():
        o["assets"] = len(o["assets"])
        o["pct_fixed"] = round(100 * o["fixed_verified"] / o["items"], 1) if o["items"] else 0.0
    comparison["owners"] = dict(sorted(owners.items(), key=lambda kv: (kv[0] == NO_OWNER_LABEL, -kv[1]["items"])))

    days_left = (next_run - run_date).days if next_run else None
    comparison["cycle_complete"] = bool(next_run and run_date >= next_run)
    comparison["days_to_next_run"] = days_left
    comparison["phases"] = phases
    comparison["warnings"] = warnings

    order = {"1": 1, "2": 2, "3": 3, "4": 4, "Backlog": 9}
    items.sort(key=lambda i: (order.get(str(i.get("phase")), 8), str(i.get("plugin_id")), str(i.get("asset_name"))))
    tracker = {"schema": SCHEMA_VERSION, "generated_at": iso(run_date), "cycle": cycle,
               "runs": runs, "ticket_statuses": TICKET_STATUSES, "items": items}
    return tracker, comparison


def write_outputs(tracker, comparison, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cyc = tracker["cycle"]
    with open(os.path.join(out_dir, "gorr_tracker.json"), "w", encoding="utf-8") as fh:
        json.dump(tracker, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "gorr_comparison.json"), "w", encoding="utf-8") as fh:
        json.dump(comparison, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "gorr_tracker.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for it in tracker["items"]:
            row = dict(it)
            row["crown_jewel"] = "true" if it.get("crown_jewel") else "false"
            row["carryover"] = "true" if it.get("carryover") is True else "false"
            row.update({"cycle_id": cyc.get("cycle_id", ""), "cycle_start": cyc.get("cycle_start", ""),
                        "next_run_date": cyc.get("next_run_date", ""),
                        "baseline_exposure_score": cyc.get("baseline_exposure_score", "")})
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--current", required=True, help="JSON with this run's findings (see tracker-schema.md)")
    ap.add_argument("--previous", help="Uploaded tracker (.json or .csv) from an earlier run")
    ap.add_argument("--out-dir", default="/mnt/user-data/outputs")
    ap.add_argument("--run-date", help="Override run date YYYY-MM-DD (defaults to today)")
    a = ap.parse_args()

    with open(a.current, encoding="utf-8-sig") as fh:
        current = json.load(fh)
    run_date = parse_day(a.run_date) if a.run_date else date.today()
    tracker, comparison = build(current, a.previous, run_date)
    write_outputs(tracker, comparison, a.out_dir)
    print(json.dumps({"mode": comparison["mode"], "items": len(tracker["items"]),
                      "counts": comparison["counts"], "cycle": tracker["cycle"],
                      "cycle_complete": comparison["cycle_complete"],
                      "days_to_next_run": comparison["days_to_next_run"],
                      "carryover": {k: comparison["carryover"][k] for k in
                                    ("total", "pts_at_risk", "recovered_since_last_run", "by_type", "open_phase")},
                      "phase_impact": [{k: r.get(k) for k in ("phase", "target_score", "projected_score", "gap_pts", "status")}
                                       for r in comparison["carryover"]["phase_impact"]],
                      "owner_coverage": {k: v for k, v in comparison["owner_coverage"].items()
                                         if k not in ("untagged_assets", "multi_owner_assets")},
                      "owners": {k: {x: v[x] for x in ("items", "assets", "fixed_verified", "overdue")}
                                 for k, v in comparison["owners"].items()},
                      "warnings": comparison["warnings"][:20]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
