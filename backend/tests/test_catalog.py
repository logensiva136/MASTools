"""Guards against the three things that bit this project before: a catalog
with made-up controls, and the automated-check mapping drifting out of
sync with what the catalog claims is automatable."""
import sys

from app.services.automated_checks import AUTOMATED_CONTROL_MAPPERS
from app.services.catalog_loader import load_catalog_files


def _catalog_dir(repo_root):
    return str(repo_root / "data" / "catalog")


def test_catalog_has_24_real_masvs_v21_controls(repo_root):
    entries = load_catalog_files(_catalog_dir(repo_root))
    assert len(entries) == 24
    codes = {e["code"] for e in entries}
    # A handful of codes the old hand-maintained catalog invented and that
    # must never come back.
    assert "MASVS-STORAGE-3" not in codes
    assert "MASVS-CRYPTO-3" not in codes
    assert "MASVS-NETWORK-3" not in codes
    assert "MASVS-PLATFORM-4" not in codes
    # And a few real ones that must be present.
    for real_code in ["MASVS-CODE-4", "MASVS-RESILIENCE-4", "MASVS-PRIVACY-3"]:
        assert real_code in codes


def test_catalog_entries_match_loader_schema(repo_root):
    entries = load_catalog_files(_catalog_dir(repo_root))
    for e in entries:
        assert e["code"].startswith("MASVS-")
        assert e["category"]
        assert e["title"]
        assert isinstance(e["mastg_tests"], list)
        assert isinstance(e["maswe_ids"], list)
        assert isinstance(e["applies_to"], list) and e["applies_to"]
        assert isinstance(e["automatable"], bool)


def test_automatable_flags_match_implemented_mappers(repo_root):
    """The whole bug this guards against: generate_catalog.py's
    AUTOMATED_CONTROLS, automated_checks.AUTOMATED_CONTROL_MAPPERS, and the
    catalog's own `automatable: true` rows all have to name the exact same
    four controls, or the UI claims automation the worker doesn't do (or
    vice versa)."""
    entries = load_catalog_files(_catalog_dir(repo_root))
    automatable_codes = {e["code"] for e in entries if e["automatable"]}
    mapper_codes = set(AUTOMATED_CONTROL_MAPPERS.keys())
    assert automatable_codes == mapper_codes

    sys.path.insert(0, str(repo_root / "data" / "catalog"))
    try:
        import generate_catalog

        assert generate_catalog.AUTOMATED_CONTROLS == mapper_codes
    finally:
        sys.path.pop(0)
