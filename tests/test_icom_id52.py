"""Tests for Icom ID-52 CSV exporter."""

import csv
from pathlib import Path

from src.exporters.icom_id52 import (
    CSV_HEADER,
    _format_freq,
    _make_name,
    _make_sub_name,
    _repeater_callsign,
    _gateway_callsign,
    _to_ascii,
    _dup_and_offset,
    export_csv,
    export_split,
    filter_for_id52,
)
from src.models import Band, Mode, Repeater, Status


def _make_rpt(**kwargs) -> Repeater:
    defaults = dict(
        call="SR5X", tx_mhz=438.6625, rx_mhz=431.0625,
        band=Band.B_70CM, mode=Mode.FM, status=Status.ACTIVE,
        voivodeship="Mazowieckie",
    )
    defaults.update(kwargs)
    return Repeater(**defaults)


class TestToAscii:
    def test_polish_chars(self):
        assert _to_ascii("łódzkie") == "lodzkie"
        assert _to_ascii("świętokrzyskie") == "swietokrzyskie"
        assert _to_ascii("Kraków") == "Krakow"


class TestMakeName:
    def test_call_with_city(self):
        rpt = _make_rpt(qth_city="Warszawa")
        name = _make_name(rpt)
        assert name == "SR5X Warszawa"
        assert len(name) <= 16

    def test_long_city_truncated(self):
        rpt = _make_rpt(qth_city="Alexandrowicz-Podlasie")
        name = _make_name(rpt)
        assert len(name) <= 16
        assert name.startswith("SR5X ")

    def test_no_city(self):
        rpt = _make_rpt(qth_city=None)
        assert _make_name(rpt) == "SR5X"

    def test_polish_city_ascii(self):
        rpt = _make_rpt(qth_city="Łódź")
        name = _make_name(rpt)
        assert "Lodz" in name


class TestMakeSubName:
    def test_fm_with_ctcss(self):
        rpt = _make_rpt(mode=Mode.FM, ctcss=103.5)
        assert _make_sub_name(rpt) == "FM 103.5"

    def test_fm_without_ctcss(self):
        rpt = _make_rpt(mode=Mode.FM, ctcss=None)
        assert _make_sub_name(rpt) == "FM"

    def test_dstar(self):
        rpt = _make_rpt(mode=Mode.DSTAR)
        assert _make_sub_name(rpt) == "DV"


class TestDstarCallsigns:
    def test_repeater_callsign_70cm(self):
        rpt = _make_rpt(mode=Mode.DSTAR, band=Band.B_70CM, dstar_module="B")
        cs = _repeater_callsign(rpt)
        assert cs == "SR5X   B"
        assert len(cs) == 8

    def test_repeater_callsign_2m(self):
        rpt = _make_rpt(mode=Mode.DSTAR, band=Band.B_2M, dstar_module="C")
        cs = _repeater_callsign(rpt)
        assert cs == "SR5X   C"

    def test_gateway_callsign(self):
        rpt = _make_rpt(mode=Mode.DSTAR)
        cs = _gateway_callsign(rpt)
        assert cs == "SR5X   G"

    def test_fm_no_callsign(self):
        rpt = _make_rpt(mode=Mode.FM)
        assert _repeater_callsign(rpt) == ""
        assert _gateway_callsign(rpt) == ""


class TestFormatFreq:
    def test_format(self):
        assert _format_freq(438.6625) == "438.662500"
        assert _format_freq(145.6125) == "145.612500"


class TestDupOffset:
    def test_negative_offset(self):
        rpt = _make_rpt(tx_mhz=438.6625, rx_mhz=431.0625)
        dup, offset = _dup_and_offset(rpt)
        assert dup == "DUP-"
        assert offset == "7.600000"

    def test_positive_offset(self):
        rpt = _make_rpt(tx_mhz=145.6125, rx_mhz=145.0125)
        dup, offset = _dup_and_offset(rpt)
        assert dup == "DUP-"


class TestFilterForId52:
    def test_fm_active_passes(self):
        rpts = [_make_rpt()]
        assert len(filter_for_id52(rpts)) == 1

    def test_dstar_active_passes(self):
        rpts = [_make_rpt(mode=Mode.DSTAR)]
        assert len(filter_for_id52(rpts)) == 1

    def test_dmr_filtered_out(self):
        rpts = [_make_rpt(mode=Mode.DMR)]
        assert len(filter_for_id52(rpts)) == 0

    def test_inactive_filtered_out(self):
        rpts = [_make_rpt(status=Status.INACTIVE)]
        assert len(filter_for_id52(rpts)) == 0

    def test_testing_passes(self):
        rpts = [_make_rpt(status=Status.TESTING)]
        assert len(filter_for_id52(rpts)) == 1

    def test_23cm_filtered_out(self):
        rpts = [_make_rpt(band=Band.B_23CM)]
        assert len(filter_for_id52(rpts)) == 0


