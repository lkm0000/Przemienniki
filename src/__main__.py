"""CLI entry point: orchestrate the full pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.exporters.icom_id52 import export_csv, export_split
from src.merge import merge_repeaters
from src.sources.mapy73 import fetch_and_parse as fetch_mapy73
from src.sources.rxf import fetch_and_parse as fetch_rxf
from src.voivodeships import assign_voivodeships


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="przemienniki",
        description="Polish repeater database pipeline for Icom ID-52",
    )
    parser.add_argument(
        "--work-dir", type=Path, default=Path("work"),
        help="Working directory for downloads and clones (default: work/)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/przemienniki_id52.csv"),
        help="Output CSV path (default: output/przemienniki_id52.csv)",
    )
    parser.add_argument(
        "--split-dir", type=Path, default=None,
        help="Also write one CSV per voivodeship into this directory",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Build even if fingerprint unchanged",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("pipeline")

    work_dir: Path = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)

    # --- Fetch & parse ---
    log.info("=== Fetching sources ===")

    mapy73_rpts = fetch_mapy73(work_dir)
    log.info("mapy73: %d records", len(mapy73_rpts))

    rxf_rpts = fetch_rxf(work_dir)
    log.info("RXF: %d records", len(rxf_rpts))

    all_rpts = mapy73_rpts + rxf_rpts
    log.info("Total raw: %d records", len(all_rpts))

    if not all_rpts:
        log.error("No repeaters fetched from any source")
        return 1

    # --- Merge ---
    log.info("=== Merging ===")
    merged = merge_repeaters(all_rpts)
    log.info("After merge: %d records", len(merged))

    # --- Assign voivodeships ---
    log.info("=== Assigning voivodeships ===")
    merged = assign_voivodeships(merged)

    # --- Export ---
    log.info("=== Exporting CSV ===")
    output_path: Path = args.output
    count = export_csv(merged, output_path)

    split_counts: dict[str, int] = {}
    if args.split_dir is not None:
        split_counts = export_split(merged, args.split_dir)

    # --- Report ---
    log.info("=== Report ===")
    log.info("Total merged: %d", len(merged))
    log.info("Exported to CSV: %d", count)
    log.info("Output: %s", output_path)
    if split_counts:
        log.info("Per-voivodeship files: %d in %s", len(split_counts), args.split_dir)

    # Mode breakdown
    from collections import Counter
    mode_counts = Counter(r.mode.value for r in merged)
    for mode, cnt in sorted(mode_counts.items()):
        log.info("  %s: %d", mode, cnt)

    # Voivodeship breakdown
    voiv_counts = Counter(r.voivodeship or "unassigned" for r in merged)
    for voiv, cnt in sorted(voiv_counts.items()):
        log.info("  %s: %d", voiv, cnt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
