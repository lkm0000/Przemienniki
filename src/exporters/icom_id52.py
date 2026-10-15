"""Export repeater list to Icom ID-52 CSV format."""

from __future__ import annotations

import csv
import io
import logging
import unicodedata
from pathlib import Path

from src.models import Band, Mode, Repeater, Status

logger = logging.getLogger(__name__)

CSV_HEADER = [
    "Group No", "Group Name", "Name", "Sub Name",
    "Repeater Call Sign", "Gateway Call Sign",
    "Frequency", "Dup", "Offset", "Mode",
    "TONE", "Repeater Tone", "RPT1USE",
    "Position", "Latitude", "Longitude", "UTC Offset",
]

# Allowed modes and bands for ID-52
ALLOWED_MODES = {Mode.FM, Mode.DSTAR}
ALLOWED_BANDS = {Band.B_2M, Band.B_70CM}
ALLOWED_STATUSES = {Status.ACTIVE, Status.TESTING}


def _to_ascii(text: str) -> str:
    """Transliterate Polish characters to ASCII."""
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
        "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
    }
    result = []
    for ch in text:
        if ch in replacements:
            result.append(replacements[ch])
        elif ord(ch) < 128:
            result.append(ch)
        else:
            nfkd = unicodedata.normalize("NFKD", ch)
            ascii_ch = nfkd.encode("ascii", "ignore").decode("ascii")
            result.append(ascii_ch if ascii_ch else "")
    return "".join(result)


def _make_name(rpt: Repeater) -> str:
    """Build the Name field: call + QTH, max 16 chars ASCII."""
    call = rpt.call.upper()
    city = _to_ascii(rpt.qth_city or "")
    if city:
        # Trim city to fit: call + space + city <= 16
        max_city = 16 - len(call) - 1
        if max_city > 0:
            return f"{call} {city[:max_city]}"
    return call[:16]


def _make_sub_name(rpt: Repeater) -> str:
    """Build the Sub Name field: mode + CTCSS, max 8 chars."""
    if rpt.mode == Mode.DSTAR:
        return "DV"
    if rpt.mode == Mode.FM:
        if rpt.ctcss:
            tone_str = f"{rpt.ctcss:g}"
            label = f"FM {tone_str}"
            return label[:8]
        return "FM"
    return str(rpt.mode.value)[:8]


def _format_freq(mhz: float) -> str:
    """Format frequency with 6 decimal places."""
    return f"{mhz:.6f}"


def _dup_and_offset(rpt: Repeater) -> tuple[str, str]:
    """Calculate DUP direction and offset magnitude."""
    offset = rpt.offset_mhz
    if abs(offset) < 0.0001:
        return "OFF", "0.000000"
    if offset < 0:
        return "DUP-", _format_freq(abs(offset))
    return "DUP+", _format_freq(abs(offset))


def _repeater_callsign(rpt: Repeater) -> str:
    """Build Repeater Call Sign for D-STAR (padded to 8 chars)."""
    if rpt.mode != Mode.DSTAR:
        return ""
    call = rpt.call.upper().strip()
    module = rpt.dstar_module or ("B" if rpt.band == Band.B_70CM else "C")
    # Pad call to 7 chars, append module
    padded = call.ljust(7)[:7] + module
    return padded


def _gateway_callsign(rpt: Repeater) -> str:
    """Build Gateway Call Sign for D-STAR."""
    if rpt.mode != Mode.DSTAR:
        return ""
    call = rpt.call.upper().strip()
    return call.ljust(7)[:7] + "G"


def _format_lat(lat: float | None) -> str:
    """Format latitude for ID-52 CSV."""
    if lat is None:
        return ""
    direction = "N" if lat >= 0 else "S"
    lat = abs(lat)
    degrees = int(lat)
    minutes = (lat - degrees) * 60
    return f"{degrees:d}{direction}{minutes:07.4f}"


