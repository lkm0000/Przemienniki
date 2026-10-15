"""Merge and deduplicate repeaters from multiple sources."""

from __future__ import annotations

import logging
from collections import defaultdict

from src.models import Repeater

logger = logging.getLogger(__name__)

FREQ_TOLERANCE_KHZ = 5.0


def _freq_close(a: float, b: float) -> bool:
    """Check if two frequencies are within tolerance."""
    return abs(a - b) * 1000 <= FREQ_TOLERANCE_KHZ


def _is_newer(a: Repeater, b: Repeater) -> bool:
    """Return True if a has a more recent 'updated' than b."""
    if not a.updated:
        return False
    if not b.updated:
        return True
    return a.updated > b.updated


def _fill_fields(target: Repeater, source: Repeater) -> None:
    """Fill empty fields in target from source."""
    fields = [
        "latitude", "longitude", "qth_locator", "qth_city",
        "agl_m", "asl_m", "ctcss", "dcs_code", "color_code",
        "access_text", "dstar_module", "dmr_id", "dmr_network",
    ]
    for field in fields:
        if getattr(target, field) is None and getattr(source, field) is not None:
            setattr(target, field, getattr(source, field))


def _check_conflicts(a: Repeater, b: Repeater) -> list[str]:
    """Return descriptions of conflicting fields."""
    conflicts = []
    if a.ctcss and b.ctcss and a.ctcss != b.ctcss:
        conflicts.append(f"CTCSS: {a.source}={a.ctcss} vs {b.source}={b.ctcss}")
    if a.color_code and b.color_code and a.color_code != b.color_code:
        conflicts.append(f"CC: {a.source}={a.color_code} vs {b.source}={b.color_code}")
    return conflicts


def merge_repeaters(repeaters: list[Repeater]) -> list[Repeater]:
    """Merge repeaters: group by (call, band, mode), deduplicate."""
    groups: dict[tuple, list[Repeater]] = defaultdict(list)

    for rpt in repeaters:
        groups[rpt.merge_key()].append(rpt)

    merged: list[Repeater] = []

    for key, group in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1].value, kv[0][2].value)):
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Within a group, cluster by TX frequency (within tolerance)
        clusters: list[list[Repeater]] = []
        for rpt in sorted(group, key=lambda r: r.tx_mhz):
            placed = False
            for cluster in clusters:
                if _freq_close(rpt.tx_mhz, cluster[0].tx_mhz):
                    cluster.append(rpt)
                    placed = True
                    break
            if not placed:
                clusters.append([rpt])

        for cluster in clusters:
            if len(cluster) == 1:
                merged.append(cluster[0])
                continue

            # Pick the most recent entry as winner
            cluster.sort(key=lambda r: (r.updated or "", r.source), reverse=True)
            winner = cluster[0]

            # Fill from others
            all_notes = []
            for other in cluster[1:]:
                conflicts = _check_conflicts(winner, other)
                if conflicts:
                    all_notes.extend(conflicts)
                _fill_fields(winner, other)

            if all_notes:
                existing = winner.notes or ""
                winner.notes = "; ".join(filter(None, [existing] + all_notes))

            # Mark as merged
            sources = sorted({r.source for r in cluster if r.source})
            if len(sources) > 1:
                winner.source = "+".join(sources)

            merged.append(winner)

    logger.info("Merged %d records → %d", len(repeaters), len(merged))
    return merged
