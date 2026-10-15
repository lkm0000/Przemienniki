# Przemienniki PL → Icom ID-52

## Project overview

Python pipeline that fetches Polish amateur radio repeater data from two sources, merges/deduplicates, assigns voivodeships, and exports a CSV file for import into the Icom ID-52 handheld radio.

License: AGPL-3.0 (required by mapy73 data source).

## Architecture

```
Fetch (mapy73 YAML + RXF XML)
  → Parse (src/sources/mapy73.py, src/sources/rxf.py)
  → Merge/Dedup (src/merge.py)
  → Assign voivodeships (src/voivodeships.py + data/wojewodztwa.geojson)
  → Export CSV (src/exporters/icom_id52.py)
```

Entry point: `python -m src` (src/__main__.py)

## Data sources

- **mapy73.pl** — YAML files from git repo `Hotel-Foxtrot-Tango-Echo/przemienniki-mapy73pl`. Top-level keys: `x:` (frequencies by band), `h:` (locations), `r:` (cross-band), `o:` (operators). Mode codes: a=FM, b=D-STAR, e=DMR, g=C4FM. Status: "4"=active, "3"=testing, "6"=inactive.
- **przemienniki.net** — RXF XML export. `modeInt` bitmask (FM=4, DSTAR=32, DMR/MOTOTRBO=1024, C4FM=4096). `statusInt` bitmask (WORKING=1, TESTING=8).

## Key conventions

- `tx_mhz` = repeater OUTPUT (what user listens to)
- `rx_mhz` = repeater INPUT (what user transmits on)
- `offset_mhz = rx_mhz - tx_mhz` (negative = DUP-)
- Merge key: `(call.upper(), band, mode)`
- ID-52 export filters: FM + D-STAR only, 2m + 70cm only, status active + testing
- Voivodeships use ASCII names ≤16 chars (e.g. "WarmMazurskie", "Dolnoslaskie")

## Common commands

```bash
# Activate venv
source .venv/bin/activate

# Run tests (81 tests)
pytest -v

# Run full pipeline
python -m src --work-dir work --output output/przemienniki_id52.csv --force

# Install in dev mode
pip install -e ".[dev]"
```

## Dependencies

- PyYAML, requests, shapely (runtime)
- pytest (dev)
- Python >=3.11

## File structure

- `src/models.py` — Repeater dataclass, Band/Mode/Status enums
- `src/maidenhead.py` — QTH locator → (lat, lon)
- `src/sources/mapy73.py` — YAML parser + git clone
- `src/sources/rxf.py` — RXF XML parser + download
- `src/merge.py` — dedup by (call, band, mode), 5 kHz TX tolerance
- `src/voivodeships.py` — GeoJSON point-in-polygon + 20km nearest fallback
- `src/exporters/icom_id52.py` — CSV export with groups = voivodeships
- `src/__main__.py` — CLI (argparse)
- `data/wojewodztwa.geojson` — 16 Polish voivodeship polygons
- `schema/repeater.schema.json` — JSON Schema
- `tests/` — 81 tests across 6 files + fixtures

## CI/CD

- `.github/workflows/test.yml` — pytest on PR/push (Python 3.11 + 3.12)
- `.github/workflows/build.yml` — daily cron 01:17 UTC (03:17 CEST), workflow_dispatch, push to src/**, repository_dispatch. Fingerprint caching (skip if unchanged on cron). Publishes CSV to GitHub Release `latest`.
