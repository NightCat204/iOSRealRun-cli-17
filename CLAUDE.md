# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`iOSRealRun-cli-17` is a Python CLI tool that simulates GPS running routes on iOS 17+ devices via USB. It uses `pymobiledevice3` to establish a tunnel to the device and inject spoofed location data at a configurable speed.

## Setup

```shell
conda create -n iOSRealRun python=3.12
conda activate iOSRealRun
pip3 install -r requirements.txt
```

## Running

```shell
# macOS — run directly (script auto-elevates via sudo internally)
python main.py

# Windows — must run terminal as Administrator
python main.py
```

Do NOT use `sudo python3 main.py` on macOS — this switches to the system Python and loses the virtualenv dependencies.

Enable `DEBUG` env var for verbose logging: `DEBUG=1 python main.py`

## Configuration

`config.yaml` controls runtime behavior:

| Key | Description |
|-----|-------------|
| `v` | Running speed in m/s (default 3.8) |
| `routeConfig` | Path to the route file (e.g. `ZJGroute.txt`) |

Route files contain coordinate points in `{lat: ..., lng: ...}` format (BD-09 coordinate system from Baidu Maps). Only draw a single loop.

## Architecture

The program flow is strictly sequential:

1. **`main.py`** — entry point; handles root elevation, logging, and orchestrates all phases
2. **`init/init.py`** — pre-flight checks: requires root, iOS ≥ 17, USB-connected device unlocked and trusted, developer mode enabled
3. **`init/tunnel.py`** — starts a `RemoteServiceDiscovery` tunnel in a **separate subprocess** (required by `pymobiledevice3` async internals); returns `(process, address, port)` via a `multiprocessing.Queue`
4. **`init/route.py`** — reads and parses the route file into a list of `{lat, lng}` dicts
5. **`run.py`** — main simulation loop:
   - `fixLockT()` interpolates waypoints to match the target speed and a fixed time step (`dt=0.2s`)
   - `randLoc()` adds per-lap random lateral drift (divided into `n` segments) to mimic natural variance
   - `bd09Towgs84()` converts BD-09 → WGS-84 before injecting each coordinate
   - `run()` loops infinitely, randomizing speed slightly each lap (`±d` m/s variance)
6. **`driver/location.py`** — thin wrapper over `pymobiledevice3.LocationSimulation`; `set_location()` and `clear_location()`
7. **`driver/connect.py`** — all `pymobiledevice3` connection logic: USB lockdown, developer mode reveal, RSD tunnel setup
8. **`config.py`** — loads `config.yaml` at import time as a singleton `config` object

**Coordinate system**: route files use BD-09 (Baidu); iOS expects WGS-84. Conversion happens in `run.py:bd09Towgs84()` at inject time.

**Cleanup**: `Ctrl+C` is the only safe exit. The `finally` block in `main.py` always calls `clear_location()` then `process.terminate()`. Skipping this leaves the device stuck in simulated location until reboot.
