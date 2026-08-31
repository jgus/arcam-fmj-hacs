# Changelog

Releases are tagged on this repo and summarized in GitHub releases.

## 0.1.2 — 2026-08-31

- Rewritten README: feature overview, supported receivers, installation, migration from the built-in integration, and updating docs
- Added Apache-2.0 LICENSE (matching Home Assistant core)
- `manifest.json` `documentation` now points at this repository

## 0.1.1 — 2026-08-26

- Bumped `arcam-fmj` to `8e5cd3d`

## 0.1.0 — 2026-08-25

Initial release: a drop-in replacement for the built-in `arcam_fmj` integration with:

- Media player with accurate per-source playback state (Network, USB, Bluetooth, tuner), track metadata, codec and sample-rate details, and model-aware transport controls
- Receiver setup controls: friendly name, display behaviour, source-aware VFD information, audio and video processing, Room EQ, model-filtered DAC filters, Dolby features, tone controls, trims, lip-sync delay, processor-mode input and volume, and volume limits
- Direct mode, headphone override, and Zone 1 OSD switches
- Tuner controls: FM scan up/down, DAB scan, FM genre, and menu state
- Diagnostics: headphones connected, active input detection, amplifier faults, and lifter/output-stage temperatures
- A remote entity per supported zone
- `save_settings` / `restore_settings` services using the installer PIN
- Zone 2 media player on multi-zone models