def _format_lon(lon: float | None) -> str:
    """Format longitude for ID-52 CSV."""
    if lon is None:
        return ""
    direction = "E" if lon >= 0 else "W"
    lon = abs(lon)
    degrees = int(lon)
    minutes = (lon - degrees) * 60
    return f"{degrees:d}{direction}{minutes:07.4f}"


def _build_groups(repeaters: list[Repeater]) -> dict[str, list[Repeater]]:
    """Group repeaters by voivodeship, sorted by group name."""
    groups: dict[str, list[Repeater]] = {}
    for rpt in repeaters:
        group_name = rpt.voivodeship or "Inne"
        if group_name not in groups:
            groups[group_name] = []
        groups[group_name].append(rpt)

    # Sort repeaters within each group by call
    for group_list in groups.values():
        group_list.sort(key=lambda r: (r.call.upper(), r.mode.value))

    return dict(sorted(groups.items()))


def filter_for_id52(repeaters: list[Repeater]) -> list[Repeater]:
    """Filter repeaters to those supported by ID-52."""
    return [
        rpt for rpt in repeaters
        if rpt.mode in ALLOWED_MODES
        and rpt.band in ALLOWED_BANDS
        and rpt.status in ALLOWED_STATUSES
    ]


def _build_row(group_no: int, group_name: str, rpt: Repeater) -> list:
    """Build one ID-52 CSV row for a repeater."""
    dup, offset = _dup_and_offset(rpt)
    mode_str = "DV" if rpt.mode == Mode.DSTAR else "FM"

    tone = ""
    repeater_tone = ""
    if rpt.mode == Mode.FM and rpt.ctcss:
        tone = "TONE"
        repeater_tone = f"{rpt.ctcss:g} Hz"

    position = "Approximate" if (rpt.latitude is not None and rpt.longitude is not None) else ""

    return [
        group_no,
        group_name,
        _make_name(rpt),
        _make_sub_name(rpt),
        _repeater_callsign(rpt),
        _gateway_callsign(rpt),
        _format_freq(rpt.tx_mhz),
        dup,
        offset,
        mode_str,
        tone,
        repeater_tone,
        "Yes",
        position,
        _format_lat(rpt.latitude),
        _format_lon(rpt.longitude),
        "+1:00",
    ]


def _write_csv(output_path: Path, rows: list[list]) -> None:
    """Write header + rows to a CSV file, creating parent dirs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def export_csv(repeaters: list[Repeater], output_path: Path) -> int:
    """Export repeaters to ID-52 CSV format. Returns number of rows written."""
    filtered = filter_for_id52(repeaters)
    if not filtered:
        logger.warning("No repeaters matched ID-52 filter criteria")
        return 0

    groups = _build_groups(filtered)
    rows = [
        _build_row(group_no, group_name, rpt)
        for group_no, (group_name, group_rpts) in enumerate(groups.items(), start=1)
        for rpt in group_rpts
    ]
    _write_csv(output_path, rows)

    logger.info("Exported %d repeaters to %s (%d groups)", len(rows), output_path, len(groups))
    return len(rows)


def export_split(repeaters: list[Repeater], output_dir: Path) -> dict[str, int]:
    """Export one ID-52 CSV per voivodeship into output_dir.

    Files are named "NN_<Group Name>.csv". Group numbers match the combined
    export, so several files can be imported without groups colliding.
    Returns {file name: number of rows}.
    """
    filtered = filter_for_id52(repeaters)
    if not filtered:
        logger.warning("No repeaters matched ID-52 filter criteria")
        return {}

    groups = _build_groups(filtered)
    counts: dict[str, int] = {}
    for group_no, (group_name, group_rpts) in enumerate(groups.items(), start=1):
        file_name = f"{group_no:02d}_{group_name}.csv"
        _write_csv(output_dir / file_name, [_build_row(group_no, group_name, r) for r in group_rpts])
        counts[file_name] = len(group_rpts)

    logger.info("Exported %d voivodeship files to %s", len(counts), output_dir)
    return counts
