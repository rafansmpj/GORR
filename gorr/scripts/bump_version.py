#!/usr/bin/env python3
"""Bump GORR skill version everywhere and move [Unreleased] into a dated release.

Usage: python scripts/bump_version.py <major|minor|patch> "one-line summary" [--status Released]
"""
import re, sys, datetime, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
kind, summary = sys.argv[1], sys.argv[2]
status = sys.argv[sys.argv.index("--status") + 1] if "--status" in sys.argv else "Released"

old = (root / "VERSION").read_text().strip()
ma, mi, pa = map(int, old.split("."))
new = {"major": f"{ma+1}.0.0", "minor": f"{ma}.{mi+1}.0", "patch": f"{ma}.{mi}.{pa+1}"}[kind]
today = datetime.date.today().isoformat()

(root / "VERSION").write_text(new + "\n")
for f, pat in (("SKILL.md", r'(\n  version: ")[^"]+(")'), ("listing.yaml", r'(\nversion: ")[^"]+(")')):
    p = root / f
    p.write_text(re.sub(pat, rf"\g<1>{new}\g<2>", p.read_text(), count=1))

schema = re.search(r'SCHEMA_VERSION = "([^"]+)"', (root / "scripts/tracker.py").read_text()).group(1)
cl = root / "CHANGELOG.md"
t = cl.read_text()
t = t.replace("|---------|------|----------------|--------|---------|\n",
              f"|---------|------|----------------|--------|---------|\n| {new} | {today} | {schema} | {status} | {summary} |\n", 1)
unrel = re.search(r"## \[Unreleased\]\n(.*?)\n---\n", t, re.S)
# drop empty section headers
lines, out = unrel.group(1).strip().splitlines(), []
for i, l in enumerate(lines):
    if l.startswith("### ") and (i + 1 == len(lines) or lines[i + 1].startswith("### ") or not lines[i + 1].strip()):
        continue
    out.append(l)
entry = f"## [{new}] — {today}\n\n" + ("\n".join(out) or f"- {summary}") + "\n\n"
t = t.replace(unrel.group(0), "## [Unreleased]\n\n### Added\n### Changed\n### Fixed\n\n---\n\n" + entry, 1)
cl.write_text(t)
print(f"{old} -> {new}  (tracker schema {schema})")
