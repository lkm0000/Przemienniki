"""Assign voivodeships to repeaters using GeoJSON point-in-polygon."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import nearest_points

from src.maidenhead import locator_to_latlon
from src.models import Repeater

logger = logging.getLogger(__name__)

GEOJSON_PATH = Path(__file__).resolve().parent.parent / "data" / "wojewodztwa.geojson"

MAX_FALLBACK_KM = 20.0

# ASCII-safe names for ID-52 (max 16 chars)
_VOIVODESHIP_ASCII: dict[str, str] = {
    "dolnośląskie": "Dolnoslaskie",
    "kujawsko-pomorskie": "KujPomorskie",
    "lubelskie": "Lubelskie",
    "lubuskie": "Lubuskie",
    "łódzkie": "Lodzkie",
    "małopolskie": "Malopolskie",
    "mazowieckie": "Mazowieckie",
    "opolskie": "Opolskie",
    "podkarpackie": "Podkarpackie",
    "podlaskie": "Podlaskie",
    "pomorskie": "Pomorskie",
    "śląskie": "Slaskie",
    "świętokrzyskie": "Swietokrzyskie",
    "warmińsko-mazurskie": "WarmMazurskie",
    "wielkopolskie": "Wielkopolskie",
    "zachodniopomorskie": "Zachodniopom",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


class VoivodeshipLookup:
    """Lookup voivodeship from coordinates using GeoJSON polygons."""

    def __init__(self, geojson_path: Path | None = None):
        path = geojson_path or GEOJSON_PATH
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.polygons: list[tuple[str, str, object]] = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            name = props.get("nazwa", props.get("name", "")).lower()
            ascii_name = _VOIVODESHIP_ASCII.get(name, name.title()[:16])
            geom = shape(feature["geometry"])
            self.polygons.append((name, ascii_name, geom))

        logger.info("Loaded %d voivodeship polygons", len(self.polygons))

    def lookup(self, lat: float, lon: float) -> tuple[str | None, str | None]:
        """Return (native_name, ascii_name) for given coordinates.

        Falls back to nearest polygon within MAX_FALLBACK_KM.
        Returns (None, None) if no match.
        """
        point = Point(lon, lat)

        # Direct hit
        for name, ascii_name, geom in self.polygons:
            if geom.contains(point):
                return name, ascii_name

        # Nearest polygon fallback
        best_dist = float("inf")
        best_name = None
        best_ascii = None
        for name, ascii_name, geom in self.polygons:
            nearest_on_geom, _ = nearest_points(geom, point)
            dist_km = _haversine_km(lat, lon, nearest_on_geom.y, nearest_on_geom.x)
            if dist_km < best_dist:
                best_dist = dist_km
                best_name = name
                best_ascii = ascii_name

        if best_dist <= MAX_FALLBACK_KM:
            logger.debug("Nearest voivodeship for (%.4f, %.4f): %s (%.1f km)",
                         lat, lon, best_name, best_dist)
            return best_name, best_ascii

        return None, None


def assign_voivodeships(repeaters: list[Repeater],
                        geojson_path: Path | None = None) -> list[Repeater]:
    """Assign voivodeship to each repeater based on coordinates."""
    lookup = VoivodeshipLookup(geojson_path)
    assigned = 0
    from_locator = 0

    for rpt in repeaters:
        lat = rpt.latitude
        lon = rpt.longitude

        # Try to get coordinates from QTH locator if missing
        if (lat is None or lon is None) and rpt.qth_locator:
            try:
                lat, lon = locator_to_latlon(rpt.qth_locator)
                if rpt.latitude is None:
                    rpt.latitude = lat
                if rpt.longitude is None:
                    rpt.longitude = lon
                from_locator += 1
            except ValueError:
                pass

        if lat is not None and lon is not None:
            _, ascii_name = lookup.lookup(lat, lon)
            if ascii_name:
                rpt.voivodeship = ascii_name
                assigned += 1

    logger.info("Assigned voivodeships: %d/%d (coords from locator: %d)",
                assigned, len(repeaters), from_locator)
    return repeaters
