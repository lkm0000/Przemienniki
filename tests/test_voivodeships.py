"""Tests for voivodeship assignment."""

from pathlib import Path

from src.models import Band, Mode, Repeater, Status
from src.voivodeships import VoivodeshipLookup, assign_voivodeships


def _make_rpt(**kwargs) -> Repeater:
    defaults = dict(
        call="SR5X", tx_mhz=438.6625, rx_mhz=431.0625,
        band=Band.B_70CM, mode=Mode.FM, status=Status.ACTIVE,
    )
    defaults.update(kwargs)
    return Repeater(**defaults)


class TestVoivodeshipLookup:
    def test_point_in_polygon(self, test_geojson: Path):
        lookup = VoivodeshipLookup(test_geojson)
        # Warsaw (52.2, 21.0) should be in mazowieckie
        name, ascii_name = lookup.lookup(52.2, 21.0)
        assert name == "mazowieckie"
        assert ascii_name == "Mazowieckie"

    def test_wroclaw_dolnoslaskie(self, test_geojson: Path):
        lookup = VoivodeshipLookup(test_geojson)
        name, _ = lookup.lookup(51.1, 17.0)
        assert name == "dolnośląskie"

    def test_krakow_malopolskie(self, test_geojson: Path):
        lookup = VoivodeshipLookup(test_geojson)
        name, ascii_name = lookup.lookup(50.06, 19.94)
        assert name == "małopolskie"
        assert ascii_name == "Malopolskie"

    def test_outside_all_polygons_no_match(self, test_geojson: Path):
        lookup = VoivodeshipLookup(test_geojson)
        # Point way outside Poland
        name, ascii_name = lookup.lookup(40.0, 10.0)
        assert name is None
        assert ascii_name is None

    def test_near_boundary_fallback(self, test_geojson: Path):
        lookup = VoivodeshipLookup(test_geojson)
        # Point slightly outside mazowieckie boundary (22.01, 52.5)
        # Should fall back to nearest within 20km
        name, _ = lookup.lookup(52.5, 22.01)
        # Should match mazowieckie (very close to boundary)
        assert name == "mazowieckie"


class TestAssignVoivodeships:
    def test_assigns_from_coords(self, test_geojson: Path):
        rpts = [_make_rpt(latitude=52.2, longitude=21.0)]
        assign_voivodeships(rpts, test_geojson)
        assert rpts[0].voivodeship == "Mazowieckie"

    def test_assigns_from_locator(self, test_geojson: Path):
        # No coords, but has locator near Warsaw
        rpts = [_make_rpt(latitude=None, longitude=None, qth_locator="KO02MC")]
        assign_voivodeships(rpts, test_geojson)
        assert rpts[0].latitude is not None
        assert rpts[0].voivodeship is not None

    def test_no_coords_no_locator(self, test_geojson: Path):
        rpts = [_make_rpt(latitude=None, longitude=None, qth_locator=None)]
        assign_voivodeships(rpts, test_geojson)
        assert rpts[0].voivodeship is None
