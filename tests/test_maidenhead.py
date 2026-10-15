"""Tests for Maidenhead locator conversion."""

import pytest

from src.maidenhead import locator_to_latlon


class TestLocatorToLatlon:
    def test_six_char_locator_warsaw(self):
        # KO02MC should be near Warsaw (~52.1N, 20.9E)
        lat, lon = locator_to_latlon("KO02MC")
        assert 52.0 < lat < 52.2
        assert 20.7 < lon < 21.1

    def test_six_char_locator_wroclaw(self):
        # JO81CG grid centre: lat~51.27, lon~16.21
        lat, lon = locator_to_latlon("JO81CG")
        assert 51.2 < lat < 51.4
        assert 16.1 < lon < 16.3

    def test_four_char_locator(self):
        # JO91 centre should be around 51.5N, 18-20E
        lat, lon = locator_to_latlon("JO91")
        assert 51.0 < lat < 52.0
        assert 18.0 < lon < 20.0

    def test_case_insensitive(self):
        lat1, lon1 = locator_to_latlon("KO02MC")
        lat2, lon2 = locator_to_latlon("ko02mc")
        assert lat1 == lat2
        assert lon1 == lon2

    def test_invalid_length(self):
        with pytest.raises(ValueError, match="4 or 6"):
            locator_to_latlon("KO0")

    def test_invalid_field(self):
        with pytest.raises(ValueError, match="Invalid field"):
            locator_to_latlon("ZZ00AA")

    def test_invalid_subsquare(self):
        with pytest.raises(ValueError, match="Invalid subsquare"):
            locator_to_latlon("KO02M1")

    def test_known_value_jo91ab(self):
        # JO91AB: field J(9)→lon, O(14)→lat; square 9,1; subsquare A(0),B(1)
        lat, lon = locator_to_latlon("JO91AB")
        # Lon: 9*20 - 180 + 9*2 + 0*(2/24) + 1/24 = 18.0417
        # Lat: 14*10 - 90 + 1*1 + 1*(1/24) + 0.5/24 = 51.0625
        assert abs(lat - 51.0625) < 0.01
        assert abs(lon - 18.0417) < 0.05
