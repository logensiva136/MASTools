# MASTools

An open-source mobile app security testing tool that tracks and reports
against **OWASP MASVS** (what to verify), **MASTG** (how to test it), and
**MASWE** (the weaknesses behind each control) — for both Android and iOS
apps.

It is not a MobSF replacement for automated scanning depth; it's a
checklist-and-findings workbench: upload an app, work through the MASVS
control matrix (auto-filled where a static check can decide it, manual
everywhere else), attach evidence, and generate a report that cites the
exact MASVS/MASTG/MASWE IDs behind every result.

## Stack

| Layer     | Tech                                             |
|-----------|---------------------------------------------------|
| Frontend  | React + Vite + TypeScript                          |
| Backend   | FastAPI + SQLAlchemy + Alembic                     |
| Worker    | Celery, with apktool / jadx / Java in its image    |
| Broker    | Redis                                              |
| Database  | PostgreSQL                                         |
| Runtime   | Docker Compose (built for Docker Desktop on Windows, WSL2 backend) |

## Project layout

```
backend/    FastAPI app: models, API routes, Alembic migrations
worker/     Celery tasks + static analysis checks (manifest, permissions, ...)
frontend/   React/Vite dashboard: control matrix, uploads, reports
data/       Versioned MASVS/MASTG/MASWE catalog (YAML), loaded into Postgres
```

## Running it (Windows + Docker Desktop)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
   with the WSL2 backend enabled.
2. Copy the environment template and adjust if needed:
   ```powershell
   copy .env.example .env
   ```
3. Build and start everything:
   ```powershell
   docker compose up --build
   ```
4. Once the stack is up:
   - Frontend: http://localhost:5173
   - Backend API docs: http://localhost:8000/docs
5. On first run, the backend seeds the MASVS/MASTG/MASWE catalog from
   `data/catalog/` automatically (see `backend/app/services/catalog_loader.py`).

## Current scope (v1)

- Projects → Apps (APK/IPA upload) → Test Runs.
- Full MASVS v2 control matrix with linked MASTG test cases and MASWE IDs.
- Manual result recording (pass / fail / N/A / pending) with evidence & notes.
- One automated static check end-to-end: Android manifest & permission
  analysis, mapped to the relevant MASVS-PLATFORM / MASTG-TEST entries.
- Markdown/HTML report generation per test run.

**Not yet implemented** (tracked as follow-up work):
- Additional static checks (hardcoded secrets, network security config,
  binary/native analysis via apktool+jadx output).
- Dynamic testing / instrumentation (Frida, objection) — the `TestRun` and
  `ControlResult` models already have the fields this would populate; see
  `worker/checks/README.md` for the intended hook point.
- Multi-user auth (currently single-user, no login).
- PDF report export (HTML report is designed to be print-to-PDF in the
  meantime).

**Known limitation:** automated check results are only backfilled into a
test run's `ControlResult` rows at the moment `POST /apps/{id}/scan`
finishes. If you create a test run *after* a scan already ran, re-trigger
the scan once to populate that run's automated fields — `create_test_run`
does not currently backfill from pre-existing `extracted_metadata`.

## Updating the MASVS/MASTG/MASWE catalog

The catalog is data, not code. To move to a newer OWASP release, edit the
YAML files under `data/catalog/`, bump `CATALOG_VERSION` in `.env`, and
restart the backend — it re-seeds idempotently (it upserts rows, keyed by
`code` + `version`). See `data/catalog/README.md`.
