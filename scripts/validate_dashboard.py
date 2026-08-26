#!/usr/bin/env python3
"""Validate the commissioner-precinct, interactive-legend, decision-tool release.

The checks cover prepared-data integrity, hotspot classification, locator geometry,
self-contained HTML content, and package-level consistency. Browser interactions
are exercised separately by the documented Playwright smoke-test workflow.
"""
from __future__ import annotations

import json
import re
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
    ROOT / "GITHUB_PAGES_DEPLOYMENT.md",
    ROOT / "REVISION_NOTES.md",
    ROOT / "ATTRIBUTION_AND_DATA_NOTES.md",
    ROOT / "TERMS_OF_USE.md",
    DATA / "tracts_web.geojson",
    DATA / "zipcodes_web.geojson",
    DATA / "commissioner_precincts_web.geojson",
    DATA / "parcels_web.geojson",
    DATA / "housing_grid.geojson",
    DATA / "sf_points_sorted.npy",
    DATA / "mf_points_sorted.npy",
    DATA / "gdb_layer_inventory.csv",
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


def assert_valid_geometry(frame: gpd.GeoDataFrame, label: str) -> None:
    assert frame.geometry.notna().all(), f"{label} includes null geometry."
    assert (~frame.geometry.is_empty).all(), f"{label} includes empty geometry."
    assert frame.geometry.is_valid.all(), f"{label} includes invalid geometry."


