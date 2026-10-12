"""Loads data/catalog/*.yaml into the masvs_controls table.

Idempotent: upserts on (code, version), so re-running after editing the
YAML (or bumping CATALOG_VERSION) is safe. Run standalone with:

    python -m app.services.catalog_loader

or automatically on container start (see docker-compose.yml).
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.config import get_settings
from app.database import SessionLocal
from app.models import MasvsControl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("catalog_loader")


def load_catalog_files(catalog_dir: str) -> list[dict]:
    entries: list[dict] = []
    base = Path(catalog_dir)
    if not base.exists():
        logger.warning("Catalog directory %s does not exist; nothing to load.", catalog_dir)
        return entries

    for path in sorted(base.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        version = doc.get("version") or get_settings().catalog_version
        for i, control in enumerate(doc.get("controls", [])):
            entries.append(
                {
                    "version": version,
                    "code": control["code"],
                    "category": control["category"],
                    "title": control["title"],
                    "description": control["description"].strip(),
                    "mastg_tests": control.get("mastg_tests", []),
                    "maswe_ids": control.get("maswe_ids", []),
                    "applies_to": control.get("applies_to", ["android", "ios"]),
                    "automatable": bool(control.get("automatable", False)),
                    "sort_order": i,
                }
            )
    return entries


def seed_catalog() -> int:
    settings = get_settings()
    entries = load_catalog_files(settings.catalog_dir)
    if not entries:
        logger.info("No catalog entries found under %s; skipping seed.", settings.catalog_dir)
        return 0

    db = SessionLocal()
    upserted = 0
    try:
        for entry in entries:
            existing = (
                db.query(MasvsControl)
                .filter(MasvsControl.code == entry["code"], MasvsControl.version == entry["version"])
                .one_or_none()
            )
            if existing:
                for key, value in entry.items():
                    setattr(existing, key, value)
            else:
                db.add(MasvsControl(**entry))
            upserted += 1
        db.commit()
    finally:
        db.close()

    logger.info("Seeded/updated %d catalog controls.", upserted)
    return upserted


if __name__ == "__main__":
    seed_catalog()
