#!/usr/bin/env python3
"""Regenerates masvs_v2.yaml from OWASP's own source repositories, instead of
hand-maintaining the catalog. Run this whenever OWASP ships a new MASVS,
MASTG, or MASWE release.

Usage:
    pip install pyyaml
    python data/catalog/generate_catalog.py --workdir /tmp/owasp-mas

This clones (shallow) OWASP/masvs, OWASP/mastg, and OWASP/maswe into
--workdir (skips any that are already there — `git pull` them yourself
first if you want a fresher checkout), reads their current MASVS v2
controls, MASTG v2 tests-beta test cases, and MASWE weaknesses, resolves
the cross-references between them, and writes data/catalog/masvs_v2.yaml.

Why tests-beta and not tests/: as of this writing every file under MASTG's
tests/ directory is marked `status: deprecated` and points at its
tests-beta/ replacement, which is the live MASTG v2 test-writing effort.
tests-beta/ tests don't carry a direct MASVS id; they reference a MASWE
weakness instead, and MASWE's own front matter maps each weakness to the
MASVS v2 control(s) it threatens. So the resolution is:

    MASTG-TEST --(maswe field)--> MASWE --(mappings.masvs-v2)--> MASVS control

`automatable` is set to True only for the controls MASTools' worker
actually implements a static check for today (see worker/tasks.py's
AUTOMATED_CONTROL_MAPPERS) — keep AUTOMATED_CONTROLS below in sync with
that module so the catalog never claims automation the code doesn't do.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPOS = {
    "masvs": "https://github.com/OWASP/masvs",
    "mastg": "https://github.com/OWASP/mastg",
    "maswe": "https://github.com/OWASP/maswe",
}

# Keep in sync with worker/tasks.py AUTOMATED_CONTROL_MAPPERS.
AUTOMATED_CONTROLS = {"MASVS-PRIVACY-1", "MASVS-PLATFORM-1", "MASVS-RESILIENCE-4", "MASVS-NETWORK-1"}

CATEGORY_SHORT = {
    "MASVS-STORAGE": "STORAGE",
    "MASVS-CRYPTO": "CRYPTO",
    "MASVS-AUTH": "AUTH",
    "MASVS-NETWORK": "NETWORK",
    "MASVS-PLATFORM": "PLATFORM",
    "MASVS-CODE": "CODE",
    "MASVS-RESILIENCE": "RESILIENCE",
    "MASVS-PRIVACY": "PRIVACY",
}


def clone_or_skip(name: str, url: str, workdir: Path) -> Path:
    dest = workdir / name
    if dest.exists():
        print(f"  {name}: already present at {dest}, skipping clone", file=sys.stderr)
        return dest
    print(f"  {name}: cloning {url} -> {dest}", file=sys.stderr)
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        check=True,
        env={"GIT_LFS_SKIP_SMUDGE": "1"},
    )
    return dest


def front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return yaml.safe_load(m.group(1)) if m else {}


def load_controls(masvs_dir: Path) -> list[dict]:
    data = yaml.safe_load((masvs_dir / "OWASP_MASVS.yaml").read_text(encoding="utf-8"))
    controls = []
    for group in data["groups"]:
        for i, ctrl in enumerate(group["controls"]):
            controls.append({
                "id": ctrl["id"],
                "category": CATEGORY_SHORT.get(group["id"], group["id"]),
                "title": ctrl["statement"].strip(),
                "description": (ctrl.get("description") or "").strip(),
                "sort_order": i,
            })
    return controls


def load_mastg_tests(mastg_dir: Path) -> dict[str, dict]:
    """tests-beta/ tests, keyed by id. Each carries maswe references, not a
    direct MASVS id (see module docstring)."""
    tests: dict[str, dict] = {}
    for platform_dir in (mastg_dir / "tests-beta").iterdir():
        if not platform_dir.is_dir():
            continue
        for group_dir in platform_dir.iterdir():
            if not group_dir.is_dir():
                continue
            for f in group_dir.glob("MASTG-TEST-*.md"):
                fm = front_matter(f)
                test_id = f.stem
                maswe_ids = fm.get("maswe") or []
                if isinstance(maswe_ids, str):
                    maswe_ids = [maswe_ids]
                entry = tests.setdefault(test_id, {"id": test_id, "maswe_ids": set()})
                entry["maswe_ids"].update(maswe_ids)
    return tests


def load_maswe(maswe_dir: Path) -> dict[str, dict]:
    weaknesses: dict[str, dict] = {}
    for group_dir in (maswe_dir / "weaknesses").iterdir():
        if not group_dir.is_dir():
            continue
        for f in group_dir.glob("MASWE-*.md"):
            fm = front_matter(f)
            weaknesses[fm.get("id", f.stem)] = {
                "masvs_ids": (fm.get("mappings") or {}).get("masvs-v2") or [],
            }
    return weaknesses


def build_catalog(workdir: Path) -> list[dict]:
    controls = load_controls(workdir / "masvs")
    tests = load_mastg_tests(workdir / "mastg")
    weaknesses = load_maswe(workdir / "maswe")

    control_by_id = {c["id"]: c for c in controls}
    for c in controls:
        c["mastg_tests"] = set()
        c["maswe_ids"] = set()

    for wid, w in weaknesses.items():
        for cid in w["masvs_ids"]:
            if cid in control_by_id:
                control_by_id[cid]["maswe_ids"].add(wid)

    for test_id, t in tests.items():
        resolved = set()
        for wid in t["maswe_ids"]:
            w = weaknesses.get(wid)
            if w:
                resolved.update(w["masvs_ids"])
        for cid in resolved:
            if cid in control_by_id:
                control_by_id[cid]["mastg_tests"].add(test_id)

    out = []
    for c in sorted(controls, key=lambda c: (c["category"], c["sort_order"])):
        out.append({
            "code": c["id"],
            "category": c["category"],
            "title": c["title"],
            "description": c["description"],
            "mastg_tests": sorted(c["mastg_tests"]),
            "maswe_ids": sorted(c["maswe_ids"]),
            "applies_to": ["android", "ios"],
            "automatable": c["id"] in AUTOMATED_CONTROLS,
        })
    return out


def write_yaml(entries: list[dict], out_path: Path) -> None:
    header = (
        "# OWASP MASVS v2.1 catalog, generated from OWASP's own source data by\n"
        "# generate_catalog.py (masvs v2.1.0 + mastg v2.0.0 tests-beta + maswe).\n"
        "# Do not hand-edit — re-run the generator instead. See README.md.\n\n"
    )
    doc = {"version": "MASVS-v2.1", "controls": entries}
    body = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=78, allow_unicode=True)
    out_path.write_text(header + body, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", default="/tmp/owasp-mas", help="where to clone/read the OWASP repos")
    parser.add_argument(
        "--out", default=str(Path(__file__).parent / "masvs_v2.yaml"),
        help="output YAML path (default: data/catalog/masvs_v2.yaml next to this script)",
    )
    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    for name, url in REPOS.items():
        clone_or_skip(name, url, workdir)

    entries = build_catalog(workdir)
    write_yaml(entries, Path(args.out))
    unmapped = [e["code"] for e in entries if not e["mastg_tests"]]
    print(f"Wrote {len(entries)} controls to {args.out}")
    if unmapped:
        print(f"Controls with no published tests-beta test yet: {', '.join(unmapped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