def main() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    report = json.loads((DATA / "data_quality_report.json").read_text(encoding="utf-8"))
    tracts = gpd.read_file(DATA / "tracts_web.geojson")
    zipcodes = gpd.read_file(DATA / "zipcodes_web.geojson")
    precincts = gpd.read_file(DATA / "commissioner_precincts_web.geojson")
    parcels = gpd.read_file(DATA / "parcels_web.geojson")
    housing_grid = gpd.read_file(DATA / "housing_grid.geojson")
    inventory = pd.read_csv(DATA / "gdb_layer_inventory.csv")
    sf = np.load(DATA / "sf_points_sorted.npy", mmap_mode="r")
    mf = np.load(DATA / "mf_points_sorted.npy", mmap_mode="r")
    html = INDEX.read_text(encoding="utf-8")

    counts = report["counts"]
    assert len(tracts) == counts["census_tracts"] == 1115
    assert len(zipcodes) == counts["zip_codes"] == 155
    assert len(precincts) == counts["commissioner_precincts"] == 4
    assert len(parcels) == counts["parcels"] == 20344
    assert len(housing_grid) == counts["housing_grid_cells"] == 4863
    assert len(inventory) == report["available_vector_layers"] == 32
    inventory_names = set(inventory["gdb_layer"].astype(str))
    assert "Harris_County_Zipcodes" in inventory_names
    assert "Harris_County_Commissioner_Precincts" in inventory_names

    assert sf.shape == (counts["single_family_points"], 2)
    assert mf.shape == (counts["multi_family_points"], 2)
    assert np.all(sf[:-1, 0] <= sf[1:, 0])
    assert np.all(mf[:-1, 0] <= mf[1:, 0])

    assert_valid_geometry(tracts, "tract layer")
    assert_valid_geometry(zipcodes, "ZIP-code layer")
    assert_valid_geometry(precincts, "commissioner-precinct layer")

    # Five-digit ZIP locator integrity.
    zip_values = zipcodes["ZIP"].astype(str).str.strip()
    assert zip_values.nunique() == 155
    assert zip_values.map(lambda value: bool(re.fullmatch(r"\d{5}", value))).all()
    assert "77007" in set(zip_values)
    assert report["zip_code_note"].startswith(
        "Harris_County_Zipcodes is included for boundary display and search only"
    )

    # Four stable precinct identifiers; officeholder names are intentionally not
    # used in the public interface so the dashboard does not become outdated.
    precinct_values = pd.to_numeric(precincts["PCT_NO"], errors="raise").astype(int)
    assert set(precinct_values) == {1, 2, 3, 4}
    assert precinct_values.nunique() == 4
    assert (pd.to_numeric(precincts["AREA_IN_MI"], errors="coerce") > 0).all()
    assert report["commissioner_precinct_note"].startswith(
        "Harris_County_Commissioner_Precincts is included for boundary display"
    )

    # Every ZIP and precinct must intersect at least one source census tract;
    # these relationships support transparent screening summaries rather than
    # source-level reaggregation.
    tract_sindex = tracts.sindex
    zip_intersections = []
    for geom in zipcodes.geometry:
        candidates = list(tract_sindex.query(geom, predicate="intersects"))
        zip_intersections.append(len(candidates))
    precinct_intersections = []
    for geom in precincts.geometry:
        candidates = list(tract_sindex.query(geom, predicate="intersects"))
        precinct_intersections.append(len(candidates))
    assert min(zip_intersections) > 0
    assert min(precinct_intersections) > 0

    # Verify the documented 80th-percentile hotspot thresholds reproduce the
    # uploaded 0-3 score while retaining all eight factor combinations.
    hazard = (
        np.round(pd.to_numeric(tracts["pr_25"], errors="coerce").to_numpy(float), 3)
        >= HOTSPOT_PRECIP_THRESHOLD
    )
    growth = (
        pd.to_numeric(tracts["hh_chg"], errors="coerce").to_numpy(float)
        >= HOTSPOT_HOUSEHOLD_THRESHOLD
    )
    svi = (
        pd.to_numeric(tracts["SVI"], errors="coerce").to_numpy(float)
        >= HOTSPOT_SVI_THRESHOLD
    )
    calculated_score = hazard.astype(int) + growth.astype(int) + svi.astype(int)
    source_score = (
        pd.to_numeric(tracts["hotspot_sc"], errors="coerce")
        .fillna(0)
        .to_numpy(int)
    )
    assert np.array_equal(calculated_score, source_score)

    combinations = [
        classify_hotspot(bool(h), bool(g), bool(s))
        for h, g, s in zip(hazard, growth, svi)
    ]
    combination_counts = Counter(combinations)
    assert set(combination_counts) == EXPECTED_COMBINATIONS
    assert combination_counts["All three high"] == 5
    assert sum(combination_counts.values()) == 1115

    # Interface, locator, legend-filter, quick-decision, and report functions
    # must all be embedded in the standalone HTML.
    required_html_strings = [
        "Dashboard Overview",
        "Key Functions",
        "Potential Audiences",
        "Practical Applications",
        "READING THE CURRENT LAYER",
        "FROM MAP TO USE",
        "Compound-hotspot typology",
        "Pattern-based typology",
        "203.603 mm",
        "746 households",
        "0.88386",
        "right_diagonal_line",
        "vertical_line",
        "hotspot_pattern_hazard",
        "hotspot_pattern_growth",
        "hotspot_pattern_svi",
        "Locate a ZIP code",
        "Find ZIP code",
        "Show all ZIP-code boundaries",
        "e.g., 77007",
        "Harris_County_Zipcodes",
        "Locate a commissioner precinct",
        "Select commissioner precinct",
        "Show all commissioner precinct boundaries",
        "Harris_County_Commissioner_Precincts",
        "Precinct 1",
        "legend-button",
        "selectLegend",
        "zoomLegendMatches",
        "Clear filter",
        "Click a raster class to locate census tracts",
        "QUICK DECISION VIEW",
        "Highest overall exposure",
        "Three-factor overlap",
        "Emerging adaptation needs",
        "Selected-place conditions",
        "ONE-PAGE DECISION BRIEF",
        "Generate one-page decision brief",
        "Print / Save as PDF",
        "screening summary",
        "not an official ZIP- or precinct-level aggregation",
        "Climate Housing Exposure Index Dashboard",
        "Kaifa.Lu@ttu.edu",
    ]
    absent = [text for text in required_html_strings if text not in html]
    assert not absent, f"Expected revised interface text not found: {absent}"

    # The standalone build embeds BokehJS and the analytical data. The only
    # intentionally external resource is the optional CARTO/OSM basemap tile URL.
    assert "BEGIN bokeh.min.js" in html
    assert "dashboard_init_trigger" in html
    assert "commissioner_precincts_web.geojson" not in html  # data are embedded, not fetched
    assert INDEX.stat().st_size > 10_000_000
    assert INDEX.read_bytes() == LEGACY.read_bytes(), (
        "Standalone HTML copies are not identical."
    )

    result = {
        "tracts": len(tracts),
        "zip_codes": len(zipcodes),
        "commissioner_precincts": len(precincts),
        "gdb_layers": len(inventory),
        "single_family_points": int(sf.shape[0]),
        "multi_family_points": int(mf.shape[0]),
        "hotspot_combination_counts": dict(combination_counts),
        "all_three_high_tracts": int(combination_counts["All three high"]),
        "zip_intersecting_tract_range": [min(zip_intersections), max(zip_intersections)],
        "precinct_intersecting_tract_counts": precinct_intersections,
        "index_html_mb": round(INDEX.stat().st_size / 1024 / 1024, 1),
        "legacy_html_identical": True,
    }
    print("Commissioner-precinct and decision-tool dashboard validation passed.")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
