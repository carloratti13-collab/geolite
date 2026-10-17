from __future__ import annotations

import pandas as pd


def mineral_points(minerals: pd.DataFrame) -> pd.DataFrame:
    """Return mineral records for Streamlit map/table components."""
    return minerals[["lat", "lon", "mineral", "country", "note", "image_url", "color"]].copy()
