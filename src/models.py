"""Common data model for repeater records."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Band(Enum):
    B_6M = "6m"
    B_2M = "2m"
    B_70CM = "70cm"
    B_23CM = "23cm"
    B_13CM = "13cm"
    OTHER = "other"

    @classmethod
    def from_frequency(cls, freq_mhz: float) -> Band:
        if 50 <= freq_mhz < 54:
            return cls.B_6M
        if 144 <= freq_mhz < 148:
            return cls.B_2M
        if 430 <= freq_mhz < 440:
            return cls.B_70CM
        if 1240 <= freq_mhz < 1300:
            return cls.B_23CM
        if 2300 <= freq_mhz < 2450:
            return cls.B_13CM
        return cls.OTHER


class Mode(Enum):
    FM = "FM"
    DSTAR = "D-STAR"
    DMR = "DMR"
    C4FM = "C4FM"
    ATV = "ATV"
    TETRA = "TETRA"
    APCO25 = "APCO-25"
    OTHER = "other"


class Status(Enum):
    ACTIVE = "active"
    TESTING = "testing"
    PLANNED = "planned"
    BUILDING = "building"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


@dataclass
class Repeater:
    call: str
    tx_mhz: float          # repeater output (user listens)
    rx_mhz: float          # repeater input (user transmits)
    band: Band
    mode: Mode
    status: Status = Status.UNKNOWN

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    qth_locator: Optional[str] = None
    qth_city: Optional[str] = None
    agl_m: Optional[float] = None
    asl_m: Optional[float] = None

    # Access
    ctcss: Optional[float] = None
    dcs_code: Optional[int] = None
    color_code: Optional[int] = None
    access_text: Optional[str] = None

    # D-STAR specific
    dstar_module: Optional[str] = None  # B (70cm), C (2m)

    # DMR specific
    dmr_id: Optional[int] = None
    dmr_network: Optional[str] = None

    # Metadata
    source: str = ""
    updated: Optional[str] = None
    voivodeship: Optional[str] = None
    notes: Optional[str] = None

    extra: dict = field(default_factory=dict)

    @property
    def offset_mhz(self) -> float:
        return round(self.rx_mhz - self.tx_mhz, 6)

    def merge_key(self) -> tuple:
        return (self.call.upper().strip(), self.band, self.mode)
