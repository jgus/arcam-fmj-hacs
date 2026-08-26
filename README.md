# arcam-fmj-hacs

HACS drop-in replacement for the [arcam_fmj](https://www.home-assistant.io/integrations/arcam_fmj) Home Assistant integration, tracking [home-assistant/core](https://github.com/home-assistant/core) `dev` with local changes on top while they churn toward upstreaming.

## Enhancements over the built-in integration

- Capability-aware entities: controls and diagnostics are created only for features supported by the detected model and zone, with source-specific entities available only when relevant
- Richer device information, including detected model, hardware revision, firmware version, and system model
- Additional diagnostics for connected headphones, active input, amplifier faults, menu state, FM genre, and all supported temperature sensors
- Receiver setup controls for friendly name, display behavior, audio and video processing, Room EQ, DAC filters, Dolby features, tone controls, trims, lip sync, and volume limits
- FM and DAB scan controls
- Improved Network, USB, Bluetooth, and tuner presentation with accurate playback state, available track metadata, codec and sample-rate details, configured input names, and model-aware transport controls
- A remote entity for each supported zone, exposing the receiver's available navigation, playback, numeric, colour, menu, and toggle commands through `remote.send_command`
- Secure device-settings backup and restore actions using the receiver's four-digit installer PIN

## Upstream provenance

`custom_components/arcam_fmj` is copied verbatim from `homeassistant/components/arcam_fmj` at core commit `1db381611fbe5f80cf8210d5ab36b73ef9ddeaaa` (2026-08-23), with only these deviations:

- `manifest.json` gains a `version` key (required by HACS), `@jgus` as a codeowner, and pins the current `jgus/arcam_fmj` `working` tip
- the integration and tests use the library's 2.x command API
- `tests/` mirrors `tests/components/arcam_fmj` from core, ported to run standalone via [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)

When porting changes back to core, diff against the corresponding upstream files; everything else should be a clean transplant.

## Installation

1. Add this repo to HACS as a custom repository (category: Integration)
2. Install "Arcam FMJ Receivers"
3. Restart Home Assistant

The stock `arcam_fmj` integration and this one share a domain — only one may be loaded at a time.

## Development

Requires Python >= 3.14 (matching core `dev`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Snapshot tests use syrupy's amber format (`tests/snapshots/*.ambr`, mirroring core's layout via the `snapshot` fixture override in `conftest.py` — without it syrupy reads `__snapshots__/` instead and every snapshot is "missing"). Update with `pytest --snapshot-update`.
