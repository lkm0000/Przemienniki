"""Tests for merge/deduplication logic."""

from src.merge import merge_repeaters
from src.models import Band, Mode, Repeater, Status


def _make_rpt(**kwargs) -> Repeater:
    defaults = dict(
        call="SR5X", tx_mhz=438.6625, rx_mhz=431.0625,
        band=Band.B_70CM, mode=Mode.FM, status=Status.ACTIVE,
        source="test",
    )
    defaults.update(kwargs)
    return Repeater(**defaults)


class TestMerge:
    def test_no_duplicates(self):
        rpts = [
            _make_rpt(call="SR5A"),
            _make_rpt(call="SR5B"),
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 2

    def test_exact_duplicate_merged(self):
        rpts = [
            _make_rpt(source="mapy73", updated="2025-01-01"),
            _make_rpt(source="rxf", updated="2025-06-01"),
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 1
        # Newer source wins
        assert "rxf" in merged[0].source

    def test_freq_tolerance(self):
        """Entries within 5 kHz should be merged."""
        rpts = [
            _make_rpt(tx_mhz=438.6625, source="mapy73", updated="2025-01-01"),
            _make_rpt(tx_mhz=438.6650, source="rxf", updated="2025-06-01"),  # 2.5 kHz diff
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 1

    def test_freq_beyond_tolerance_not_merged(self):
        """Entries beyond 5 kHz should not be merged."""
        rpts = [
            _make_rpt(tx_mhz=438.6625, source="mapy73"),
            _make_rpt(tx_mhz=438.6725, source="rxf"),  # 10 kHz diff
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 2

    def test_different_modes_not_merged(self):
        rpts = [
            _make_rpt(mode=Mode.FM),
            _make_rpt(mode=Mode.DSTAR),
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 2

    def test_fill_empty_fields(self):
        rpts = [
            _make_rpt(source="mapy73", updated="2025-06-01", qth_city="Warszawa", ctcss=None),
            _make_rpt(source="rxf", updated="2025-01-01", qth_city=None, ctcss=94.8),
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 1
        # Winner is mapy73 (newer), but ctcss filled from rxf
        assert merged[0].qth_city == "Warszawa"
        assert merged[0].ctcss == 94.8

    def test_conflict_noted(self):
        rpts = [
            _make_rpt(source="mapy73", updated="2025-06-01", ctcss=94.8),
            _make_rpt(source="rxf", updated="2025-01-01", ctcss=88.5),
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 1
        assert merged[0].notes
        assert "CTCSS" in merged[0].notes

    def test_merge_preserves_different_calls(self):
        rpts = [
            _make_rpt(call="SR5A"),
            _make_rpt(call="SR5B"),
            _make_rpt(call="SR5A", source="rxf", updated="2025-06-01"),
        ]
        merged = merge_repeaters(rpts)
        assert len(merged) == 2
