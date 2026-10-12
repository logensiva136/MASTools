"""Android manifest & permission analysis via Androguard.

No apktool/jadx shell-out needed for this particular check — Androguard
parses the binary AndroidManifest.xml directly from the APK. apktool/jadx
stay installed in the worker image for checks that need unpacked
resources or decompiled Java (see checks/README.md for what's planned).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Permissions broad/sensitive enough to flag by default if present without
# obvious justification. This is a starting heuristic, not a verdict —
# results still land as "manual_review", not an automatic fail.
SENSITIVE_PERMISSIONS = {
    "android.permission.READ_SMS",
    "android.permission.SEND_SMS",
    "android.permission.READ_CONTACTS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.READ_CALL_LOG",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
}


def analyze_apk(apk_path: str) -> dict:
    """Returns a dict of extracted facts. Raises on unparseable APKs."""
    from androguard.core.apk import APK

    apk = APK(apk_path)

    permissions = list(apk.get_permissions())
    sensitive_permissions = sorted(set(permissions) & SENSITIVE_PERMISSIONS)

    exported_activities = [a for a in apk.get_activities() if apk.get_element("activity", "exported", name=a) == "true"]
    exported_services = [s for s in apk.get_services() if apk.get_element("service", "exported", name=s) == "true"]
    exported_receivers = [r for r in apk.get_receivers() if apk.get_element("receiver", "exported", name=r) == "true"]
    exported_providers = [p for p in apk.get_providers() if apk.get_element("provider", "exported", name=p) == "true"]

    debuggable = apk.get_attribute_value("application", "debuggable") == "true"

    try:
        uses_cleartext = apk.get_attribute_value("application", "usesCleartextTraffic")
        uses_cleartext_traffic = uses_cleartext != "false"  # defaults to true below API 28 if unset
    except Exception:  # noqa: BLE001 - attribute may be absent on some manifests
        uses_cleartext_traffic = True

    return {
        "package_name": apk.get_package(),
        "version_name": apk.get_androidversion_name(),
        "min_sdk": apk.get_min_sdk_version(),
        "target_sdk": apk.get_target_sdk_version(),
        "permissions": permissions,
        "sensitive_permissions": sensitive_permissions,
        "exported_activities": exported_activities,
        "exported_services": exported_services,
        "exported_receivers": exported_receivers,
        "exported_providers": exported_providers,
        "debuggable": debuggable,
        "uses_cleartext_traffic": uses_cleartext_traffic,
    }
