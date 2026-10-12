# Catalog data

The MASVS/MASTG/MASWE catalog lives here as YAML, not in code, so moving to a
new OWASP release is a data edit, not a migration.

## Files

- `masvs_v2.yaml` — one file per catalog version. Each entry becomes one row
  in the `masvs_controls` table.

## Important: starter set, not the full official text

`masvs_v2.yaml` currently ships a **representative starter set** covering
every MASVS v2 category (STORAGE, CRYPTO, AUTH, NETWORK, PLATFORM, CODE,
RESILIENCE, PRIVACY) with paraphrased titles/descriptions and best-effort
MASTG-TEST / MASWE ID cross-references.

Before relying on this for a real engagement:

1. Cross-check every `code`, `mastg_tests`, and `maswe_ids` entry against the
   current release at https://mas.owasp.org/MASVS/ and
   https://mas.owasp.org/MASTG/ — OWASP renumbers these between releases.
2. Fill in the remaining controls per category (this starter set is
   intentionally not exhaustive, to keep the first pass reviewable).
3. Consider pulling MASTG's own machine-readable data (the MASTG repo
   publishes structured test/control metadata) instead of hand-maintaining
   this file long-term.

## Schema (per entry)

```yaml
- code: MASVS-STORAGE-1          # unique within a version
  category: STORAGE               # STORAGE | CRYPTO | AUTH | NETWORK | PLATFORM | CODE | RESILIENCE | PRIVACY
  title: Short one-line summary
  description: >
    Longer paraphrase of what the control requires.
  mastg_tests: ["MASTG-TEST-0001"]
  maswe_ids: ["MASWE-0001"]
  applies_to: ["android", "ios"]
  automatable: false              # true if a worker check can decide this automatically
```

## Loading

`backend/app/services/catalog_loader.py` reads every `*.yaml` file in this
directory and upserts rows into `masvs_controls`, keyed on `(code,
version)`. The `version` value comes from the filename-derived or
explicitly set `CATALOG_VERSION` env var (defaults to `MASVS-v2.1`) unless
a file sets its own `version:` key at the top.
