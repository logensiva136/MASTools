# Static / dynamic checks

Each module here implements one analysis step and returns a plain `dict` of
findings that `tasks.py` merges into `App.extracted_metadata` and maps onto
`ControlResult` rows via `tasks.AUTOMATED_CONTROL_MAPPERS`.

## Implemented

- `manifest_check.py` — Android manifest & permissions (via Androguard):
  package/version, declared permissions, exported components, `debuggable`,
  and `usesCleartextTraffic`. Feeds MASVS-PLATFORM-1, MASVS-PLATFORM-2,
  MASVS-CODE-2, and MASVS-NETWORK-1.

## Intended next checks (not yet implemented)

- `secrets_check.py` — entropy + regex scan over decompiled sources (jadx
  output) and resources for hardcoded keys/credentials → MASVS-CRYPTO-3.
- `network_config_check.py` — parse Android Network Security Config /
  iOS ATS (Info.plist) → MASVS-NETWORK-2.
- `binary_check.py` — native library inspection (stripped symbols, PIE,
  stack protector) → MASVS-RESILIENCE-*.

## Dynamic testing hook point (not yet implemented)

Dynamic checks (Frida/objection-based SSL-pinning bypass, root/jailbreak
detection bypass, runtime storage inspection) need a live device or
emulator, which this worker container does not provision. The intended
seam is a new task, e.g. `tasks.run_dynamic_analysis(app_id, device_udid)`,
that:

1. Connects to a device reachable from the worker container (ADB over TCP,
   or a Frida server already running on the device/emulator).
2. Runs an `objection`/`frida` script per MASTG-TEST-* case.
3. Writes results through the same `ControlResult` update path used by the
   static checks (see `apply_automated_results` in `tasks.py`).

This is deliberately out of scope for v1 — it depends on a specific device
story (which emulator/device, how the worker reaches it) that needs a
decision before building against it.
