"""pytest shared fixtures for Public-Sanitation-Monitoring tests."""
from __future__ import annotations

import sys
import pathlib
from typing import List, Dict

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


@pytest.fixture()
def normal_reading() -> Dict:
    """A normal-range sensor reading."""
    return {
        'timestamp': '2025-02-01T10:00:00',
        'location_id': 'block_A_toilet_1',
        'nh3_ppm': 8.0,
        'h2s_ppm': 0.3,
        'temperature_c': 26.0,
        'humidity_pct': 65.0,
        'pm25_ugm3': 15.0,
    }


@pytest.fixture()
def warning_reading() -> Dict:
    """A reading that exceeds warning thresholds."""
    return {
        'timestamp': '2025-02-01T10:05:00',
        'location_id': 'block_A_toilet_1',
        'nh3_ppm': 30.0,   # > warning(25.0)
        'h2s_ppm': 0.5,
        'temperature_c': 28.0,
        'humidity_pct': 70.0,
        'pm25_ugm3': 20.0,
    }


@pytest.fixture()
def critical_reading() -> Dict:
    """A reading that exceeds critical thresholds."""
    return {
        'timestamp': '2025-02-01T10:10:00',
        'location_id': 'block_B_toilet_1',
        'nh3_ppm': 65.0,   # > critical(50.0)
        'h2s_ppm': 6.0,    # > critical(5.0)
        'temperature_c': 28.0,
        'humidity_pct': 70.0,
        'pm25_ugm3': 20.0,
    }


@pytest.fixture()
def reading_history(normal_reading) -> List[Dict]:
    """A list of 10 identical normal readings for history-based tests."""
    return [dict(normal_reading) for _ in range(10)]
