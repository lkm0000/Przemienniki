"""Tests for mapy73 YAML parser."""

from pathlib import Path

from src.models import Band, Mode, Status
from src.sources.mapy73 import parse_file, _resolve_mode, _parse_access


class TestResolveMode:
    def test_fm(self):
        assert _resolve_mode("a") == [Mode.FM]

    def test_dstar(self):
        assert _resolve_mode("b") == [Mode.DSTAR]

    def test_dmr(self):
        assert _resolve_mode("e") == [Mode.DMR]

    def test_c4fm(self):
        assert _resolve_mode("g") == [Mode.C4FM]

    def test_network_only_becomes_fm(self):
        # d=Echolink, i=FM-Link, j=FM-Poland — all are FM-based
        assert _resolve_mode("d") == [Mode.FM]
        assert _resolve_mode("i") == [Mode.FM]
        assert _resolve_mode("j") == [Mode.FM]

    def test_combined_fm_network(self):
        # aj = FM + FM-Poland — FM is already present, no duplicate
        modes = _resolve_mode("aj")
        assert Mode.FM in modes
        assert len(modes) == 1

    def test_combined_fm_echolink(self):
        modes = _resolve_mode("ad")
        assert Mode.FM in modes

    def test_unknown_defaults_to_fm(self):
        assert _resolve_mode("") == [Mode.FM]


class TestParseAccess:
    def test_ctcss(self):
        rx = {"f": 431.0, "t": [{"c": "94.8"}]}
        result = _parse_access(rx)
        assert result["ctcss"] == 94.8
        assert "CTCSS" in result["access_text"]

    def test_color_code(self):
        rx = {"f": 431.0, "t": [{"f": "1"}]}
        result = _parse_access(rx)
        assert result["color_code"] == 1

    def test_carrier(self):
        rx = {"f": 431.0, "t": [{"a": ""}]}
        result = _parse_access(rx)
        assert "carrier" in result["access_text"]

    def test_1750_and_ctcss(self):
        rx = {"f": 145.0, "t": [{"b": ""}, {"c": "67.0"}]}
        result = _parse_access(rx)
        assert result["ctcss"] == 67.0
        assert "1750Hz" in result["access_text"]

    def test_no_tones(self):
        rx = {"f": 431.0}
        result = _parse_access(rx)
        assert result == {}


class TestParseFile:
    def test_parses_all_entries(self, mapy73_sample: Path):
        repeaters = parse_file(mapy73_sample, "SR5TEST")
        # 3 entries on 70cm (FM, D-STAR, DMR) + 1 on 2m (FM) = 4
        assert len(repeaters) == 4

    def test_fm_entry(self, mapy73_sample: Path):
        rpts = parse_file(mapy73_sample, "SR5TEST")
        fm_70 = [r for r in rpts if r.mode == Mode.FM and r.band == Band.B_70CM]
        assert len(fm_70) == 1
        rpt = fm_70[0]
        assert rpt.call == "SR5TEST"
        assert rpt.tx_mhz == 438.6625
        assert rpt.rx_mhz == 431.0625
        assert rpt.ctcss == 94.8
        assert rpt.status == Status.ACTIVE

    def test_dstar_entry(self, mapy73_sample: Path):
        rpts = parse_file(mapy73_sample, "SR5TEST")
        dstar = [r for r in rpts if r.mode == Mode.DSTAR]
        assert len(dstar) == 1
        assert dstar[0].dstar_module == "B"  # 70cm

    def test_dmr_entry(self, mapy73_sample: Path):
        rpts = parse_file(mapy73_sample, "SR5TEST")
        dmr = [r for r in rpts if r.mode == Mode.DMR]
        assert len(dmr) == 1
        assert dmr[0].color_code == 1

    def test_location_parsed(self, mapy73_sample: Path):
        rpts = parse_file(mapy73_sample, "SR5TEST")
        rpt = rpts[0]
        assert rpt.latitude == 52.203
        assert rpt.longitude == 21.00
        assert rpt.qth_city == "Warszawa"
        assert rpt.agl_m == 45
        assert rpt.asl_m == 120

    def test_2m_testing_status(self, mapy73_sample: Path):
        rpts = parse_file(mapy73_sample, "SR5TEST")
        fm_2m = [r for r in rpts if r.band == Band.B_2M]
        assert len(fm_2m) == 1
        assert fm_2m[0].status == Status.TESTING

    def test_source_is_mapy73(self, mapy73_sample: Path):
        rpts = parse_file(mapy73_sample, "SR5TEST")
        for rpt in rpts:
            assert rpt.source == "mapy73"
