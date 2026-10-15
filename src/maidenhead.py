"""Convert Maidenhead / QTH locator to (latitude, longitude).

Supports 4-char (JO91) and 6-char (JO91AB) locators.
Returns the centre of the grid square.
"""

from __future__ import annotations


def locator_to_latlon(locator: str) -> tuple[float, float]:
    """Convert a Maidenhead locator string to (lat, lon) in decimal degrees.

    Raises ValueError for invalid locators.
    """
    loc = locator.strip().upper()
    if len(loc) not in (4, 6):
        raise ValueError(f"Locator must be 4 or 6 characters, got {len(loc)}: {locator!r}")

    # Field (18x18)
    a, b = loc[0], loc[1]
    if not ("A" <= a <= "R") or not ("A" <= b <= "R"):
        raise ValueError(f"Invalid field characters in locator: {locator!r}")
    lon = (ord(a) - ord("A")) * 20 - 180
    lat = (ord(b) - ord("A")) * 10 - 90

    # Square (10x10)
    c, d = loc[2], loc[3]
    if not c.isdigit() or not d.isdigit():
        raise ValueError(f"Invalid square characters in locator: {locator!r}")
    lon += int(c) * 2
    lat += int(d) * 1

    if len(loc) == 6:
        # Subsquare (24x24)
        e, f = loc[4], loc[5]
        if not ("A" <= e <= "X") or not ("A" <= f <= "X"):
            raise ValueError(f"Invalid subsquare characters in locator: {locator!r}")
        lon += (ord(e) - ord("A")) * (2 / 24)
        lat += (ord(f) - ord("A")) * (1 / 24)
        # Centre of subsquare
        lon += 1 / 24
        lat += 0.5 / 24
    else:
        # Centre of square
        lon += 1
        lat += 0.5

    return (round(lat, 6), round(lon, 6))
