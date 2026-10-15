"""Tests for RXF XML parser."""

from pathlib import Path

from src.models import Band, Mode, Status
from src.sources.rxf import parse_file


class TestParseFile:
    def test_filters_polish_only(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        calls = {r.call for r in rpts}
        assert "DB0AAT" not in calls
        assert all(r.call.startswith("SR") for r in rpts)

    def test_total_count(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        # SR6UVW (FM), SR6R (D-STAR), SR9P (FM+C4FM=2), SR5DX (FM), SR3OLD (FM)
        # = 6 records (SR9P expands to 2)
        assert len(rpts) == 6

    def test_fm_repeater(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr6uvw = [r for r in rpts if r.call == "SR6UVW"]
        assert len(sr6uvw) == 1
        rpt = sr6uvw[0]
        assert rpt.mode == Mode.FM
        assert rpt.band == Band.B_70CM
        assert rpt.tx_mhz == 438.8625
        assert rpt.rx_mhz == 431.2625
        assert rpt.ctcss == 88.5
        assert rpt.status == Status.ACTIVE
        assert rpt.qth_city == "Wroclaw"

    def test_dstar_repeater(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr6r = [r for r in rpts if r.call == "SR6R"]
        assert len(sr6r) == 1
        rpt = sr6r[0]
        assert rpt.mode == Mode.DSTAR
        assert rpt.dstar_module == "B"  # 70cm

    def test_multimode_expansion(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr9p = [r for r in rpts if r.call == "SR9P"]
        assert len(sr9p) == 2
        modes = {r.mode for r in sr9p}
        assert modes == {Mode.FM, Mode.C4FM}

    def test_zero_coords_fallback_to_locator(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr5dx = [r for r in rpts if r.call == "SR5DX"]
        assert len(sr5dx) == 1
        rpt = sr5dx[0]
        # Should have fallback coords from KO01AB locator
        assert rpt.latitude is not None
        assert rpt.longitude is not None
        assert 50.0 < rpt.latitude < 52.0

    def test_disabled_repeater(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr3old = [r for r in rpts if r.call == "SR3OLD"]
        assert len(sr3old) == 1
        assert sr3old[0].status == Status.INACTIVE

    def test_testing_status(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr5dx = [r for r in rpts if r.call == "SR5DX"]
        assert sr5dx[0].status == Status.TESTING

    def test_source_is_rxf(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        for rpt in rpts:
            assert rpt.source == "rxf"

    def test_coordinates_from_xml(self, rxf_sample: Path):
        rpts = parse_file(rxf_sample)
        sr6uvw = [r for r in rpts if r.call == "SR6UVW"][0]
        assert sr6uvw.latitude == 51.107885
        assert sr6uvw.longitude == 17.038538
