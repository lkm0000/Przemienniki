"""Parser for mapy73.pl YAML repeater database.

Clones the git repo and iterates over db/!dziedzictwo-narodowe/SR*.yaml files.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import yaml

from src.maidenhead import locator_to_latlon
from src.models import Band, Mode, Repeater, Status

logger = logging.getLogger(__name__)

REPO_URL = "https://github.com/Hotel-Foxtrot-Tango-Echo/przemienniki-mapy73pl.git"
DB_DIR = "db/!dziedzictwo-narodowe"

# Mode letter → Mode enum.  Letters d, i, j are network overlays, not modes.
_MODE_MAP: dict[str, Mode] = {
    "a": Mode.FM,
    "b": Mode.DSTAR,
    "c": Mode.ATV,
    "e": Mode.DMR,
    "f": Mode.APCO25,
    "g": Mode.C4FM,
    "h": Mode.TETRA,
}

_NETWORK_LETTERS = {"d", "i", "j"}  # Echolink, FM-Link, FM-Poland

# Status string → Status enum (mapy73 encoding)
_STATUS_MAP: dict[str, Status] = {
    "1": Status.PLANNED,
    "2": Status.BUILDING,
    "3": Status.TESTING,
    "4": Status.ACTIVE,
    "5": Status.UNKNOWN,
    "6": Status.INACTIVE,
}

_BAND_KEY_MAP: dict[str, Band] = {
    "6m": Band.B_6M,
    "2m": Band.B_2M,
    "70cm": Band.B_70CM,
    "23cm": Band.B_23CM,
    "13cm": Band.B_13CM,
}


def clone_or_update(work_dir: Path) -> Path:
    """Clone (or pull) the mapy73 repo. Returns path to the repo root."""
    repo_dir = work_dir / "przemienniki-mapy73pl"
    if (repo_dir / ".git").is_dir():
        logger.info("Updating existing mapy73 clone")
        subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "--ff-only"],
            check=True, capture_output=True, text=True,
        )
    else:
        logger.info("Cloning mapy73 repo")
        repo_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth=1", REPO_URL, str(repo_dir)],
            check=True, capture_output=True, text=True,
        )
    return repo_dir


def _resolve_mode(t_code: str) -> list[Mode]:
    """Resolve a mapy73 type code (possibly combined like 'aj') into Mode(s).

    Network-only letters (d, i, j) contribute FM as base mode.
    """
    modes: list[Mode] = []
    has_network_only = False
    for ch in t_code:
        if ch in _MODE_MAP:
            modes.append(_MODE_MAP[ch])
        elif ch in _NETWORK_LETTERS:
            has_network_only = True
    # If only network letters were present, base mode is FM
    if not modes and has_network_only:
        modes.append(Mode.FM)
    return modes if modes else [Mode.FM]


def _parse_access(rx_block: dict) -> dict:
    """Extract access info from an rx block's 't' array."""
    result: dict = {}
    tones = rx_block.get("t")
    if not tones or not isinstance(tones, list):
        return result

    parts = []
    for item in tones:
        if not isinstance(item, dict):
            continue
        for key, val in item.items():
            if key == "a":
                parts.append("carrier")
            elif key == "b":
                parts.append("1750Hz")
            elif key == "c":
                try:
                    result["ctcss"] = float(val)
                except (ValueError, TypeError):
                    pass
                parts.append(f"CTCSS {val}")
            elif key == "d":
                try:
                    result["dcs_code"] = int(val)
                except (ValueError, TypeError):
                    pass
                parts.append(f"DCS {val}")
            elif key == "e":
                parts.append(f"DTMF {val}")
            elif key == "f":
                try:
                    result["color_code"] = int(val)
                except (ValueError, TypeError):
                    pass
                parts.append(f"CC{val}")

    if parts:
        result["access_text"] = ", ".join(parts)
    return result


def _parse_location(loc_data: dict) -> dict:
    """Extract location fields from a mapy73 h: entry."""
    result: dict = {}
    if "a" in loc_data:
        try:
            result["latitude"] = float(loc_data["a"])
        except (ValueError, TypeError):
            pass
    if "o" in loc_data:
        try:
            result["longitude"] = float(loc_data["o"])
        except (ValueError, TypeError):
            pass
    if "p" in loc_data:
        result["qth_city"] = str(loc_data["p"])
    if "g" in loc_data:
        try:
            result["agl_m"] = float(loc_data["g"])
        except (ValueError, TypeError):
            pass
    if "e" in loc_data:
        try:
            result["asl_m"] = float(loc_data["e"])
        except (ValueError, TypeError):
            pass
    return result


def parse_file(path: Path, callsign: str) -> list[Repeater]:
    """Parse a single mapy73 YAML file into Repeater records."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        return []

    freq_section = data.get("x")
    if not freq_section or not isinstance(freq_section, dict):
        return []

    locations = data.get("h", {})
    if not isinstance(locations, dict):
        locations = {}

    repeaters: list[Repeater] = []

    for band_key, entries in freq_section.items():
        band = _BAND_KEY_MAP.get(band_key, Band.OTHER)
        if not isinstance(entries, list):
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            rx_block = entry.get("rx", {})
            tx_block = entry.get("tx", {})
            if not isinstance(rx_block, dict) or not isinstance(tx_block, dict):
                continue

            rx_freq = rx_block.get("f")
            tx_freq = tx_block.get("f")
            if rx_freq is None or tx_freq is None:
                continue

            try:
                rx_mhz = float(rx_freq)
                tx_mhz = float(tx_freq)
            except (ValueError, TypeError):
                continue

            status = _STATUS_MAP.get(str(entry.get("s", "5")), Status.UNKNOWN)

            # Resolve location
            loc_hash = str(entry.get("h", ""))
            loc_fields: dict = {}
            if loc_hash and loc_hash in locations:
                loc_fields = _parse_location(locations[loc_hash])

            # Resolve access from rx block
            access_fields = _parse_access(rx_block)

            # Resolve mode(s) — can produce multiple Repeater records
            t_code = str(entry.get("t", "a"))
            modes = _resolve_mode(t_code)

            for mode in modes:
                rpt = Repeater(
                    call=callsign,
                    tx_mhz=tx_mhz,
                    rx_mhz=rx_mhz,
                    band=band,
                    mode=mode,
                    status=status,
                    source="mapy73",
                    **loc_fields,
                    **access_fields,
                )
                # D-STAR module assignment
                if mode == Mode.DSTAR:
                    if band == Band.B_70CM:
                        rpt.dstar_module = "B"
                    elif band == Band.B_2M:
                        rpt.dstar_module = "C"
                    elif band == Band.B_23CM:
                        rpt.dstar_module = "A"

                repeaters.append(rpt)

    return repeaters


def fetch_and_parse(work_dir: Path) -> list[Repeater]:
    """Clone repo and parse all Polish repeater YAML files."""
    repo_dir = clone_or_update(work_dir)
    db_path = repo_dir / DB_DIR

    if not db_path.is_dir():
        logger.warning("DB directory not found: %s", db_path)
        return []

    repeaters: list[Repeater] = []
    yaml_files = sorted(db_path.glob("SR*.yaml"))
    logger.info("Found %d SR*.yaml files in mapy73", len(yaml_files))

    for yaml_file in yaml_files:
        callsign = yaml_file.stem
        try:
            rpts = parse_file(yaml_file, callsign)
            repeaters.extend(rpts)
        except Exception:
            logger.exception("Error parsing %s", yaml_file.name)

    logger.info("Parsed %d repeater records from mapy73", len(repeaters))
    return repeaters
