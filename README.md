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
   If port 8000, 5173, or 5432 is already taken on your machine ("port is
   already allocated"), set `API_HOST_PORT`, `WEB_HOST_PORT`, or
   `POSTGRES_HOST_PORT` in `.env` to a free port instead — everything else
   (the frontend's API URL, CORS) adjusts automatically.
3. Build and start everything:
   ```powershell
   docker compose up --build
   ```
4. Once the stack is up:
   - Frontend: http://localhost:5173
   - Backend API docs: http://localhost:8000/docs
5. On first run, the backend seeds the MASVS/MASTG/MASWE catalog from
   `data/catalog/` automatically (see `backend/app/services/catalog_loader.py`).
6. Create an account at http://localhost:5173/login (there's no seeded
   user — the first screen you'll see is sign in / create account).

## Production deployment

`docker-compose.yml` above is for local development (hot reload, bind
mounts, host-exposed Postgres). For a real deployment, use
`docker-compose.prod.yml` instead:

```bash
cp .env.example .env
# edit .env: set a real SECRET_KEY (openssl rand -hex 32), a real
# POSTGRES_PASSWORD, BACKEND_CORS_ORIGINS, and PUBLIC_API_BASE_URL —
# docker-compose.prod.yml refuses to start if any of these are left unset
docker compose -f docker-compose.prod.yml up -d --build
```

What's different: code is baked into the images and containers run as a
non-root user (no bind mounts, no `--reload`), the frontend is a static
bundle served by nginx instead of the Vite dev server, Postgres/Redis
aren't published to the host at all, and every container runs with
`cap_drop: [ALL]`, `no-new-privileges`, and a read-only root filesystem.
Put a TLS-terminating reverse proxy (Caddy, nginx, Traefik) in front of
the `api`/`web` ports — neither container terminates TLS itself.

## Current scope (v1)

- Multi-user accounts: every project belongs to the user who created it;
  nothing is shared between accounts.
- Projects → Apps (APK/IPA upload) → Test Runs.
- Full MASVS v2.1 control matrix (24 real controls) with linked MASTG
  test cases and MASWE IDs — generated from OWASP's own source
  repositories, not hand-copied (see `data/catalog/README.md`).
- Manual result recording (pass / fail / N/A / pending) with evidence & notes.
- Four automated static checks end-to-end: Android manifest/permission
  analysis mapped to MASVS-PRIVACY-1 (permission minimization),
  MASVS-PLATFORM-1 (exported components / IPC), MASVS-RESILIENCE-4
  (debuggable flag), and MASVS-NETWORK-1 (cleartext traffic) — see
  `backend/app/services/automated_checks.py` for why each check maps to
  that particular control.
- Markdown/HTML report generation per test run.

**Not yet implemented** (tracked as follow-up work):
- Additional static checks (hardcoded secrets, network security config,
  binary/native analysis via apktool+jadx output).
- iOS static analysis — IPA upload works, but `run_static_analysis`
  doesn't branch to an iOS checker yet (Android-only today).
- Dynamic testing / instrumentation (Frida, objection) — the `TestRun` and
  `ControlResult` models already have the fields this would populate; see
  `worker/checks/README.md` for the intended hook point.
- PDF report export (HTML report is designed to be print-to-PDF in the
  meantime).

## Updating the MASVS/MASTG/MASWE catalog

The catalog is generated from OWASP's own source repositories, not hand
edited. To move to a newer OWASP release, run
`python data/catalog/generate_catalog.py`, review the diff, bump
`CATALOG_VERSION` in `.env` if the version changed, and restart the
backend — it re-seeds idempotently (it upserts rows, keyed by `code` +
`version`). See `data/catalog/README.md`.
