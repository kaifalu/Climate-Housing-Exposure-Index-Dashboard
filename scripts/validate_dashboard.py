#!/usr/bin/env python3
"""Validate the revised dashboard package, hotspot logic, and static entry files."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INDEX = ROOT / "index.html"
LEGACY = ROOT / "climate_housing_exposure_index_dashboard.html"

HOTSPOT_PRECIP_THRESHOLD = 203.603
HOTSPOT_HOUSEHOLD_THRESHOLD = 746
HOTSPOT_SVI_THRESHOLD = 0.88386

REQUIRED = [
    INDEX,
    LEGACY,
    ROOT / ".nojekyll",
    ROOT / "server.py",
    ROOT / "preprocess_data.py",
    ROOT / "build_dashboard.py",
    ROOT / "README.md",
    ROOT / "REVISION_NOTES.md",
    DATA / "tracts_web.geojson",
    DATA / "parcels_web.geojson",
    DATA / "housing_grid.geojson",
    DATA / "sf_points_sorted.npy",
    DATA / "mf_points_sorted.npy",
    DATA / "data_quality_report.json",
]

EXPECTED_COMBINATIONS = {
    "None high",
    "Hazard only",
    "Growth only",
    "SVI only",
    "Hazard + growth",
    "Hazard + SVI",
    "Growth + SVI",
    "All three high",
}


def classify_hotspot(hazard: bool, growth: bool, svi: bool) -> str:
    if hazard and growth and svi:
        return "All three high"
    if hazard and growth:
        return "Hazard + growth"
    if hazard and svi:
        return "Hazard + SVI"
    if growth and svi:
        return "Growth + SVI"
    if hazard:
        return "Hazard only"
    if growth:
        return "Growth only"
    if svi:
        return "SVI only"
    return "None high"


def main() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    report = json.loads((DATA / "data_quality_report.json").read_text(encoding="utf-8"))
    tracts = gpd.read_file(DATA / "tracts_web.geojson")
    inventory = pd.read_csv(DATA / "gdb_layer_inventory.csv")
    sf = np.load(DATA / "sf_points_sorted.npy", mmap_mode="r")
    mf = np.load(DATA / "mf_points_sorted.npy", mmap_mode="r")
    html = INDEX.read_text(encoding="utf-8")

    assert len(tracts) == report["counts"]["census_tracts"] == 1115
    assert len(inventory) == report["available_vector_layers"] == 30
    assert sf.shape == (report["counts"]["single_family_points"], 2)
    assert mf.shape == (report["counts"]["multi_family_points"], 2)
    assert np.all(sf[:-1, 0] <= sf[1:, 0])
    assert np.all(mf[:-1, 0] <= mf[1:, 0])

    # Verify the documented 80th-percentile hotspot thresholds reproduce the
    # uploaded 0–3 score and retain all eight underlying combinations.
    hazard = np.round(pd.to_numeric(tracts["pr_25"], errors="coerce").to_numpy(float), 3) >= HOTSPOT_PRECIP_THRESHOLD
    growth = pd.to_numeric(tracts["hh_chg"], errors="coerce").to_numpy(float) >= HOTSPOT_HOUSEHOLD_THRESHOLD
    svi = pd.to_numeric(tracts["SVI"], errors="coerce").to_numpy(float) >= HOTSPOT_SVI_THRESHOLD
    calculated_score = hazard.astype(int) + growth.astype(int) + svi.astype(int)
    source_score = pd.to_numeric(tracts["hotspot_sc"], errors="coerce").fillna(0).to_numpy(int)
    assert np.array_equal(calculated_score, source_score)

    combinations = [classify_hotspot(bool(h), bool(g), bool(s)) for h, g, s in zip(hazard, growth, svi)]
    combination_counts = Counter(combinations)
    assert set(combination_counts) == EXPECTED_COMBINATIONS
    assert combination_counts["All three high"] == 5
    assert sum(combination_counts.values()) == 1115

    # Verify revised interface content and GitHub Pages compatibility.
    required_html_strings = [
        "Dashboard Overview",
        "Key Functions",
        "Potential Audiences",
        "Practical Applications",
        "READING THE CURRENT LAYER",
        "FROM MAP TO USE",
        "Compound-hotspot typology",
        "203.603 mm",
        "746 households",
        "0.88386",
        "Hazard + growth",
        "Growth + SVI",
        "All three high",
        "Climate Housing Exposure Index Dashboard",
        "Kaifa.Lu@ttu.edu",
        "GMT precipitation kriging surface",
    ]
    absent = [text for text in required_html_strings if text not in html]
    assert not absent, f"Expected revised interface text not found: {absent}"
    assert INDEX.read_bytes() == LEGACY.read_bytes(), "Standalone HTML copies are not identical."

    result = {
        "tracts": len(tracts),
        "gdb_layers": len(inventory),
        "single_family_points": int(sf.shape[0]),
        "multi_family_points": int(mf.shape[0]),
        "hotspot_combination_counts": dict(combination_counts),
        "all_three_high_tracts": int(combination_counts["All three high"]),
        "index_html_mb": round(INDEX.stat().st_size / 1024 / 1024, 1),
        "legacy_html_identical": True,
    }
    print("Revised dashboard package validation passed.")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