class TestExportCsv:
    def test_creates_csv_with_header(self, tmp_path: Path):
        rpts = [
            _make_rpt(latitude=52.2, longitude=21.0),
        ]
        out = tmp_path / "test.csv"
        count = export_csv(rpts, out)
        assert count == 1

        with open(out) as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == CSV_HEADER
            row = next(reader)
            assert len(row) == len(CSV_HEADER)

    def test_groups_by_voivodeship(self, tmp_path: Path):
        rpts = [
            _make_rpt(voivodeship="Mazowieckie"),
            _make_rpt(call="SR6Y", voivodeship="Dolnoslaskie"),
        ]
        out = tmp_path / "test.csv"
        count = export_csv(rpts, out)
        assert count == 2

        with open(out) as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)
            group_names = {r[1] for r in rows}
            assert "Mazowieckie" in group_names
            assert "Dolnoslaskie" in group_names

    def test_dstar_fields(self, tmp_path: Path):
        rpts = [
            _make_rpt(mode=Mode.DSTAR, dstar_module="B", latitude=52.2, longitude=21.0),
        ]
        out = tmp_path / "test.csv"
        export_csv(rpts, out)

        with open(out) as f:
            reader = csv.reader(f)
            next(reader)
            row = next(reader)
            # Mode should be DV
            assert row[CSV_HEADER.index("Mode")] == "DV"
            # Repeater Call Sign should be padded
            rpt_cs = row[CSV_HEADER.index("Repeater Call Sign")]
            assert len(rpt_cs) == 8
            assert rpt_cs.endswith("B")

    def test_empty_input_returns_zero(self, tmp_path: Path):
        out = tmp_path / "test.csv"
        count = export_csv([], out)
        assert count == 0

    def test_utc_offset(self, tmp_path: Path):
        rpts = [_make_rpt()]
        out = tmp_path / "test.csv"
        export_csv(rpts, out)

        with open(out) as f:
            reader = csv.reader(f)
            next(reader)
            row = next(reader)
            assert row[CSV_HEADER.index("UTC Offset")] == "+1:00"

    def test_rpt1use_yes(self, tmp_path: Path):
        rpts = [_make_rpt()]
        out = tmp_path / "test.csv"
        export_csv(rpts, out)

        with open(out) as f:
            reader = csv.reader(f)
            next(reader)
            row = next(reader)
            assert row[CSV_HEADER.index("RPT1USE")] == "Yes"


class TestExportSplit:
    def test_one_file_per_voivodeship(self, tmp_path: Path):
        rpts = [
            _make_rpt(voivodeship="Mazowieckie"),
            _make_rpt(call="SR5Y", voivodeship="Mazowieckie"),
            _make_rpt(call="SR6Y", voivodeship="Dolnoslaskie"),
        ]
        counts = export_split(rpts, tmp_path)
        assert counts == {"01_Dolnoslaskie.csv": 1, "02_Mazowieckie.csv": 2}
        assert sorted(p.name for p in tmp_path.iterdir()) == list(counts)

    def test_group_numbers_match_combined_export(self, tmp_path: Path):
        rpts = [
            _make_rpt(voivodeship="Mazowieckie"),
            _make_rpt(call="SR6Y", voivodeship="Dolnoslaskie"),
        ]
        combined = tmp_path / "all.csv"
        export_csv(rpts, combined)
        export_split(rpts, tmp_path / "split")

        with open(combined) as f:
            combined_rows = list(csv.reader(f))[1:]
        split_rows = []
        for p in sorted((tmp_path / "split").iterdir()):
            with open(p) as f:
                reader = csv.reader(f)
                assert next(reader) == CSV_HEADER
                split_rows.extend(reader)
        assert split_rows == combined_rows

    def test_filtered_out_repeaters_skipped(self, tmp_path: Path):
        rpts = [
            _make_rpt(voivodeship="Mazowieckie"),
            _make_rpt(call="SR6Y", mode=Mode.DMR, voivodeship="Dolnoslaskie"),
        ]
        counts = export_split(rpts, tmp_path)
        assert counts == {"01_Mazowieckie.csv": 1}

    def test_empty_input_writes_nothing(self, tmp_path: Path):
        assert export_split([], tmp_path / "split") == {}
        assert not (tmp_path / "split").exists()
