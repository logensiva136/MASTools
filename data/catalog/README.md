# Catalog data

The MASVS/MASTG/MASWE catalog lives here as YAML, not in code, so moving to a
new OWASP release is a data refresh, not a migration.

## Files

- `masvs_v2.yaml` — one file per catalog version. Each entry becomes one row
  in the `masvs_controls` table.
- `generate_catalog.py` — regenerates `masvs_v2.yaml` directly from OWASP's
  own source repositories. **This is the only supported way to edit this
  file** — don't hand-edit it, the next regeneration will overwrite you.

## Where the data comes from

`masvs_v2.yaml` is generated, not hand-written, from:

- [OWASP/masvs](https://github.com/OWASP/masvs) (tag `v2.1.0`) — the 24
  current MASVS v2.1 controls, verbatim statement and description text.
- [OWASP/mastg](https://github.com/OWASP/mastg) (tag `v2.0.0`),
  `tests-beta/` — the current MASTG v2 test-writing effort. **Not**
  `tests/`: every file under the stable `tests/` directory is marked
  `status: deprecated` and points at its `tests-beta/` replacement, which is
  real but still incomplete (200 tests published so far, some of those
  themselves `status: placeholder` stubs).
- [OWASP/maswe](https://github.com/OWASP/maswe) — the 78 current MASWE
  weaknesses, which bridge MASTG tests to MASVS controls: a `tests-beta`
  test case references a MASWE id, and the MASWE entry's own front matter
  (`mappings.masvs-v2`) names the control(s) it threatens. The generator
  resolves this two-hop path for every test.

Three controls (`MASVS-AUTH-3`, `MASVS-PRIVACY-2`, `MASVS-PRIVACY-4`) have
MASWE weaknesses defined but no `tests-beta` test case yet, as of the
versions above — they'll show `mastg_tests: []` until OWASP publishes one.
Those have to be tested manually against the control statement and the
mapped weaknesses' own requirement text.

`automatable` is `true` only for the four controls MASTools' worker
currently has a static check for (`worker/tasks.py`'s
`AUTOMATED_CONTROL_MAPPERS`): `MASVS-PRIVACY-1` (permission minimization),
`MASVS-PLATFORM-1` (IPC / exported components), `MASVS-RESILIENCE-4`
(anti-dynamic-analysis / debuggable flag), and `MASVS-NETWORK-1` (cleartext
traffic). If you add a new automated check, update
`generate_catalog.AUTOMATED_CONTROLS` to match and regenerate — don't just
flip the YAML field by hand, or the two will drift again.

## Regenerating

```bash
pip install pyyaml
python data/catalog/generate_catalog.py --workdir /tmp/owasp-mas
git diff data/catalog/masvs_v2.yaml   # review before committing
```

This shallow-clones `OWASP/masvs`, `OWASP/mastg`, and `OWASP/maswe` into
`--workdir` (skipping any that are already there — pull them yourself
first for a fresher checkout) and overwrites `masvs_v2.yaml`. Do this
whenever OWASP ships a new MASVS, MASTG, or MASWE release — check
https://github.com/OWASP/masvs/releases first, since the version pinned in
this file's header comment may be stale.

## Schema (per entry)

```yaml
- code: MASVS-STORAGE-1          # unique within a version
  category: STORAGE               # STORAGE | CRYPTO | AUTH | NETWORK | PLATFORM | CODE | RESILIENCE | PRIVACY
  title: The app securely stores sensitive data.
  description: >
    Longer description, verbatim from OWASP MASVS.
  mastg_tests: ["MASTG-TEST-0200", ...]
  maswe_ids: ["MASWE-0001", ...]
  applies_to: ["android", "ios"]
  automatable: false              # true only if worker/tasks.py actually implements this check
```

## Loading

`backend/app/services/catalog_loader.py` reads every `*.yaml` file in this
directory and upserts rows into `masvs_controls`, keyed on `(code,
version)`. The `version` value comes from the file's own `version:` key
(falls back to the `CATALOG_VERSION` env var, default `MASVS-v2.1`, if a
file doesn't set one).
