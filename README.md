# Arcam FMJ Receivers

[![Test](https://github.com/jgus/arcam-fmj-hacs/actions/workflows/test.yml/badge.svg)](https://github.com/jgus/arcam-fmj-hacs/actions/workflows/test.yml)

A Home Assistant integration for Arcam FMJ receivers — a drop-in replacement for the built-in [arcam_fmj](https://www.home-assistant.io/integrations/arcam_fmj) integration with substantially richer control, diagnostics, and receiver configuration.

The same feature work is being upstreamed to Home Assistant core; until it lands, this repository is the way to get it now. Releases are tagged on this repo and installable via HACS.

## What you get

On top of the media player and basic power/volume/source control of the built-in integration:

- **Capability-aware entities** — controls and diagnostics are created only for features supported by the detected model and zone, with source-specific entities available only when relevant
- **Receiver setup** — friendly name, front-panel display (brightness, VFD information), audio processing (Dolby Audio mode, Dolby leveler, PLIIx panorama, dynamic-range compression), video processing (film mode, MPEG noise reduction, noise reduction, HDMI output), Room EQ profiles, model-filtered DAC filters, tone controls, subwoofer and sub-stereo trims, lip-sync delay, processor-mode input and volume, auto-shutdown interval, and volume limits (max, max turn-on, max streaming)
- **Tuner** — FM scan up/down and DAB scan buttons, FM genre, and on-screen menu state
- **Device health** — headphones connected, active input detection, DC offset and short-circuit faults, incoming video interlaced, and lifter and output-stage temperatures (two of each)
- **Remote entity** — one per supported zone, exposing the receiver's navigation, playback, numeric, colour, menu, and toggle commands through `remote.send_command`
- **Settings backup & restore** — `save_settings` and `restore_settings` services using the receiver's four-digit installer PIN
- **Richer device information** — detected model, hardware revision, firmware version, and system model

Entity availability is model-dependent: a PA720 will not show AVR-only controls, and a single-zone receiver will not get a Zone 2 media player.

## Supported receivers

The integration covers the receivers in the [`arcam-fmj`](https://github.com/jgus/arcam_fmj) library's model table:

- **AVR series** — AV860, AVR850, AVR550, AVR390, SR250, RV-6, RV-9, MC-10, AVR380, AVR450, AVR750
- **AVR+ (HDA) series** — AVR5, AVR10, AVR20, AVR30, AV40, AVR11, AVR21, AVR31, AV41
- **Stereo processors** — SDP-55, SDP-58
- **Integrated amps (SA series)** — SA10, SA20, SA30, SA750
- **Power amps (PA series)** — PA240, PA410, PA720
- **ST60**

Multi-zone models (AVR20/AVR30/AV40, AVR21/AVR31/AV41, SDP-55/SDP-58, and the multi-zone 450/860-series receivers) also expose a Zone 2 media player.

## Installation

### HACS

1. Add this repository as a **custom repository** (category: *Integration*)
2. Install **Arcam FMJ Receivers**
3. Restart Home Assistant

### Manual

1. Clone or download this repository into `config/custom_components/arcam_fmj`
2. Restart Home Assistant

## Switching from the built-in integration

This integration shares the `arcam_fmj` domain with the built-in one — only one can be active at a time, and the custom integration takes precedence. Once installed and Home Assistant is restarted, your existing `arcam_fmj` config entry is picked up as-is. If the receiver misbehaves after the switch, delete the entry and re-add the receiver (host and port, or via SSDP discovery).

## Updating

- **HACS**: check for updates, download, restart Home Assistant
- **Manual**: `git pull` in the integration directory, restart Home Assistant

Releases follow semantic versioning and are tagged on this repo; see [CHANGELOG.md](CHANGELOG.md).

## Reporting issues

Bug reports and feature requests: [open an issue](https://github.com/jgus/arcam-fmj-hacs/issues). Include your receiver model and the Home Assistant log output for the `arcam` logger.

## License

[Apache-2.0](LICENSE), matching Home Assistant core. The base integration is derived from the [Home Assistant](https://www.home-assistant.io/) core `arcam_fmj` integration; see [Upstreaming to Home Assistant core](#upstreaming-to-home-assistant-core) for provenance.

## Upstreaming to Home Assistant core

The feature work here is also being contributed to the built-in `arcam_fmj` integration in [home-assistant/core](https://github.com/home-assistant/core). Upstream review is slow, so this repo tracks core `dev` with the local changes layered on top — keeping the port clean while the PR works through review, and remaining the practical way to use the features in the meantime.

`custom_components/arcam_fmj` is copied verbatim from `homeassistant/components/arcam_fmj` at core commit `1db381611fbe5f80cf8210d5ab36b73ef9ddeaaa` (2026-08-23), with only these deviations:

- `manifest.json` gains a `version` key (required by HACS), `@jgus` as a codeowner, a pin to the current `jgus/arcam_fmj` `working` tip, and `documentation` pointing at this repo
- the integration and tests use the library's 2.x command API
- `tests/` mirrors `tests/components/arcam_fmj` from core, ported to run standalone via [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)

When porting changes back to core, diff against the corresponding upstream files; everything else should be a clean transplant.

## Development

Requires Python >= 3.14 (matching core `dev`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Snapshot tests use syrupy's amber format (`tests/snapshots/*.ambr`, mirroring core's layout via the `snapshot` fixture override in `conftest.py` — without it syrupy reads `__snapshots__/` instead and every snapshot is "missing"). Update with `pytest --snapshot-update`.
