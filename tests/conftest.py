"""Shared pytest fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def mapy73_sample(fixtures_dir: Path) -> Path:
    return fixtures_dir / "mapy73_sample.yaml"


@pytest.fixture
def rxf_sample(fixtures_dir: Path) -> Path:
    return fixtures_dir / "rxf_sample.xml"


@pytest.fixture
def test_geojson(fixtures_dir: Path) -> Path:
    return fixtures_dir / "wojewodztwa_test.geojson"
