"""Parser for przemienniki.net RXF XML export."""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from src.maidenhead import locator_to_latlon
from src.models import Band, Mode, Repeater, Status

logger = logging.getLogger(__name__)

RXF_URL = "https://przemienniki.net/export/rxf.xml"

# modeInt bitmask values
_MODE_BITS: list[tuple[int, Mode]] = [
    (4, Mode.FM),
    (32, Mode.DSTAR),
    (256, Mode.ATV),
    (1024, Mode.DMR),      # MOTOTRBO
    (2048, Mode.APCO25),
    (4096, Mode.C4FM),
    (8192, Mode.TETRA),
]

# statusInt bitmask → Status
_STATUS_MAP: dict[int, Status] = {
    1: Status.ACTIVE,
    2: Status.INACTIVE,
    4: Status.UNKNOWN,
    8: Status.TESTING,
    16: Status.BUILDING,
    32: Status.PLANNED,
}


def _text(elem: ET.Element | None, tag: str) -> str:
    """Get text of a child element, or empty string."""
    child = elem.find(tag) if elem is not None else None
    return (child.text or "").strip() if child is not None else ""


def _float_or_none(elem: ET.Element | None, tag: str) -> float | None:
    """Get float value of a child element, or None."""
    val = _text(elem, tag)
    if not val:
        return None
    try:
        f = float(val)
        return f if f != 0.0 else None
    except ValueError:
        return None


def _decode_modes(mode_int: int) -> list[Mode]:
    """Decode a modeInt bitmask into a list of Mode enums."""
    modes = []
    for bit, mode in _MODE_BITS:
        if mode_int & bit:
            modes.append(mode)
    return modes if modes else [Mode.FM]


def _decode_status(status_int: int) -> Status:
    """Decode statusInt to Status enum."""
    return _STATUS_MAP.get(status_int, Status.UNKNOWN)


def _content_hash(xml_bytes: bytes) -> str:
    """Hash XML content excluding the <generated> element."""
    try:
        root = ET.fromstring(xml_bytes)
        gen = root.find("generated")
        if gen is not None:
            root.remove(gen)
        canonical = ET.tostring(root, encoding="unicode")
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except ET.ParseError:
        return hashlib.sha256(xml_bytes).hexdigest()


def download(work_dir: Path) -> tuple[Path, str]:
    """Download RXF XML. Returns (file_path, content_hash)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path = work_dir / "rxf.xml"

    logger.info("Downloading RXF from %s", RXF_URL)
    resp = requests.get(RXF_URL, timeout=60)
    resp.raise_for_status()

    xml_bytes = resp.content
    out_path.write_bytes(xml_bytes)

    content_hash = _content_hash(xml_bytes)
    logger.info("Downloaded RXF XML (%d bytes, hash=%s)", len(xml_bytes), content_hash[:12])
    return out_path, content_hash


def parse_file(path: Path) -> list[Repeater]:
    """Parse an RXF XML file into Repeater records."""
    tree = ET.parse(path)
    root = tree.getroot()

    repeaters_elem = root.find("repeaters")
    if repeaters_elem is None:
        return []

    repeaters: list[Repeater] = []
    skipped = 0

    for rpt_elem in repeaters_elem.findall("repeater"):
        call = _text(rpt_elem, "qra")
        country = _text(rpt_elem, "country").lower()

        # Filter: Polish repeaters only (country=pl AND SR prefix)
        if country != "pl" or not call.upper().startswith("SR"):
            skipped += 1
            continue

        # Frequencies
        tx_mhz = None
        rx_mhz = None
        for qrg in rpt_elem.findall("qrg"):
            freq_type = qrg.get("type", "")
            try:
                freq_val = float(qrg.text or "0")
            except ValueError:
                continue
            if freq_type == "tx":
                tx_mhz = freq_val  # repeater output
            elif freq_type == "rx":
                rx_mhz = freq_val  # repeater input

        if tx_mhz is None or rx_mhz is None:
            continue
        if tx_mhz == 0 or rx_mhz == 0:
            continue

        band = Band.from_frequency(tx_mhz)

        # Status
        try:
            status_int = int(_text(rpt_elem, "statusInt") or "4")
        except ValueError:
            status_int = 4
        status = _decode_status(status_int)

        # Modes (bitmask)
        try:
            mode_int = int(_text(rpt_elem, "modeInt") or "4")
        except ValueError:
            mode_int = 4
        modes = _decode_modes(mode_int)

        # Location
        loc_elem = rpt_elem.find("location")
        latitude = _float_or_none(loc_elem, "latitude")
        longitude = _float_or_none(loc_elem, "longitude")
        qth_locator = _text(loc_elem, "locator") if loc_elem is not None else ""
        asl_m = _float_or_none(loc_elem, "altitudeOverSea")
        agl_m = _float_or_none(loc_elem, "altitudeOverGround")

        # Fallback coordinates from locator
        if (latitude is None or longitude is None) and qth_locator:
            try:
                lat, lon = locator_to_latlon(qth_locator)
                latitude = latitude or lat
                longitude = longitude or lon
            except ValueError:
                pass

        qth_city = _text(rpt_elem, "qth")

        # Access / activation
        ctcss = None
        dcs_code = None
        access_parts = []
        for act in rpt_elem.findall("activation"):
            act_name = (act.text or "").strip()
            access_parts.append(act_name)

        for ctcss_elem in rpt_elem.findall("ctcss"):
            if ctcss_elem.get("type") == "rx":
                try:
                    ctcss = float(ctcss_elem.text or "0")
                except ValueError:
                    pass

        access_text = ", ".join(access_parts) if access_parts else None

        # Updated timestamp
        updated = _text(rpt_elem, "updated") or None

        # Create one Repeater per mode
        for mode in modes:
            rpt = Repeater(
                call=call.upper(),
                tx_mhz=tx_mhz,
                rx_mhz=rx_mhz,
                band=band,
                mode=mode,
                status=status,
                latitude=latitude,
                longitude=longitude,
                qth_locator=qth_locator or None,
                qth_city=qth_city or None,
                asl_m=asl_m,
                agl_m=agl_m,
                ctcss=ctcss,
                dcs_code=dcs_code,
                access_text=access_text,
                source="rxf",
                updated=updated,
            )

            # D-STAR module
            if mode == Mode.DSTAR:
                if band == Band.B_70CM:
                    rpt.dstar_module = "B"
                elif band == Band.B_2M:
                    rpt.dstar_module = "C"
                elif band == Band.B_23CM:
                    rpt.dstar_module = "A"

            repeaters.append(rpt)

    logger.info("Parsed %d repeater records from RXF (skipped %d non-PL)", len(repeaters), skipped)
    return repeaters


def fetch_and_parse(work_dir: Path) -> list[Repeater]:
    """Download and parse the RXF XML file."""
    try:
        path, _ = download(work_dir)
        return parse_file(path)
    except requests.RequestException as e:
        logger.warning("Failed to download RXF: %s", e)
        return []
