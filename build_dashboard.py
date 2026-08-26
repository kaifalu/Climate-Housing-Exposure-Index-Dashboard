#!/usr/bin/env python3
"""Build the standalone Climate Housing Exposure Index dashboard."""
from __future__ import annotations

import html as html_lib
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from bokeh.embed import file_html
from bokeh.events import DocumentReady
from bokeh.layouts import column, row
from bokeh.models import (
    BasicTickFormatter,
    Button,
    ColumnDataSource,
    CustomJS,
    Div,
    HoverTool,
    InlineStyleSheet,
    NumeralTickFormatter,
    Range1d,
    Select,
    Slider,
    TabPanel,
    Tabs,
    TapTool,
    TextInput,
    Toggle,
    WMTSTileSource,
)
from bokeh.plotting import figure
from bokeh.resources import INLINE
from bokeh.transform import dodge

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = ROOT / "index.html"
LEGACY_OUTPUT = ROOT / "climate_housing_exposure_index_dashboard.html"

PAGE_WIDTH = 1760
CONTROL_COLUMN_WIDTH = 365
CONTROL_CONTENT_WIDTH = 335
MAP_COLUMN_WIDTH = 1005
MAP_PLOT_WIDTH = 985
INSIGHTS_COLUMN_WIDTH = 390
INSIGHT_CONTENT_WIDTH = 365

HOTSPOT_PRECIP_THRESHOLD = 203.603
HOTSPOT_HOUSEHOLD_THRESHOLD = 746
HOTSPOT_SVI_THRESHOLD = 0.88386

NAVY = "#17324D"
DEEP_NAVY = "#0E2438"
TEAL = "#168C95"
AQUA = "#4CB8BE"
GOLD = "#F2B134"
LIGHT = "#F4F7F9"
TEXT = "#273746"
MUTED = "#617382"

SEQ_BLUE = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
SEQ_TEAL = ["#edf8fb", "#b2e2e2", "#66c2a4", "#2ca25f", "#006d2c"]
SEQ_PURPLE = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"]
SEQ_ORANGE = ["#fff5eb", "#fdd0a2", "#fdae6b", "#f16913", "#a63603"]
DIVERGING = ["#2166ac", "#67a9cf", "#f7f7f7", "#ef8a62", "#b2182b"]
BIVARIATE = ["#e8e8e8", "#45B8C4", "#C36AA5", "#354A8C"]
HOTSPOT_ORDER = [
    "None high", "Hazard only", "Growth only", "SVI only",
    "Hazard + growth", "Hazard + SVI", "Growth + SVI", "All three high",
]
HOTSPOT_NEUTRAL_FILLS = {
    "None high": "#F7F8F8",
    "Hazard only": "#EEF2F3",
    "Growth only": "#EEF2F3",
    "SVI only": "#EEF2F3",
    "Hazard + growth": "#E6ECEE",
    "Hazard + SVI": "#E6ECEE",
    "Growth + SVI": "#E6ECEE",
    "All three high": "#D9E2E5",
}
# CSS equivalents of the three overlaid map patterns. Hazard is represented
# by diagonal lines, growth by vertical lines, and social vulnerability by
# dots; combined categories layer the corresponding patterns.
HOTSPOT_PATTERN_STYLES = {
    "None high": "background-color:#F7F8F8;",
    "Hazard only": "background-color:#EEF2F3;background-image:repeating-linear-gradient(135deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px);",
    "Growth only": "background-color:#EEF2F3;background-image:repeating-linear-gradient(90deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px);",
    "SVI only": "background-color:#EEF2F3;background-image:radial-gradient(circle at 2px 2px,#263B4A 1.15px,transparent 1.35px);background-size:7px 7px;",
    "Hazard + growth": "background-color:#E6ECEE;background-image:repeating-linear-gradient(135deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px),repeating-linear-gradient(90deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px);",
    "Hazard + SVI": "background-color:#E6ECEE;background-image:repeating-linear-gradient(135deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px),radial-gradient(circle at 2px 2px,#263B4A 1.15px,transparent 1.35px);background-size:auto,7px 7px;",
    "Growth + SVI": "background-color:#E6ECEE;background-image:repeating-linear-gradient(90deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px),radial-gradient(circle at 2px 2px,#263B4A 1.15px,transparent 1.35px);background-size:auto,7px 7px;",
    "All three high": "background-color:#D9E2E5;background-image:repeating-linear-gradient(135deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px),repeating-linear-gradient(90deg,transparent 0,transparent 5px,#263B4A 5px,#263B4A 6.5px),radial-gradient(circle at 2px 2px,#263B4A 1.15px,transparent 1.35px);background-size:auto,auto,7px 7px;",
}


def load_geojson(name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA / name)
    return gdf.to_crs(3857)


def to_multipolygon_arrays(geometries):
    all_xs, all_ys = [], []
    for geom in geometries:
        if geom is None or geom.is_empty:
            all_xs.append([])
            all_ys.append([])
            continue
        polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        feature_xs, feature_ys = [], []
        for poly in polygons:
            rings_x, rings_y = [], []
            ext = np.asarray(poly.exterior.coords)
            rings_x.append(ext[:, 0].tolist())
            rings_y.append(ext[:, 1].tolist())
            for interior in poly.interiors:
                ring = np.asarray(interior.coords)
                rings_x.append(ring[:, 0].tolist())
                rings_y.append(ring[:, 1].tolist())
            feature_xs.append(rings_x)
            feature_ys.append(rings_y)
        all_xs.append(feature_xs)
        all_ys.append(feature_ys)
    return all_xs, all_ys


def initial_quantile_colors(values, palette):
    arr = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    finite = arr[np.isfinite(arr)]
    if not len(finite):
        return ["#d9d9d9"] * len(arr)
    breaks = np.quantile(finite, [0.2, 0.4, 0.6, 0.8])
    bins = np.searchsorted(breaks, arr, side="right")
    return [palette[int(i)] if np.isfinite(v) else "#d9d9d9" for i, v in zip(bins, arr)]


def fmt_int(value: float) -> str:
    return f"{int(round(float(value))):,}"


def build_dashboard() -> None:
    report = json.loads((DATA / "data_quality_report.json").read_text(encoding="utf-8"))
    kriging_meta = json.loads((DATA / "kriging_metadata.json").read_text(encoding="utf-8"))
    inventory = pd.read_csv(DATA / "gdb_layer_inventory.csv")
    totals = report["totals"]
    counts_report = report["counts"]

    tracts = load_geojson("tracts_web.geojson")
    parcels = load_geojson("parcels_web.geojson")
    county = load_geojson("county_web.geojson")
    zipcodes = load_geojson("zipcodes_web.geojson")
    precincts = load_geojson("commissioner_precincts_web.geojson")
    housing_grid = load_geojson("housing_grid.geojson")
    climate = pd.read_csv(DATA / "climate_points.csv")
    sf_sample = pd.read_csv(DATA / "sf_sample.csv")
    mf_points = pd.read_csv(DATA / "mf_points.csv")

    tract_xs, tract_ys = to_multipolygon_arrays(tracts.geometry)
    parcel_xs, parcel_ys = to_multipolygon_arrays(parcels.geometry)
    county_xs, county_ys = to_multipolygon_arrays(county.geometry)
    zipcode_xs, zipcode_ys = to_multipolygon_arrays(zipcodes.geometry)
    precinct_xs, precinct_ys = to_multipolygon_arrays(precincts.geometry)
    grid_xs, grid_ys = to_multipolygon_arrays(housing_grid.geometry)

    # Boundary-to-tract relationships support transparent screening summaries
    # in the one-page report. These lists are not source-data aggregations; they
    # identify census tracts whose geometry intersects each locator boundary.
    zipcode_tract_indices = [
        np.flatnonzero(tracts.geometry.intersects(geom)).astype(int).tolist()
        for geom in zipcodes.geometry
    ]
    precinct_tract_indices = [
        np.flatnonzero(tracts.geometry.intersects(geom)).astype(int).tolist()
        for geom in precincts.geometry
    ]

    tract_fields = [
        "GEOID", "NAME", "LOCATION", "CHEI_2020", "CHEI_2050", "adapt_gap",
        "pr_15", "pr_20", "pr_25", "pr_30", "delta_mm", "sens_pct", "SVI",
        "hp_2020", "hp_2050", "pop_chg", "hh_2020", "hh_2050", "hh_chg",
        "j_2020", "j_2050", "job_chg", "pop_den", "n_single_f", "n_multi_fa",
        "parcel_hu_change", "hotspot_sc", "hotspot_ca", "centroid_x", "centroid_y",
        "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy",
    ]
    tract_data: dict[str, Any] = {"xs": tract_xs, "ys": tract_ys}
    for field in tract_fields:
        if field not in tracts:
            continue
        series = tracts[field]
        if pd.api.types.is_numeric_dtype(series):
            tract_data[field] = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
        else:
            tract_data[field] = series.fillna("").astype(str).tolist()
    # Reconstruct the eight-category compound-hotspot typology using the
    # documented countywide 80th-percentile thresholds. Precipitation is rounded
    # to the displayed three decimals so the classification exactly reproduces
    # the supplied 0–3 hotspot score.
    hazard_high = np.round(pd.to_numeric(tracts["pr_25"], errors="coerce").to_numpy(dtype=float), 3) >= HOTSPOT_PRECIP_THRESHOLD
    growth_high = pd.to_numeric(tracts["hh_chg"], errors="coerce").to_numpy(dtype=float) >= HOTSPOT_HOUSEHOLD_THRESHOLD
    svi_high = pd.to_numeric(tracts["SVI"], errors="coerce").to_numpy(dtype=float) >= HOTSPOT_SVI_THRESHOLD
    hotspot_score = hazard_high.astype(int) + growth_high.astype(int) + svi_high.astype(int)
    hotspot_combo = []
    for h, g, v in zip(hazard_high, growth_high, svi_high):
        if h and g and v:
            hotspot_combo.append("All three high")
        elif h and g:
            hotspot_combo.append("Hazard + growth")
        elif h and v:
            hotspot_combo.append("Hazard + SVI")
        elif g and v:
            hotspot_combo.append("Growth + SVI")
        elif h:
            hotspot_combo.append("Hazard only")
        elif g:
            hotspot_combo.append("Growth only")
        elif v:
            hotspot_combo.append("SVI only")
        else:
            hotspot_combo.append("None high")
    tract_data["hazard_high"] = hazard_high.astype(int)
    tract_data["growth_high"] = growth_high.astype(int)
    tract_data["svi_high"] = svi_high.astype(int)
    tract_data["hotspot_score"] = hotspot_score
    tract_data["hotspot_combo"] = hotspot_combo
    tract_data["hotspot_fill"] = [HOTSPOT_NEUTRAL_FILLS[value] for value in hotspot_combo]

    tract_data["fill_color"] = initial_quantile_colors(tract_data["CHEI_2050"], SEQ_BLUE)
    tract_data["display_label"] = ["Climate Housing Exposure Index, 2050"] * len(tracts)
    tract_data["display_value"] = [f"{v:.3f}" if np.isfinite(v) else "No data" for v in tract_data["CHEI_2050"]]
    tract_source = ColumnDataSource(tract_data, name="tract_source")

    # Condition-specific geometry sources keep the semantic overlay system
    # efficient: a tract is included only in the pattern source(s) corresponding
    # to the high conditions it actually meets. Across all three sources this
    # requires 671 geometry draws rather than drawing every tract three times.
    hotspot_sources: dict[str, ColumnDataSource] = {}
    for condition, mask in {
        "hazard": hazard_high,
        "growth": growth_high,
        "svi": svi_high,
    }.items():
        indices = np.flatnonzero(mask).tolist()
        hotspot_sources[condition] = ColumnDataSource({
            "xs": [tract_data["xs"][i] for i in indices],
            "ys": [tract_data["ys"][i] for i in indices],
        }, name=f"hotspot_{condition}_source")

    parcel_data = {
        "xs": parcel_xs,
        "ys": parcel_ys,
        "ParcelID": parcels["ParcelID"].fillna("").astype(str).tolist(),
        "current_label": parcels["Label_Current_Land_Use"].fillna("Unknown").astype(str).tolist(),
        "future_label": parcels["Label_Land_Use_2050"].fillna("Unknown").astype(str).tolist(),
        "current_units": pd.to_numeric(parcels["Housing_Units_Current"], errors="coerce").fillna(0).to_numpy(dtype=float),
        "future_units": pd.to_numeric(parcels["Housing_Units_2050"], errors="coerce").fillna(0).to_numpy(dtype=float),
        "hu_change": pd.to_numeric(parcels["hu_change"], errors="coerce").fillna(0).to_numpy(dtype=float),
    }
    parcel_data["fill_color"] = initial_quantile_colors(parcel_data["hu_change"], SEQ_ORANGE)
    parcel_data["display_value"] = [f"{v:,.0f}" for v in parcel_data["hu_change"]]
    parcel_source = ColumnDataSource(parcel_data, name="parcel_source")

    climate_source = ColumnDataSource({
        "x": climate["x"].to_numpy(dtype=float),
        "y": climate["y"].to_numpy(dtype=float),
        "gmt": climate["gmt"].to_numpy(dtype=float),
        "precip": climate["precip_mm"].to_numpy(dtype=float),
    }, name="climate_master_source")
    climate_initial = climate.loc[np.isclose(climate["gmt"], 2.5)]
    climate_display_source = ColumnDataSource({
        "x": climate_initial["x"].to_numpy(dtype=float),
        "y": climate_initial["y"].to_numpy(dtype=float),
        "gmt": climate_initial["gmt"].to_numpy(dtype=float),
        "precip": climate_initial["precip_mm"].to_numpy(dtype=float),
        "color": initial_quantile_colors(climate_initial["precip_mm"], SEQ_BLUE),
        "display_alpha": np.full(len(climate_initial), 0.90, dtype=float),
    }, name="climate_display_source")

    grid_data = {
        "xs": grid_xs,
        "ys": grid_ys,
        "grid_id": housing_grid["grid_id"].astype(str).tolist(),
        "sf_count": housing_grid["sf_count"].to_numpy(dtype=float),
        "mf_count": housing_grid["mf_count"].to_numpy(dtype=float),
        "total_count": housing_grid["total_count"].to_numpy(dtype=float),
    }
    grid_data["fill_color"] = initial_quantile_colors(grid_data["total_count"], SEQ_TEAL)
    grid_data["display_value"] = [f"{v:,.0f}" for v in grid_data["total_count"]]
    grid_source = ColumnDataSource(grid_data, name="housing_grid_source")

    sf_x, sf_y = sf_sample["x"].to_numpy(dtype=float), sf_sample["y"].to_numpy(dtype=float)
    mf_x, mf_y = mf_points["x"].to_numpy(dtype=float), mf_points["y"].to_numpy(dtype=float)
    housing_sample_source = ColumnDataSource({
        "sf_x": [sf_x.tolist()], "sf_y": [sf_y.tolist()],
        "mf_x": [mf_x.tolist()], "mf_y": [mf_y.tolist()],
    }, name="housing_sample_source")
    housing_point_source = ColumnDataSource({
        "x": np.concatenate([sf_x, mf_x]), "y": np.concatenate([sf_y, mf_y]),
        "color": [TEAL] * len(sf_x) + ["#F16913"] * len(mf_x),
        "kind": ["Single-family"] * len(sf_x) + ["Multi-family"] * len(mf_x),
        "display_alpha": np.full(len(sf_x) + len(mf_x), 0.58, dtype=float),
    }, name="housing_point_source")
    county_source = ColumnDataSource({"xs": county_xs, "ys": county_ys}, name="county_source")
    zipcode_source = ColumnDataSource({
        "xs": zipcode_xs,
        "ys": zipcode_ys,
        "ZIP": zipcodes["ZIP"].fillna("").astype(str).tolist(),
        "POSTAL": zipcodes["POSTAL"].fillna("").astype(str).tolist(),
        "STATE": zipcodes["STATE"].fillna("TX").astype(str).tolist(),
        "ZIP_TYPE": zipcodes["ZIP_TYPE"].fillna("").astype(str).tolist(),
        "bbox_minx": pd.to_numeric(zipcodes["bbox_minx"], errors="coerce").to_numpy(dtype=float),
        "bbox_miny": pd.to_numeric(zipcodes["bbox_miny"], errors="coerce").to_numpy(dtype=float),
        "bbox_maxx": pd.to_numeric(zipcodes["bbox_maxx"], errors="coerce").to_numpy(dtype=float),
        "bbox_maxy": pd.to_numeric(zipcodes["bbox_maxy"], errors="coerce").to_numpy(dtype=float),
        "tract_indices": zipcode_tract_indices,
    }, name="zipcode_source")
    selected_zip_source = ColumnDataSource({
        "xs": [], "ys": [], "ZIP": [], "POSTAL": [], "STATE": [], "ZIP_TYPE": [],
        "tract_indices": [],
    }, name="selected_zip_source")
    precinct_source = ColumnDataSource({
        "xs": precinct_xs,
        "ys": precinct_ys,
        "PCT_NO": pd.to_numeric(precincts["PCT_NO"], errors="coerce").fillna(0).astype(int).tolist(),
        "AREA_IN_MI": pd.to_numeric(precincts["AREA_IN_MI"], errors="coerce").to_numpy(dtype=float),
        "bbox_minx": pd.to_numeric(precincts["bbox_minx"], errors="coerce").to_numpy(dtype=float),
        "bbox_miny": pd.to_numeric(precincts["bbox_miny"], errors="coerce").to_numpy(dtype=float),
        "bbox_maxx": pd.to_numeric(precincts["bbox_maxx"], errors="coerce").to_numpy(dtype=float),
        "bbox_maxy": pd.to_numeric(precincts["bbox_maxy"], errors="coerce").to_numpy(dtype=float),
        "tract_indices": precinct_tract_indices,
    }, name="precinct_source")
    selected_precinct_source = ColumnDataSource({
        "xs": [], "ys": [], "PCT_NO": [], "AREA_IN_MI": [], "tract_indices": [],
    }, name="selected_precinct_source")

    # Dedicated overlay sources keep legend filtering separate from map-click
    # selection, so the tract profile continues to work while one legend class
    # is highlighted.
    legend_mask_source = ColumnDataSource({"xs": [], "ys": []}, name="legend_mask_source")
    legend_highlight_polygon_source = ColumnDataSource({"xs": [], "ys": []}, name="legend_highlight_polygon_source")
    legend_highlight_point_source = ColumnDataSource({"x": [], "y": []}, name="legend_highlight_point_source")

    minx, miny, maxx, maxy = county.total_bounds
    padx, pady = (maxx - minx) * 0.025, (maxy - miny) * 0.025
    map_plot = figure(
        x_axis_type="mercator", y_axis_type="mercator",
        x_range=Range1d(minx - padx, maxx + padx), y_range=Range1d(miny - pady, maxy + pady),
        height=720, width=MAP_PLOT_WIDTH, tools="pan,wheel_zoom,box_zoom,reset,save,tap",
        active_scroll="wheel_zoom", match_aspect=True, toolbar_location="right",
        title="Climate–Housing Exposure Explorer", output_backend="canvas",
    )
    map_plot.toolbar.logo = None
    map_plot.background_fill_color = "#EAF0F3"
    map_plot.border_fill_color = "#FFFFFF"
    map_plot.outline_line_color = "#CBD5DC"
    map_plot.grid.visible = False
    map_plot.axis.visible = False
    map_plot.title.text_font_size = "15pt"
    map_plot.title.text_color = NAVY
    tile_source = WMTSTileSource(
        url="https://a.basemaps.cartocdn.com/light_all/{Z}/{X}/{Y}.png",
        attribution="© OpenStreetMap contributors © CARTO",
    )
    map_plot.add_tile(tile_source, alpha=0.66)

    # Kriging images must be above the tile layer and below tract outlines.
    bounds = tuple(map(float, county.total_bounds))
    kriging_renderers = {}
    for code in ["15", "20", "25", "30"]:
        rgba = np.load(DATA / f"kriging_gmt_{code}_rgba.npy")
        source = ColumnDataSource({
            "image": [rgba], "x": [bounds[0]], "y": [bounds[1]],
            "dw": [bounds[2] - bounds[0]], "dh": [bounds[3] - bounds[1]],
        }, name=f"kriging_source_{code}")
        renderer = map_plot.image_rgba(
            image="image", x="x", y="y", dw="dw", dh="dh", source=source,
            global_alpha=0.84, visible=False, level="glyph", name=f"kriging_{code}",
        )
        kriging_renderers[code] = renderer

    grid_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=grid_source, fill_color="fill_color", fill_alpha=0.75,
        line_color=None, visible=False, name="housing_grid",
    )
    parcel_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=parcel_source, fill_color="fill_color", fill_alpha=0.80,
        line_color="#ffffff", line_alpha=0.20, line_width=0.25, visible=False, name="parcels",
    )
    tract_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=tract_source, fill_color="fill_color", fill_alpha=0.82,
        line_color="#ffffff", line_alpha=0.72, line_width=0.52,
        selection_fill_color=GOLD, selection_fill_alpha=0.90,
        selection_line_color="#111111", selection_line_width=2.2,
        nonselection_fill_alpha=0.76, name="tracts",
    )
    # Pattern semantics: diagonal lines = precipitation hazard; vertical lines
    # = household growth; dots = social vulnerability. Tracts meeting multiple
    # conditions receive multiple overlays, producing the agreed combination
    # patterns while drawing only the condition-positive geometries.
    hotspot_hazard_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=hotspot_sources["hazard"],
        fill_alpha=0.0, line_alpha=0.001, line_width=0.10,
        hatch_pattern="right_diagonal_line", hatch_color="#263B4A",
        hatch_alpha=0.74, hatch_scale=15.0, hatch_weight=1.05,
        visible=False, level="annotation", name="hotspot_pattern_hazard",
    )
    hotspot_growth_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=hotspot_sources["growth"],
        fill_alpha=0.0, line_alpha=0.001, line_width=0.10,
        hatch_pattern="vertical_line", hatch_color="#263B4A",
        hatch_alpha=0.74, hatch_scale=15.0, hatch_weight=1.05,
        visible=False, level="annotation", name="hotspot_pattern_growth",
    )
    hotspot_svi_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=hotspot_sources["svi"],
        fill_alpha=0.0, line_alpha=0.001, line_width=0.10,
        hatch_pattern="dot", hatch_color="#263B4A",
        hatch_alpha=0.78, hatch_scale=14.0, hatch_weight=1.15,
        visible=False, level="annotation", name="hotspot_pattern_svi",
    )
    hotspot_pattern_renderers = [
        hotspot_hazard_renderer, hotspot_growth_renderer, hotspot_svi_renderer,
    ]
    climate_renderer = map_plot.scatter(
        x="x", y="y", source=climate_display_source, marker="circle", size=8,
        fill_color="color", fill_alpha="display_alpha", line_color="#ffffff", line_width=0.7,
        visible=False, name="climate_points",
    )
    housing_point_renderer = map_plot.scatter(
        x="x", y="y", source=housing_point_source, marker="circle", size=3.2,
        fill_color="color", fill_alpha="display_alpha", line_color=None,
        visible=False, name="housing_points",
    )
    map_plot.multi_polygons(
        xs="xs", ys="ys", source=county_source, fill_alpha=0.0,
        line_color=NAVY, line_width=2.3, line_alpha=0.96, level="annotation", name="county_boundary",
    )
    legend_mask_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=legend_mask_source, fill_color="#FFFFFF", fill_alpha=0.58,
        line_alpha=0.0, visible=True, level="overlay", name="legend_nonmatch_mask",
    )
    all_zip_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=zipcode_source, fill_alpha=0.0,
        line_color="#385A6D", line_width=0.85, line_alpha=0.46,
        visible=False, level="overlay", name="all_zip_boundaries",
    )
    all_precinct_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=precinct_source, fill_alpha=0.0,
        line_color="#6A4C93", line_dash="dashed", line_width=1.7, line_alpha=0.72,
        visible=False, level="overlay", name="all_commissioner_precinct_boundaries",
    )
    legend_highlight_polygon_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=legend_highlight_polygon_source,
        fill_color=GOLD, fill_alpha=0.08, line_color=GOLD, line_width=3.2, line_alpha=1.0,
        visible=True, level="overlay", name="legend_matching_polygons",
    )
    legend_highlight_point_renderer = map_plot.scatter(
        x="x", y="y", source=legend_highlight_point_source, marker="circle", size=12,
        fill_color=GOLD, fill_alpha=0.26, line_color=NAVY, line_width=1.8,
        visible=True, level="overlay", name="legend_matching_points",
    )
    selected_zip_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=selected_zip_source,
        fill_color=GOLD, fill_alpha=0.055, line_color=GOLD,
        line_width=4.0, line_alpha=1.0, visible=True, level="overlay",
        name="selected_zip_boundary",
    )
    selected_precinct_renderer = map_plot.multi_polygons(
        xs="xs", ys="ys", source=selected_precinct_source,
        fill_color="#4CB8BE", fill_alpha=0.045, line_color="#7A4FA3",
        line_width=4.2, line_alpha=1.0, visible=True, level="overlay",
        name="selected_commissioner_precinct_boundary",
    )

    map_plot.add_tools(HoverTool(renderers=[tract_renderer], tooltips=[
        ("Census tract", "@GEOID"), ("Layer", "@display_label"), ("Value", "@display_value"),
        ("GMT 2.5°C precipitation", "@pr_25{0.0} mm"), ("SVI 2020", "@SVI{0.000}"),
        ("Population change", "@pop_chg{0,0}"), ("Household change", "@hh_chg{0,0}"),
        ("Employment change", "@job_chg{0,0}"),
        ("Compound hotspot", "@hotspot_combo"), ("Hotspot score", "@hotspot_score{0}"),
    ]))
    map_plot.add_tools(HoverTool(renderers=[parcel_renderer], tooltips=[
        ("Parcel ID", "@ParcelID"), ("Current land use", "@current_label"),
        ("Future land use", "@future_label"), ("Housing-unit change", "@hu_change{0,0}"),
    ]))
    map_plot.add_tools(HoverTool(renderers=[climate_renderer], tooltips=[
        ("GMT threshold", "@gmt{0.0}°C"), ("3-day precipitation", "@precip{0.0} mm"),
    ]))
    map_plot.add_tools(HoverTool(renderers=[grid_renderer], tooltips=[
        ("Single-family records", "@sf_count{0,0}"), ("Multi-family records", "@mf_count{0,0}"),
        ("Total housing records", "@total_count{0,0}"),
    ]))
    map_plot.add_tools(HoverTool(renderers=[housing_point_renderer], tooltips=[("Housing stock", "@kind")]))
    map_plot.add_tools(HoverTool(renderers=[all_zip_renderer, selected_zip_renderer], tooltips=[
        ("ZIP code", "@ZIP"), ("Postal name", "@POSTAL"), ("Type", "@ZIP_TYPE"),
    ]))
    map_plot.add_tools(HoverTool(renderers=[all_precinct_renderer, selected_precinct_renderer], tooltips=[
        ("Commissioner precinct", "Precinct @PCT_NO"), ("Area", "@AREA_IN_MI{0} sq mi"),
    ]))
    tap_tool = map_plot.select_one(TapTool)
    if tap_tool is not None:
        tap_tool.renderers = [tract_renderer]

    layer_meta = {
        "chei_2050": {"label": "Composite • Climate Housing Exposure Index, 2050", "short": "CHEI (2050)", "source": "tract", "field": "CHEI_2050", "kind": "seq", "palette": SEQ_BLUE, "unit": "index", "decimals": 3, "description": "Projected tract-level CHEI for 2050, combining precipitation hazard, projected housing exposure, and social vulnerability."},
        "chei_2020": {"label": "Composite • Climate Housing Exposure Index, 2020", "short": "CHEI (2020)", "source": "tract", "field": "CHEI_2020", "kind": "seq", "palette": SEQ_BLUE, "unit": "index", "decimals": 3, "description": "Baseline tract-level Climate Housing Exposure Index for 2020."},
        "adapt_gap": {"label": "Composite • CHEI adaptation gap, 2020–2050", "short": "CHEI change", "source": "tract", "field": "adapt_gap", "kind": "div", "unit": "index change", "decimals": 3, "description": "CHEI in 2050 minus CHEI in 2020. Positive values indicate a higher modeled exposure index in 2050."},
        "hotspot": {"label": "Composite • Compound climate-inequality hotspots, 2050", "short": "Hotspot combination", "source": "tract", "field": "hotspot_combo", "kind": "cat_hotspot", "description": "Eight-category, noncompensatory typology showing which high precipitation, household-growth, and social-vulnerability conditions occur together in each tract."},
        "pr_tract": {"label": "Climate • Extreme 3-day precipitation by GMT (tract)", "short": "3-day precipitation", "source": "tract", "field": "pr_dynamic", "kind": "seq", "palette": SEQ_BLUE, "unit": "mm", "decimals": 1, "description": "Average three-day precipitation sum for extreme events during the 20-year period associated with the selected GMT threshold, aggregated to census tracts."},
        "pr_change": {"label": "Climate • Precipitation change, GMT 2.5°C vs 1.5°C", "short": "Precipitation change", "source": "tract", "field": "sens_pct", "kind": "seq", "palette": SEQ_PURPLE, "unit": "%", "decimals": 1, "description": "Percentage change in average extreme three-day precipitation at GMT 2.5°C relative to GMT 1.5°C."},
        "pr_points": {"label": "Climate • GMT model precipitation points", "short": "Model-point precipitation", "source": "climate_points", "field": "precip", "kind": "seq", "palette": SEQ_BLUE, "unit": "mm", "decimals": 1, "description": "Uploaded climate-model point values for the selected GMT threshold."},
        "pr_kriging": {"label": "Climate • GMT precipitation kriging surface", "short": "Kriging precipitation", "source": "kriging", "field": "pr_dynamic", "kind": "seq", "palette": SEQ_BLUE, "unit": "mm", "decimals": 1, "description": "Derived ordinary-kriging display surface fitted to the uploaded point layer because the named GDB kriging raster was not exposed by the open-source FileGDB reader."},
        "pop_2050": {"label": "Growth • Projected population, 2050", "short": "Population (2050)", "source": "tract", "field": "hp_2050", "kind": "seq", "palette": SEQ_TEAL, "unit": "people", "decimals": 0, "description": "Projected census tract population in 2050."},
        "pop_growth": {"label": "Growth • Population change, 2020–2050", "short": "Population change", "source": "tract", "field": "pop_chg", "kind": "div", "unit": "people", "decimals": 0, "description": "Projected population change between 2020 and 2050."},
        "hh_2050": {"label": "Growth • Projected households, 2050", "short": "Households (2050)", "source": "tract", "field": "hh_2050", "kind": "seq", "palette": SEQ_TEAL, "unit": "households", "decimals": 0, "description": "Projected census tract households in 2050."},
        "hh_growth": {"label": "Growth • Household change, 2020–2050", "short": "Household change", "source": "tract", "field": "hh_chg", "kind": "div", "unit": "households", "decimals": 0, "description": "Projected household change between 2020 and 2050."},
        "jobs_2050": {"label": "Growth • Projected employment, 2050", "short": "Employment (2050)", "source": "tract", "field": "j_2050", "kind": "seq", "palette": SEQ_ORANGE, "unit": "jobs", "decimals": 0, "description": "Projected census tract employment in 2050."},
        "jobs_growth": {"label": "Growth • Employment change, 2020–2050", "short": "Employment change", "source": "tract", "field": "job_chg", "kind": "div", "unit": "jobs", "decimals": 0, "description": "Projected employment change between 2020 and 2050."},
        "svi": {"label": "Equity • Social Vulnerability Index, 2020", "short": "SVI (2020)", "source": "tract", "field": "SVI", "kind": "seq", "palette": SEQ_PURPLE, "unit": "percentile", "decimals": 3, "description": "CDC Social Vulnerability Index overall percentile at the census tract level."},
        "pop_density": {"label": "Equity • Population density, 2020", "short": "Population density", "source": "tract", "field": "pop_den", "kind": "seq", "palette": SEQ_PURPLE, "unit": "source density unit", "decimals": 0, "description": "Provided tract-level population-density field for 2020."},
        "sf_tract": {"label": "Housing • Single-family housing records, 2020 (tract)", "short": "Single-family records", "source": "tract", "field": "n_single_f", "kind": "seq", "palette": SEQ_TEAL, "unit": "records", "decimals": 0, "description": "Count of provided single-family housing-stock records by tract."},
        "mf_tract": {"label": "Housing • Multi-family housing records, 2020 (tract)", "short": "Multi-family records", "source": "tract", "field": "n_multi_fa", "kind": "seq", "palette": SEQ_ORANGE, "unit": "records", "decimals": 0, "description": "Count of provided multi-family housing-stock records by tract."},
        "housing_density": {"label": "Housing • Housing-stock distribution (1 km grid)", "short": "Housing records per cell", "source": "grid", "field": "total_count", "kind": "seq", "palette": SEQ_TEAL, "unit": "records per cell", "decimals": 0, "description": "Full-record density grid calculated from all uploaded single- and multi-family point locations."},
        "housing_points": {"label": "Housing • Housing-stock point distribution", "short": "Housing-stock locations", "source": "housing_points", "field": "point", "kind": "points", "description": "Viewport-filtered source point locations when run through server.py; the standalone HTML uses a deterministic single-family sample and all multi-family points."},
        "parcel_hu_change": {"label": "Parcels • Housing-unit change, 2020–2050", "short": "Housing-unit change", "source": "parcel", "field": "hu_change", "kind": "seq", "palette": SEQ_ORANGE, "unit": "housing units", "decimals": 0, "description": "Projected parcel-level housing units in 2050 minus current housing units."},
        "parcel_current_lu": {"label": "Parcels • Current land use, 2020", "short": "Current land use", "source": "parcel", "field": "current_label", "kind": "cat_land", "description": "Broad current parcel land-use category for parcels with projected housing-unit change by 2050."},
        "parcel_future_lu": {"label": "Parcels • Future land use, 2050", "short": "Future land use", "source": "parcel", "field": "future_label", "kind": "cat_land", "description": "Broad projected parcel land-use category in 2050 for parcels with housing-unit change."},
    }
    layer_guidance = {
        "chei_2050": ["Geography: census tracts; projection year: 2050.", "Higher values indicate greater combined climate–housing exposure.", "Use for integrated adaptation and housing-resilience screening."],
        "chei_2020": ["Geography: census tracts; baseline year: 2020.", "Higher values indicate greater baseline combined exposure.", "Use as a reference for comparison with 2050 conditions."],
        "adapt_gap": ["Calculated as CHEI 2050 minus CHEI 2020.", "Positive values indicate increasing modeled exposure; negative values indicate decline.", "Use to identify potential adaptation gaps over time."],
        "hotspot": ["One point is assigned for each high condition; the score is noncompensatory.", "Diagonal lines denote precipitation hazard, vertical lines denote household growth, and dots denote social vulnerability.", "Overlaid patterns preserve all eight combinations without relying on color alone."],
        "pr_tract": ["Geography: census tracts; switch among four GMT thresholds.", "Values represent average three-day totals for modeled extreme events.", "Use to compare the spatial pattern of precipitation hazard as warming increases."],
        "pr_change": ["Compares GMT +2.5°C with GMT +1.5°C.", "Higher percentages indicate larger modeled increases in extreme precipitation.", "Use to screen climate-sensitivity patterns across tracts."],
        "pr_points": ["Geography: 246 climate-model points per GMT threshold.", "Point values are the inputs underlying tract summaries and interpolation.", "Use to inspect the spatial support of the climate layer."],
        "pr_kriging": ["Continuous display surface derived from the uploaded model points.", "Select a GMT threshold to compare interpolated precipitation patterns.", "Use for visualization; consult original points and tract values for verification."],
        "pop_2050": ["Geography: census tracts; projection year: 2050.", "Darker tracts contain more projected residents.", "Use to locate future population exposure and service demand."],
        "pop_growth": ["Change is calculated from 2020 to 2050.", "Positive values indicate projected growth; negative values indicate decline.", "Use to identify where future development pressure may alter exposure."],
        "hh_2050": ["Geography: census tracts; projection year: 2050.", "Values represent projected occupied households.", "Use to assess future residential concentration."],
        "hh_growth": ["Change is calculated from 2020 to 2050.", "The compound-hotspot typology treats growth of at least 746 households as high.", "Use to identify preventive adaptation needs created by future development."],
        "jobs_2050": ["Geography: census tracts; projection year: 2050.", "Values represent projected employment counts.", "Use to assess future workplace and economic exposure."],
        "jobs_growth": ["Change is calculated from 2020 to 2050.", "Positive values indicate projected employment growth.", "Use to screen future infrastructure and continuity-planning needs."],
        "svi": ["Geography: census tracts; baseline year: 2020.", "Higher percentiles indicate greater relative social vulnerability.", "The compound-hotspot typology treats SVI of at least 0.88386 as high."],
        "pop_density": ["Geography: census tracts; baseline year: 2020.", "Higher values represent greater population concentration.", "Use to contextualize exposure intensity and potential evacuation or service needs."],
        "sf_tract": ["Counts provided single-family housing records by census tract.", "Higher values indicate larger concentrations of single-family stock.", "Use to compare housing-form exposure and resilience needs."],
        "mf_tract": ["Counts provided multi-family housing records by census tract.", "Higher values indicate larger concentrations of multi-family stock.", "Use to identify renter- and building-scale resilience priorities."],
        "housing_density": ["A 1 km grid summarizes every uploaded housing-stock point.", "Switch between single-family, multi-family, or combined records.", "Use for countywide housing concentration without rendering every point."],
        "housing_points": ["Shows housing-stock locations as points.", "The static page uses a representative single-family sample and all multi-family points.", "Run server.py to query the complete point inventory by map viewport."],
        "parcel_hu_change": ["Geography: parcels with projected housing change.", "Positive values indicate net additional housing units by 2050.", "Use to identify fine-scale development pressure and adaptation opportunities."],
        "parcel_current_lu": ["Shows 2020 land-use categories for changing parcels.", "Colors represent categories rather than a numeric ranking.", "Use to understand the baseline development context."],
        "parcel_future_lu": ["Shows projected 2050 land-use categories for changing parcels.", "Compare with the 2020 layer to interpret land-use transitions.", "Use for long-range growth and resilience planning."],
    }
    for key, meta in layer_meta.items():
        meta["bullets"] = layer_guidance[key]

    layer_select = Select(title="Primary map layer", value="chei_2050", options=[(k, v["label"]) for k, v in layer_meta.items()], width=CONTROL_CONTENT_WIDTH, name="primary_layer_select")
    gmt_select = Select(title="GMT threshold", value="25", options=[("15", "1.5°C"), ("20", "2.0°C"), ("25", "2.5°C"), ("30", "3.0°C")], width=158, visible=False, name="gmt_threshold_select")
    housing_select = Select(title="Housing-stock display", value="combined", options=[("single", "Single-family"), ("multi", "Multi-family"), ("combined", "Combined")], width=167, visible=False)
    opacity_slider = Slider(title="Layer opacity", start=0.25, end=1.0, step=0.05, value=0.82, width=CONTROL_CONTENT_WIDTH)
    overlap_toggle = Toggle(label="Enable high–high overlap analysis", active=False, button_type="primary", width=CONTROL_CONTENT_WIDTH)
    overlap_a = Select(title="Overlap factor A", value="pr_25", options=[
        ("pr_15", "GMT 1.5°C precipitation"), ("pr_20", "GMT 2.0°C precipitation"),
        ("pr_25", "GMT 2.5°C precipitation"), ("pr_30", "GMT 3.0°C precipitation"),
        ("SVI", "Social vulnerability"), ("CHEI_2050", "CHEI 2050"),
    ], width=CONTROL_CONTENT_WIDTH, visible=False)
    overlap_b = Select(title="Overlap factor B", value="hh_chg", options=[
        ("pop_chg", "Population growth"), ("hh_chg", "Household growth"),
        ("job_chg", "Employment growth"), ("parcel_hu_change", "Parcel housing-unit change"),
        ("SVI", "Social vulnerability"), ("CHEI_2050", "CHEI 2050"),
    ], width=CONTROL_CONTENT_WIDTH, visible=False)
    threshold_slider = Slider(title="High-value threshold (percentile)", start=60, end=95, step=5, value=80, width=CONTROL_CONTENT_WIDTH, visible=False)
    search_input = TextInput(title="Find census tract GEOID", placeholder="e.g., 48201342001", width=250, name="tract_search_input")
    search_button = Button(label="Find", button_type="primary", width=75, name="tract_search_button")
    zip_search_input = TextInput(title="Find ZIP code", placeholder="e.g., 77007", width=250, name="zip_search_input")
    zip_search_button = Button(label="Find", button_type="primary", width=75, name="zip_search_button")
    show_all_zip_toggle = Toggle(
        label="Show all ZIP-code boundaries", active=False, width=CONTROL_CONTENT_WIDTH, name="show_all_zip_toggle",
    )
    precinct_select = Select(
        title="Select commissioner precinct", value="1",
        options=[("1", "Precinct 1"), ("2", "Precinct 2"), ("3", "Precinct 3"), ("4", "Precinct 4")],
        width=250, name="precinct_select",
    )
    precinct_find_button = Button(label="Find", button_type="primary", width=75, name="precinct_find_button")
    show_all_precinct_toggle = Toggle(
        label="Show all commissioner precinct boundaries", active=False, width=CONTROL_CONTENT_WIDTH, name="show_all_precinct_toggle",
    )
    reset_button = Button(label="Reset map extent", width=CONTROL_CONTENT_WIDTH)
    init_trigger = Toggle(active=False, visible=False, name="dashboard_init_trigger", width=1, height=1)

    legend_div = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=180, css_classes=["chei-panel", "legend-panel"])
    legend_filter_status = Div(
        text="<span class='legend-help'>Click one legend class to highlight matching features.</span>",
        width=CONTROL_CONTENT_WIDTH, min_height=52, css_classes=["legend-filter-status"], name="legend_filter_status",
    )
    layer_info = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=175, css_classes=["chei-panel", "info-panel"])
    overlap_summary = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=165, visible=False, css_classes=["chei-panel", "overlap-panel"])
    point_status = Div(text="", width=MAP_PLOT_WIDTH, min_height=42, css_classes=["map-status"])
    map_guide = Div(text="", width=MAP_PLOT_WIDTH, min_height=180, css_classes=["map-guide-wrapper"])
    map_actions = Div(text="", width=MAP_PLOT_WIDTH, min_height=175, css_classes=["map-actions-wrapper"])
    search_status = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=28, css_classes=["search-status"])
    zip_search_status = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=42, css_classes=["search-status", "zip-search-status"])
    precinct_search_status = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=42, css_classes=["search-status", "precinct-search-status"])

    quick_exposure_button = Button(label="Highest overall exposure", button_type="primary", width=178, height=54, css_classes=["quick-action"], name="quick_exposure_button")
    quick_overlap_button = Button(label="Three-factor overlap", width=178, height=54, css_classes=["quick-action"], name="quick_overlap_button")
    quick_adaptation_button = Button(label="Emerging adaptation needs", width=178, height=54, css_classes=["quick-action"], name="quick_adaptation_button")
    quick_selected_button = Button(label="Selected-place conditions", width=178, height=54, css_classes=["quick-action"], name="quick_selected_button")
    quick_decision_status = Div(
        text="<div class='quick-status'><b>Choose a decision question.</b><p>The dashboard will activate an appropriate layer and focus the most relevant class or selected geography.</p></div>",
        width=INSIGHT_CONTENT_WIDTH, min_height=92, css_classes=["quick-decision-status"], name="quick_decision_status",
    )
    report_geography = Select(
        title="Geography for one-page report", value="tract",
        options=[("tract", "Selected census tract"), ("zip", "Selected ZIP code"), ("precinct", "Selected commissioner precinct")],
        width=INSIGHT_CONTENT_WIDTH, name="report_geography_select",
    )
    report_button = Button(label="Generate one-page decision brief", button_type="primary", width=INSIGHT_CONTENT_WIDTH, height=42, name="report_button")
    report_status = Div(
        text="<span class='locator-note'>Select a geography, then open a print-ready brief that can be saved as PDF.</span>",
        width=INSIGHT_CONTENT_WIDTH, min_height=52, css_classes=["report-status"], name="report_status",
    )

    initial_values = np.asarray(tract_data["CHEI_2050"], dtype=float)
    counts, edges = np.histogram(initial_values[np.isfinite(initial_values)], bins=12)
    hist_source = ColumnDataSource({"left": edges[:-1], "right": edges[1:], "top": counts, "color": [SEQ_BLUE[3]] * len(counts)})
    hist_plot = figure(height=235, width=CONTROL_CONTENT_WIDTH, title="Distribution across census tracts", tools="", toolbar_location=None, min_border_left=54, min_border_right=18, min_border_bottom=58)
    hist_plot.quad(left="left", right="right", top="top", bottom=0, source=hist_source, fill_color="color", fill_alpha=0.85, line_color="#ffffff")
    hist_plot.background_fill_color = "#ffffff"
    hist_plot.outline_line_color = "#d9e2e8"
    hist_plot.xaxis.axis_label = "CHEI 2050"
    hist_plot.yaxis.axis_label = "Features"
    hist_plot.xaxis.formatter = BasicTickFormatter(precision=2)
    hist_plot.title.text_color = NAVY
    hist_plot.title.text_font_size = "10.5pt"
    hist_plot.xaxis.axis_label_text_font_size = "9pt"
    hist_plot.yaxis.axis_label_text_font_size = "9pt"
    hist_plot.xaxis.major_label_text_font_size = "8pt"
    hist_plot.yaxis.major_label_text_font_size = "8pt"
    hist_summary = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=50, css_classes=["hist-summary"])

    # Static initial state; the shared JavaScript callback updates these after
    # the first user interaction.
    initial_breaks = np.quantile(initial_values[np.isfinite(initial_values)], [0.2, 0.4, 0.6, 0.8])
    legend_rows = []
    lows = [-np.inf, *initial_breaks]
    highs = [*initial_breaks, np.inf]
    for i, color in enumerate(SEQ_BLUE):
        if i == 0:
            label = f"≤ {highs[i]:.3f}"
        elif i == len(SEQ_BLUE) - 1:
            label = f"> {lows[i]:.3f}"
        else:
            label = f"{lows[i]:.3f} – {highs[i]:.3f}"
        legend_rows.append(f"<div class='legend-row'><span style='background:{color}'></span><b>{label}</b></div>")
    legend_div.text = "<div class='panel-eyebrow'>MAP LEGEND</div><h4>Climate Housing Exposure Index, 2050</h4>" + "".join(legend_rows) + "<div class='legend-unit'>index</div>"
    layer_info.text = "<div class='panel-eyebrow'>ABOUT THIS LAYER</div><h4>Climate Housing Exposure Index, 2050</h4><p>Projected tract-level CHEI for 2050, combining precipitation hazard, projected housing exposure, and social vulnerability.</p><ul class='layer-bullets'><li>Geography: census tracts; projection year: 2050.</li><li>Higher values indicate greater combined climate–housing exposure.</li><li>Use for integrated adaptation and housing-resilience screening.</li></ul>"
    hist_summary.text = f"<p><strong>Median:</strong> {np.nanmedian(initial_values):.3f} &nbsp; <strong>Range:</strong> {np.nanmin(initial_values):.3f} to {np.nanmax(initial_values):.3f}</p>"
    point_status.text = '<span class="status-dot"></span>Click a census tract to update the profile panel, or use the ZIP-code locator to zoom to a familiar area.'
    map_guide.text = "<div class='map-guide'><div class='guide-heading'><span>READING THE CURRENT LAYER</span><h3>Climate Housing Exposure Index, 2050</h3></div><div class='guide-grid'><div><b>What it shows</b><p>Projected combined exposure at the census-tract level.</p></div><div><b>How to read it</b><p>Darker blues indicate higher CHEI values relative to other Harris County tracts.</p></div><div><b>Planning use</b><p>Screen locations for coordinated climate adaptation and housing-resilience review.</p></div></div></div>"
    map_actions.text = "<div class='action-panel'><div class='action-heading'><span>FROM MAP TO USE</span><h3>A three-step exploratory workflow</h3></div><div class='action-grid'><div><i>1</i><b>Screen</b><p>Locate tracts with higher relative CHEI values.</p></div><div><i>2</i><b>Diagnose</b><p>Click a tract and compare its climate and growth profile.</p></div><div><i>3</i><b>Validate</b><p>Confirm findings with authoritative local data before action.</p></div></div></div>"

    initial_idx = int(np.nanargmax(np.asarray(tract_data["CHEI_2050"], dtype=float)))
    tract_source.selected.indices = [initial_idx]
    t0 = tracts.iloc[initial_idx]
    selected_div = Div(width=INSIGHT_CONTENT_WIDTH, min_height=278, css_classes=["chei-panel", "selected-panel"])

    climate_profile_source = ColumnDataSource({
        "gmt": [1.5, 2.0, 2.5, 3.0],
        "precip": [float(t0["pr_15"]), float(t0["pr_20"]), float(t0["pr_25"]), float(t0["pr_30"])],
    })
    climate_profile = figure(height=230, width=INSIGHT_CONTENT_WIDTH, title="Selected tract: precipitation by GMT", tools="", toolbar_location=None)
    climate_profile.line(x="gmt", y="precip", source=climate_profile_source, line_width=3, color=TEAL)
    climate_profile.scatter(x="gmt", y="precip", source=climate_profile_source, size=9, color=GOLD, line_color=NAVY)
    climate_profile.xaxis.axis_label = "GMT increase relative to 1850–1899 (°C)"
    climate_profile.yaxis.axis_label = "3-day precipitation (mm)"
    climate_profile.background_fill_color = "#ffffff"
    climate_profile.outline_line_color = "#d9e2e8"
    climate_profile.title.text_color = NAVY
    climate_profile.add_tools(HoverTool(tooltips=[("GMT", "@gmt{0.0}°C"), ("Precipitation", "@precip{0.0} mm")]))

    profile_source = ColumnDataSource({
        "category": ["Population", "Households", "Employment"],
        "v2020": [float(t0["hp_2020"]), float(t0["hh_2020"]), float(t0["j_2020"])],
        "v2050": [float(t0["hp_2050"]), float(t0["hh_2050"]), float(t0["j_2050"])],
    })
    profile_plot = figure(x_range=["Population", "Households", "Employment"], height=255, width=INSIGHT_CONTENT_WIDTH, title="Selected tract: 2020 and 2050", tools="", toolbar_location=None)
    profile_plot.vbar(x=dodge("category", -0.17, range=profile_plot.x_range), top="v2020", width=0.31, source=profile_source, color="#6BAED6", legend_label="2020")
    profile_plot.vbar(x=dodge("category", 0.17, range=profile_plot.x_range), top="v2050", width=0.31, source=profile_source, color=GOLD, legend_label="2050")
    profile_plot.yaxis.formatter = NumeralTickFormatter(format="0,0")
    profile_plot.yaxis.axis_label = "Count"
    profile_plot.xgrid.grid_line_color = None
    profile_plot.background_fill_color = "#ffffff"
    profile_plot.outline_line_color = "#d9e2e8"
    profile_plot.title.text_color = NAVY
    profile_plot.legend.orientation = "horizontal"
    profile_plot.legend.location = "top_left"
    profile_plot.add_tools(HoverTool(tooltips=[("Measure", "@category"), ("2020", "@v2020{0,0}"), ("2050", "@v2050{0,0}")]))

    def selected_html(row) -> str:
        return f"""
        <div class='panel-eyebrow'>SELECTED CENSUS TRACT</div>
        <h3>{html_lib.escape(str(row.get('NAME', '')))} <span>{html_lib.escape(str(row['GEOID']))}</span></h3>
        <div class='selected-grid'>
          <div><b>{row['CHEI_2050']:.3f}</b><span>CHEI 2050</span></div>
          <div><b>{row['SVI']:.3f}</b><span>SVI 2020</span></div>
          <div><b>{fmt_int(row['pop_chg'])}</b><span>Population change</span></div>
          <div><b>{fmt_int(row['hh_chg'])}</b><span>Household change</span></div>
        </div>
        <p><strong>Compound hotspot:</strong> {html_lib.escape(str(hotspot_combo[int(row.name)]))} ({int(hotspot_score[int(row.name)])}/3)<br>
        <strong>Parcel housing-unit change:</strong> {fmt_int(row['parcel_hu_change'])}</p>
        <div class='selected-thresholds'><span class='{"on" if hazard_high[int(row.name)] else "off"}'>Precipitation</span><span class='{"on" if growth_high[int(row.name)] else "off"}'>Household growth</span><span class='{"on" if svi_high[int(row.name)] else "off"}'>SVI</span></div>
        """
    selected_div.text = selected_html(t0)

    callback_code = r"""
const META = __META__;
const SEQ_BLUE = __SEQ_BLUE__;
const DIVERGING = __DIVERGING__;
const BIVARIATE = __BIVARIATE__;
const HOTSPOT_FILLS = __HOTSPOT_FILLS__;
const HOTSPOT_PATTERN_STYLES = __HOTSPOT_PATTERN_STYLES__;
const HOTSPOT_ORDER = __HOTSPOT_ORDER__;
const HOTSPOT_THRESHOLDS = {precip:203.603, households:746, svi:0.88386};
const LAND_COLORS = {'Residential':'#2ca25f','Commercial':'#fdae6b','Vacant Developable (includes Farming)':'#bdbdbd','Multiple':'#756bb1','Industrial':'#e6550d','Unknown':'#969696','Other':'#6baed6','Gov/Med/Edu':'#3182bd'};
const FACTOR_LABELS = {'pr_15':'GMT +1.5°C precipitation','pr_20':'GMT +2.0°C precipitation','pr_25':'GMT +2.5°C precipitation','pr_30':'GMT +3.0°C precipitation','SVI':'Social Vulnerability Index','CHEI_2050':'CHEI 2050','pop_chg':'Population growth','hh_chg':'Household growth','job_chg':'Employment growth','parcel_hu_change':'Parcel housing-unit change'};
const FACTOR_DECIMALS = {'pr_15':3,'pr_20':3,'pr_25':3,'pr_30':3,'SVI':5,'CHEI_2050':3,'pop_chg':0,'hh_chg':0,'job_chg':0,'parcel_hu_change':0};
let currentLegendContext = null;
let activeLegendKey = null;

function finiteValues(arr) {
  return Array.from(arr || []).filter(v => Number.isFinite(Number(v))).map(Number);
}
function quantile(arr, q) {
  const a = finiteValues(arr).sort((x, y) => x - y);
  if (!a.length) return NaN;
  const p = (a.length - 1) * q, l = Math.floor(p), h = Math.ceil(p);
  return l === h ? a[l] : a[l] + (a[h] - a[l]) * (p - l);
}
function median(arr) { return quantile(arr, .5); }
function fmt(v, d=0) {
  const n = Number(v);
  if (!Number.isFinite(n)) return 'No data';
  return n.toLocaleString(undefined, {minimumFractionDigits:d, maximumFractionDigits:d});
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function titleOf(meta) { return meta.label.split('•').pop().trim(); }
function sequential(arr, palette) {
  const b = [quantile(arr,.2), quantile(arr,.4), quantile(arr,.6), quantile(arr,.8)];
  const classes = [], colors = [];
  for (const value of Array.from(arr)) {
    const n = Number(value);
    if (!Number.isFinite(n)) { classes.push('nodata'); colors.push('#d9d9d9'); continue; }
    let i = 0;
    while (i < b.length && n > b[i]) i++;
    classes.push(String(i)); colors.push(palette[i]);
  }
  return {colors:colors, breaks:b, classes:classes};
}
function diverging(arr) {
  const av = finiteValues(arr).map(Math.abs), lim = Math.max(quantile(av,.95), 1e-9);
  const colors = [], classes = [];
  for (const value of Array.from(arr)) {
    const n = Number(value);
    if (!Number.isFinite(n)) { colors.push('#d9d9d9'); classes.push('nodata'); continue; }
    let cls = 2;
    if (n <= -lim/2) cls = 0;
    else if (n < 0) cls = 1;
    else if (n === 0) cls = 2;
    else if (n < lim/2) cls = 3;
    else cls = 4;
    colors.push(DIVERGING[cls]); classes.push(String(cls));
  }
  return {colors:colors, lim:lim, classes:classes};
}
function setAllInvisible() {
  parcel_renderer.visible = false;
  climate_renderer.visible = false;
  grid_renderer.visible = false;
  housing_renderer.visible = false;
  for (const renderer of hotspot_pattern_renderers) renderer.visible = false;
  kr15.visible = false; kr20.visible = false; kr25.visible = false; kr30.visible = false;
}
function legendButton(style, label, key, count='', extra='') {
  const countHTML = count === '' ? '' : `<em>${esc(count)}</em>`;
  return `<button type='button' class='legend-row legend-button ${extra}' data-legend-key='${esc(key)}' onclick='window.CHEI&&window.CHEI.selectLegend(this.dataset.legendKey)'><span style='${style}'></span><b>${esc(label)}</b>${countHTML}</button>`;
}
function legendSequential(label, unit, breaks, palette, decimals) {
  const lows = [-Infinity, ...breaks], highs = [...breaks, Infinity];
  let rows = '';
  for (let i=0; i<palette.length; i++) {
    let txt = '';
    if (i === 0) txt = '≤ ' + fmt(highs[i], decimals);
    else if (i === palette.length - 1) txt = '> ' + fmt(lows[i], decimals);
    else txt = fmt(lows[i], decimals) + ' – ' + fmt(highs[i], decimals);
    rows += legendButton(`background:${palette[i]}`, txt, String(i));
  }
  return `<div class='panel-eyebrow'>MAP LEGEND</div><h4>${esc(label)}</h4>${rows}<div class='legend-unit'>${esc(unit||'')} · click one class to locate matches</div>`;
}
function legendDiverging(label, unit) {
  const labels = ['Large decrease','Decrease','Near zero','Increase','Large increase'];
  return `<div class='panel-eyebrow'>MAP LEGEND</div><h4>${esc(label)}</h4>` +
    labels.map((x,i)=>legendButton(`background:${DIVERGING[i]}`,x,String(i))).join('') +
    `<div class='legend-unit'>${esc(unit||'')} · click one class to locate matches</div>`;
}
function legendCategorical(label, categories, colors, counts={}) {
  const rows = categories.map(k => legendButton(`background:${colors[k]||'#969696'}`, k, String(k), counts[k] == null ? '' : fmt(counts[k]))).join('');
  return `<div class='panel-eyebrow'>MAP LEGEND</div><h4>${esc(label)}</h4>${rows}<div class='legend-unit'>Click one category to locate matches</div>`;
}
function legendHotspot(arr) {
  const counts = {};
  HOTSPOT_ORDER.forEach(k => counts[k] = 0);
  Array.from(arr).forEach(v => counts[v] = (counts[v] || 0) + 1);
  const rows = HOTSPOT_ORDER.map(k =>
    legendButton(HOTSPOT_PATTERN_STYLES[k], k, k, fmt(counts[k]), 'hotspot-row pattern-legend-button')
  ).join('');
  return `<div class='panel-eyebrow'>MAP LEGEND</div><h4>Compound-hotspot typology</h4>` +
    `<div class='pattern-key'><b>Pattern key</b><span><i class='mini-pattern hazard-pattern'></i>Hazard</span><span><i class='mini-pattern growth-pattern'></i>Growth</span><span><i class='mini-pattern svi-pattern'></i>SVI</span></div>` +
    `<div class='threshold-card'><div class='threshold-kicker'>HIGH = COUNTY 80TH PERCENTILE OR ABOVE</div>` +
    `<div><b>Extreme precipitation</b><span>≥ 203.603 mm at GMT +2.5°C</span></div>` +
    `<div><b>Household growth</b><span>≥ 746 households, 2020–2050</span></div>` +
    `<div><b>Social vulnerability</b><span>SVI ≥ 0.88386</span></div></div>` +
    `<div class='legend-subtitle'>CONDITION COMBINATION · TRACT COUNT</div>${rows}`;
}
function layerInfoHTML(meta) {
  const bullets = (meta.bullets || []).map(x => `<li>${esc(x)}</li>`).join('');
  return `<div class='panel-eyebrow'>ABOUT THIS LAYER</div><h4>${esc(titleOf(meta))}</h4><p>${esc(meta.description)}</p><ul class='layer-bullets'>${bullets}</ul>`;
}
function mapGuideHTML(meta) {
  const b = meta.bullets || [];
  return `<div class='map-guide'><div class='guide-heading'><span>READING THE CURRENT LAYER</span><h3>${esc(titleOf(meta))}</h3></div>` +
    `<div class='guide-grid'><div><b>Scope</b><p>${esc(b[0]||meta.description)}</p></div>` +
    `<div><b>Interpretation</b><p>${esc(b[1]||'Compare values and patterns across Harris County.')}</p></div>` +
    `<div><b>Planning use</b><p>${esc(b[2]||'Use as an exploratory screening layer and verify with authoritative local data.')}</p></div></div></div>`;
}
function actionHTML(meta, id) {
  if (id === 'hotspot') {
    return `<div class='action-panel hotspot-action'><div class='action-heading'><span>FROM TYPOLOGY TO PRIORITY</span><h3>Use patterns to distinguish planning needs</h3></div>` +
      `<div class='action-grid'><div><i>1</i><b>Read each condition</b><p>Diagonal lines indicate hazard, vertical lines indicate growth, and dots indicate SVI.</p></div>` +
      `<div><i>2</i><b>Compare combinations</b><p>Click a pattern class to highlight the corresponding tracts.</p></div>` +
      `<div><i>3</i><b>Coordinate action</b><p>All-three-high tracts warrant integrated climate, housing, and equity review.</p></div></div>` +
      `<div class='action-note'>The thresholds are transparent screening conventions rather than natural discontinuities in risk.</div></div>`;
  }
  return `<div class='action-panel'><div class='action-heading'><span>FROM MAP TO USE</span><h3>A three-step exploratory workflow</h3></div>` +
    `<div class='action-grid'><div><i>1</i><b>Screen</b><p>Click a legend class to isolate the most relevant tracts, parcels, points, or cells.</p></div>` +
    `<div><i>2</i><b>Diagnose</b><p>Hover and select features; compare the mapped pattern with related layers.</p></div>` +
    `<div><i>3</i><b>Validate</b><p>Confirm modeled or projected findings with authoritative local data before action.</p></div></div></div>`;
}
function updateHistogram(arr, label, color, decimals) {
  const a = finiteValues(arr);
  hist_plot.visible = true;
  if (!a.length) {
    hist_plot.visible = false;
    hist_summary.text = '<p>No numeric distribution is available for this layer.</p>';
    return;
  }
  const min = Math.min(...a), max = Math.max(...a), bins = 12, width = (max-min || 1)/bins;
  const counts = new Array(bins).fill(0);
  for (const v of a) {
    let i = Math.floor((v-min)/width);
    if (i >= bins) i = bins-1;
    if (i < 0) i = 0;
    counts[i]++;
  }
  const left = [], right = [];
  for (let i=0; i<bins; i++) { left.push(min+i*width); right.push(min+(i+1)*width); }
  hist_source.data = {left:left, right:right, top:counts, color:new Array(bins).fill(color)};
  hist_source.change.emit();
  hist_plot.title.text = 'Distribution · ' + fmt(a.length,0) + ' features';
  hist_xaxis.axis_label = label;
  hist_summary.text = `<p><strong>Median:</strong> ${fmt(quantile(a,.5),decimals)}<br><strong>Range:</strong> ${fmt(min,decimals)} to ${fmt(max,decimals)}</p>`;
}
function clearOverlaySources() {
  legend_mask_renderer.visible = false;
  legend_highlight_polygon_renderer.visible = false;
  legend_highlight_point_renderer.visible = false;
  legend_mask_source.data = {xs:[],ys:[]};
  legend_highlight_polygon_source.data = {xs:[],ys:[]};
  legend_highlight_point_source.data = {x:[],y:[]};
}
function deepQueryAll(selector) {
  const found = [];
  function walk(root) {
    if (!root || !root.querySelectorAll) return;
    found.push(...root.querySelectorAll(selector));
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) walk(el.shadowRoot);
  }
  walk(document);
  return found;
}
function markActiveLegend() {
  setTimeout(() => {
    for (const el of deepQueryAll('.legend-button')) {
      el.classList.toggle('active', activeLegendKey !== null && String(el.dataset.legendKey) === String(activeLegendKey));
    }
  }, 0);
}
function clearLegendFilter(silent=false) {
  clearOverlaySources();
  if (currentLegendContext && currentLegendContext.geometry === 'point') {
    const d = currentLegendContext.source.data;
    const n = (d.x || []).length;
    d.display_alpha = new Array(n).fill(currentLegendContext.baseAlpha);
    currentLegendContext.source.change.emit();
  }
  activeLegendKey = null;
  markActiveLegend();
  if (!silent) legend_filter_status.text = `<span class='legend-help'>Legend filter cleared. Click one class to highlight matching features.</span>`;
}
function setLegendContext(ctx) {
  clearLegendFilter(true);
  currentLegendContext = ctx;
  window.__cheiLegendContext = ctx;
  legend_filter_status.text = `<span class='legend-help'>Click one legend class to highlight matching ${esc(ctx.featureLabel || 'features')}.</span>`;
}
function boundsFromNested(xs, ys) {
  let minx=Infinity,miny=Infinity,maxx=-Infinity,maxy=-Infinity;
  function walk(x,y) {
    if (!Array.isArray(x) || !Array.isArray(y)) return;
    if (x.length && typeof x[0] === 'number') {
      for (let i=0;i<x.length;i++) {
        const xx=Number(x[i]), yy=Number(y[i]);
        if (!Number.isFinite(xx)||!Number.isFinite(yy)) continue;
        minx=Math.min(minx,xx);maxx=Math.max(maxx,xx);miny=Math.min(miny,yy);maxy=Math.max(maxy,yy);
      }
    } else for (let i=0;i<x.length;i++) walk(x[i],y[i]);
  }
  walk(xs,ys);
  return {minx,miny,maxx,maxy};
}
function fitBounds(b) {
  if (!b || !Number.isFinite(b.minx+b.miny+b.maxx+b.maxy)) return;
  const dx=Math.max(b.maxx-b.minx,2500),dy=Math.max(b.maxy-b.miny,2500);
  map_plot.x_range.start=b.minx-dx*.10;map_plot.x_range.end=b.maxx+dx*.10;
  map_plot.y_range.start=b.miny-dy*.10;map_plot.y_range.end=b.maxy+dy*.10;
}
function selectLegend(key) {
  if (!currentLegendContext) return;
  key=String(key);
  if (activeLegendKey === key) { clearLegendFilter(); return; }
  clearLegendFilter(true);
  const ctx=currentLegendContext, classes=Array.from(ctx.classes||[]), matches=[];
  for(let i=0;i<classes.length;i++) if(String(classes[i])===key) matches.push(i);
  if (!matches.length) {
    legend_filter_status.text=`<span class='error-text'>No features match this legend class.</span>`;
    return;
  }
  activeLegendKey=key;
  const matchSet=new Set(matches),d=ctx.source.data;
  if(ctx.geometry==='polygon'){
    const non=[];
    for(let i=0;i<classes.length;i++) if(!matchSet.has(i)) non.push(i);
    legend_mask_source.data={xs:non.map(i=>d.xs[i]),ys:non.map(i=>d.ys[i])};
    legend_highlight_polygon_source.data={xs:matches.map(i=>d.xs[i]),ys:matches.map(i=>d.ys[i])};
    legend_mask_renderer.visible = true;
    legend_highlight_polygon_renderer.visible = true;
  }else{
    d.display_alpha=classes.map((_,i)=>matchSet.has(i)?ctx.baseAlpha:Math.min(.10,ctx.baseAlpha*.18));ctx.source.change.emit();
    legend_highlight_point_source.data={x:matches.map(i=>d.x[i]),y:matches.map(i=>d.y[i])};
    legend_highlight_point_renderer.visible = true;
  }
  ctx.matches=matches;
  const label=(ctx.labels&&ctx.labels[key])||key;
  legend_filter_status.text=`<div class='legend-selection'><b>${esc(label)}</b><span>${fmt(matches.length)} ${esc(ctx.featureLabel||'features')} highlighted</span><div><button onclick='window.CHEI.zoomLegendMatches()'>Zoom to matches</button><button onclick='window.CHEI.clearLegendFilter()'>Clear filter</button></div></div>`;
  markActiveLegend();
}
function zoomLegendMatches() {
  const ctx=currentLegendContext;if(!ctx||!ctx.matches||!ctx.matches.length)return;
  const d=ctx.source.data;
  if(ctx.geometry==='point'){
    const xs=ctx.matches.map(i=>Number(d.x[i])).filter(Number.isFinite),ys=ctx.matches.map(i=>Number(d.y[i])).filter(Number.isFinite);
    if(xs.length)fitBounds({minx:Math.min(...xs),maxx:Math.max(...xs),miny:Math.min(...ys),maxy:Math.max(...ys)});
  }else{
    let b={minx:Infinity,miny:Infinity,maxx:-Infinity,maxy:-Infinity};
    for(const i of ctx.matches){const x=boundsFromNested(d.xs[i],d.ys[i]);b.minx=Math.min(b.minx,x.minx);b.miny=Math.min(b.miny,x.miny);b.maxx=Math.max(b.maxx,x.maxx);b.maxy=Math.max(b.maxy,x.maxy);}
    fitBounds(b);
  }
}
function refreshHousingLegendContext() {
  if(layer_select.value!=='housing_points')return;
  const d=housing_point_source.data,alpha=Math.min(opacity_slider.value,.72);
  setLegendContext({layerId:'housing_points',source:housing_point_source,geometry:'point',classes:Array.from(d.kind||[]),labels:{'Single-family':'Single-family','Multi-family':'Multi-family'},baseAlpha:alpha,featureLabel:'housing points'});
}
function sampleHousing() {
  const mode = housing_select.value, s = housing_sample.data;
  const sx = (s.sf_x&&s.sf_x.length) ? Array.from(s.sf_x[0]) : [];
  const sy = (s.sf_y&&s.sf_y.length) ? Array.from(s.sf_y[0]) : [];
  const mx = (s.mf_x&&s.mf_x.length) ? Array.from(s.mf_x[0]) : [];
  const my = (s.mf_y&&s.mf_y.length) ? Array.from(s.mf_y[0]) : [];
  let x=[], y=[], color=[], kind=[];
  if (mode==='single' || mode==='combined') {x=x.concat(sx);y=y.concat(sy);color=color.concat(new Array(sx.length).fill('#168C95'));kind=kind.concat(new Array(sx.length).fill('Single-family'));}
  if (mode==='multi' || mode==='combined') {x=x.concat(mx);y=y.concat(my);color=color.concat(new Array(mx.length).fill('#F16913'));kind=kind.concat(new Array(mx.length).fill('Multi-family'));}
  const alpha=Math.min(opacity_slider.value,.72);
  housing_point_source.data={x:x,y:y,color:color,kind:kind,display_alpha:new Array(x.length).fill(alpha)};housing_point_source.change.emit();
  point_status.text=`<span class='status-dot'></span>Standalone preview: displaying ${fmt(x.length,0)} points. Start <code>server.py</code> for viewport queries against all source points.`;
  if(layer_select.value==='housing_points')refreshHousingLegendContext();
}
function requestHousingPoints() {
  if (layer_select.value !== 'housing_points') return;
  if (window.location.protocol==='file:' || window.location.protocol==='about:' || window.location.protocol==='sandbox:' || !window.fetch) {sampleHousing();return;}
  const xmin=map_plot.x_range.start,xmax=map_plot.x_range.end,ymin=map_plot.y_range.start,ymax=map_plot.y_range.end;
  const url=`/api/housing-points?housing_type=${encodeURIComponent(housing_select.value)}&xmin=${xmin}&xmax=${xmax}&ymin=${ymin}&ymax=${ymax}&max_points=50000`;
  point_status.text='<span class="status-dot loading"></span>Loading housing-stock points for the current viewport…';
  fetch(url).then(r=>{if(!r.ok)throw new Error(r.statusText);return r.json();}).then(d=>{
    const alpha=Math.min(opacity_slider.value,.72);
    housing_point_source.data={x:d.x,y:d.y,color:d.color,kind:d.kind,display_alpha:new Array(d.x.length).fill(alpha)};housing_point_source.change.emit();
    point_status.text=`<span class='status-dot'></span>Displaying ${fmt(d.n_returned,0)} of ${fmt(d.n_total,0)} source points in the current viewport.`;
    refreshHousingLegendContext();
  }).catch(()=>sampleHousing());
}
function clearHotspotPatternData(d) {}
function applyOverlap() {
  const d=tract_source.data,a=Array.from(d[overlap_a.value]),b=Array.from(d[overlap_b.value]);
  const q=threshold_slider.value/100,ta=quantile(a,q),tb=quantile(b,q);
  const colors=[],labels=[],classes=[],counts=[0,0,0,0];
  let bothPop=0,bothHH=0,bothJobs=0;
  const la=FACTOR_LABELS[overlap_a.value]||overlap_a.value,lb=FACTOR_LABELS[overlap_b.value]||overlap_b.value;
  const da=FACTOR_DECIMALS[overlap_a.value]??2,db=FACTOR_DECIMALS[overlap_b.value]??2;
  for(let i=0;i<a.length;i++){
    const ah=Number(a[i])>=ta,bh=Number(b[i])>=tb,cls=(ah?1:0)+(bh?2:0);
    counts[cls]++;colors.push(BIVARIATE[cls]);classes.push(String(cls));
    const label=cls===0?'Neither high':cls===1?`${la} only`:cls===2?`${lb} only`:'Both high';labels.push(label);
    if(cls===3){bothPop+=Number(d.hp_2050[i])||0;bothHH+=Number(d.hh_2050[i])||0;bothJobs+=Number(d.j_2050[i])||0;}
  }
  d.fill_color=colors;d.display_label=new Array(labels.length).fill(`${la} × ${lb}`);d.display_value=labels;tract_source.change.emit();
  const legendLabels={'0':'Neither high','1':`${la} only`,'2':`${lb} only`,'3':'Both high'};
  legend_div.text=`<div class='panel-eyebrow'>MAP LEGEND</div><h4>High–high overlap</h4><div class='threshold-card compact'><div class='threshold-kicker'>COUNTYWIDE ${fmt(threshold_slider.value)}TH PERCENTILE</div><div><b>${esc(la)}</b><span>High at ≥ ${fmt(ta,da)}</span></div><div><b>${esc(lb)}</b><span>High at ≥ ${fmt(tb,db)}</span></div></div>`+
    [0,1,2,3].map(i=>legendButton(`background:${BIVARIATE[i]}`,legendLabels[String(i)],String(i),fmt(counts[i]))).join('');
  setLegendContext({layerId:'overlap',source:tract_source,geometry:'polygon',classes:classes,labels:legendLabels,baseAlpha:opacity_slider.value,featureLabel:'census tracts'});
  overlap_summary.text=`<div class='panel-eyebrow'>BOTH HIGH</div><h4>${fmt(counts[3])} census tracts</h4><p><b>${fmt(bothPop)}</b> projected residents<br><b>${fmt(bothHH)}</b> projected households<br><b>${fmt(bothJobs)}</b> projected jobs</p><div class='legend-unit'>Cutoffs: ${esc(la)} ≥ ${fmt(ta,da)} · ${esc(lb)} ≥ ${fmt(tb,db)}</div>`;
  hist_plot.visible=false;hist_summary.text='<p>Overlap mode compares two factors; numeric cutoffs are shown in the legend.</p>';
  layer_info.text=`<div class='panel-eyebrow'>ABOUT THIS VIEW</div><h4>Transparent overlap screening</h4><p>Each factor is compared with its own countywide percentile cutoff.</p><ul class='layer-bullets'><li>Click a legend class to highlight its tracts.</li><li>Actual cutoffs update with the percentile and factor selections.</li><li>This is an exploratory screen, not a causal or regulatory classification.</li></ul>`;
  map_guide.text=`<div class='map-guide'><div class='guide-heading'><span>READING THE OVERLAP VIEW</span><h3>${esc(la)} × ${esc(lb)}</h3></div><div class='guide-grid'><div><b>Factor A cutoff</b><p>${esc(la)} is high at ${fmt(ta,da)} or above.</p></div><div><b>Factor B cutoff</b><p>${esc(lb)} is high at ${fmt(tb,db)} or above.</p></div><div><b>Interpretation</b><p>Darkest tracts meet both cutoffs and may warrant coordinated review.</p></div></div></div>`;
  map_actions.text=`<div class='action-panel'><div class='action-heading'><span>USING THE OVERLAP SCREEN</span><h3>Test sensitivity before prioritizing</h3></div><div class='action-grid'><div><i>1</i><b>Compare</b><p>Change factors to examine different forms of co-exposure.</p></div><div><i>2</i><b>Locate</b><p>Click a legend class and zoom to matching tracts.</p></div><div><i>3</i><b>Validate</b><p>Review both-high tracts with local evidence and stakeholder knowledge.</p></div></div></div>`;
  point_status.text='<span class="status-dot"></span>Overlap screening is active. Click a legend class or change factors to test alternatives.';
}
function updateLayer() {
  clearLegendFilter(true);setAllInvisible();
  const active=overlap_toggle.active;
  layer_select.disabled=active;
  overlap_a.visible=active;overlap_b.visible=active;threshold_slider.visible=active;overlap_summary.visible=active;
  gmt_select.visible=!active&&['pr_tract','pr_points','pr_kriging'].includes(layer_select.value);
  housing_select.visible=!active&&['housing_density','housing_points'].includes(layer_select.value);
  const opacity=opacity_slider.value;
  tract_renderer.glyph.fill_alpha=opacity;tract_renderer.nonselection_glyph.fill_alpha=opacity;
  tract_renderer.glyph.line_color='#ffffff';tract_renderer.glyph.line_alpha=.75;tract_renderer.glyph.line_width=.55;
  parcel_renderer.glyph.fill_alpha=opacity;grid_renderer.glyph.fill_alpha=opacity;
  kr15.glyph.global_alpha=opacity;kr20.glyph.global_alpha=opacity;kr25.glyph.global_alpha=opacity;kr30.glyph.global_alpha=opacity;
  tract_renderer.visible=true;
  if(active){applyOverlap();return;}
  const id=layer_select.value,meta=META[id],d=tract_source.data;
  let field=meta.field,arr=null,result=null;
  if(id==='pr_tract'||id==='pr_kriging')field='pr_'+gmt_select.value;
  if(meta.source==='tract'){
    arr=Array.from(d[field]);
    if(meta.kind==='seq')result=sequential(arr,meta.palette);
    else if(meta.kind==='div')result=diverging(arr);
    else result={colors:arr.map(v=>HOTSPOT_FILLS[v]||'#F1F3F4'),classes:arr.map(String)};
    d.fill_color=result.colors;d.display_label=new Array(arr.length).fill(titleOf(meta));d.display_value=arr.map(v=>meta.kind==='cat_hotspot'?String(v):fmt(v,meta.decimals));tract_source.change.emit();
    if(meta.kind==='cat_hotspot'){
      const hatchOpacity=Math.max(.56,Math.min(.84,opacity*.90));
      for(const renderer of hotspot_pattern_renderers){renderer.glyph.hatch_alpha=hatchOpacity;renderer.visible=true;}
      tract_renderer.glyph.line_color='#87959B';tract_renderer.glyph.line_alpha=.62;tract_renderer.glyph.line_width=.50;
      tract_renderer.selection_glyph.fill_alpha=.10;tract_renderer.selection_glyph.line_color='#F2B134';tract_renderer.selection_glyph.line_width=3.0;
      legend_div.text=legendHotspot(arr);hist_plot.visible=false;
      hist_summary.text='<p><strong>Pattern-based typology:</strong> diagonal lines denote precipitation hazard, vertical lines denote household growth, and dots denote social vulnerability. Click any combination to locate its tracts.</p>';
      const labels={};HOTSPOT_ORDER.forEach(x=>labels[x]=x);
      setLegendContext({layerId:id,source:tract_source,geometry:'polygon',classes:result.classes,labels:labels,baseAlpha:opacity,featureLabel:'census tracts'});
    }else{
      tract_renderer.selection_glyph.fill_alpha=.90;tract_renderer.selection_glyph.line_color='#111111';tract_renderer.selection_glyph.line_width=2.2;
      if(meta.kind==='seq'){
        legend_div.text=legendSequential(titleOf(meta),meta.unit,result.breaks,meta.palette,meta.decimals);updateHistogram(arr,meta.short,meta.palette[3],meta.decimals);
        const labels={};const lows=[-Infinity,...result.breaks],highs=[...result.breaks,Infinity];
        for(let i=0;i<meta.palette.length;i++)labels[String(i)]=i===0?`≤ ${fmt(highs[i],meta.decimals)}`:i===meta.palette.length-1?`> ${fmt(lows[i],meta.decimals)}`:`${fmt(lows[i],meta.decimals)} – ${fmt(highs[i],meta.decimals)}`;
        setLegendContext({layerId:id,source:tract_source,geometry:'polygon',classes:result.classes,labels:labels,baseAlpha:opacity,featureLabel:'census tracts'});
      }else{
        legend_div.text=legendDiverging(titleOf(meta),meta.unit);updateHistogram(arr,meta.short,DIVERGING[4],meta.decimals);
        setLegendContext({layerId:id,source:tract_source,geometry:'polygon',classes:result.classes,labels:{'0':'Large decrease','1':'Decrease','2':'Near zero','3':'Increase','4':'Large increase'},baseAlpha:opacity,featureLabel:'census tracts'});
      }
    }
  }else if(meta.source==='parcel'){
    parcel_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.30;
    const p=parcel_source.data;arr=Array.from(p[field]);
    if(meta.kind==='seq'){
      result=sequential(arr,meta.palette);p.fill_color=result.colors;p.display_value=arr.map(v=>fmt(v,meta.decimals));
      legend_div.text=legendSequential(titleOf(meta),meta.unit,result.breaks,meta.palette,meta.decimals);updateHistogram(arr,meta.short,meta.palette[3],meta.decimals);
      const labels={},lows=[-Infinity,...result.breaks],highs=[...result.breaks,Infinity];for(let i=0;i<meta.palette.length;i++)labels[String(i)]=i===0?`≤ ${fmt(highs[i],meta.decimals)}`:i===meta.palette.length-1?`> ${fmt(lows[i],meta.decimals)}`:`${fmt(lows[i],meta.decimals)} – ${fmt(highs[i],meta.decimals)}`;
      setLegendContext({layerId:id,source:parcel_source,geometry:'polygon',classes:result.classes,labels:labels,baseAlpha:opacity,featureLabel:'parcels'});
    }else{
      p.fill_color=arr.map(v=>LAND_COLORS[v]||'#969696');p.display_value=arr.map(String);const cats={};arr.forEach(v=>cats[v]=(cats[v]||0)+1);
      const categories=Object.keys(cats).sort((a,b)=>cats[b]-cats[a]);legend_div.text=legendCategorical(titleOf(meta),categories,LAND_COLORS,cats);
      hist_plot.visible=false;hist_summary.text='<p>Categorical parcel layer; feature counts are shown in the legend. Click a category to locate matching parcels.</p>';
      const labels={};categories.forEach(x=>labels[x]=x);setLegendContext({layerId:id,source:parcel_source,geometry:'polygon',classes:arr.map(String),labels:labels,baseAlpha:opacity,featureLabel:'parcels'});
    }
    parcel_source.change.emit();
  }else if(meta.source==='grid'){
    grid_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.28;
    const gd=grid_source.data;field=housing_select.value==='single'?'sf_count':housing_select.value==='multi'?'mf_count':'total_count';arr=Array.from(gd[field]);result=sequential(arr,meta.palette);gd.fill_color=result.colors;gd.display_value=arr.map(v=>fmt(v,0));grid_source.change.emit();
    const label=(housing_select.value==='single'?'Single-family':housing_select.value==='multi'?'Multi-family':'Combined')+' housing-stock density';legend_div.text=legendSequential(label,'records per 1 km cell',result.breaks,meta.palette,0);updateHistogram(arr,'Housing records per cell',meta.palette[3],0);
    const labels={},lows=[-Infinity,...result.breaks],highs=[...result.breaks,Infinity];for(let i=0;i<meta.palette.length;i++)labels[String(i)]=i===0?`≤ ${fmt(highs[i],0)}`:i===meta.palette.length-1?`> ${fmt(lows[i],0)}`:`${fmt(lows[i],0)} – ${fmt(highs[i],0)}`;
    setLegendContext({layerId:id,source:grid_source,geometry:'polygon',classes:result.classes,labels:labels,baseAlpha:opacity,featureLabel:'grid cells'});
  }else if(meta.source==='climate_points'){
    climate_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.30;
    const cm=climate_source.data,g=Number(gmt_select.value)/10,x=[],y=[],v=[];for(let i=0;i<cm.gmt.length;i++)if(Number(cm.gmt[i])===g){x.push(cm.x[i]);y.push(cm.y[i]);v.push(cm.precip[i]);}
    result=sequential(v,meta.palette);climate_display_source.data={x:x,y:y,gmt:new Array(x.length).fill(g),precip:v,color:result.colors,display_alpha:new Array(x.length).fill(opacity)};climate_display_source.change.emit();
    legend_div.text=legendSequential(`GMT ${g.toFixed(1)}°C climate points`,meta.unit,result.breaks,meta.palette,meta.decimals);updateHistogram(v,'3-day precipitation (mm)',meta.palette[3],1);
    const labels={},lows=[-Infinity,...result.breaks],highs=[...result.breaks,Infinity];for(let i=0;i<meta.palette.length;i++)labels[String(i)]=i===0?`≤ ${fmt(highs[i],meta.decimals)}`:i===meta.palette.length-1?`> ${fmt(lows[i],meta.decimals)}`:`${fmt(lows[i],meta.decimals)} – ${fmt(highs[i],meta.decimals)}`;
    setLegendContext({layerId:id,source:climate_display_source,geometry:'point',classes:result.classes,labels:labels,baseAlpha:opacity,featureLabel:'climate points'});
  }else if(meta.source==='kriging'){
    tract_renderer.glyph.fill_alpha=0;tract_renderer.nonselection_glyph.fill_alpha=0;tract_renderer.glyph.line_alpha=.50;tract_renderer.glyph.line_width=.40;
    const code=gmt_select.value;({'15':kr15,'20':kr20,'25':kr25,'30':kr30})[code].visible=true;const arr2=Array.from(d['pr_'+code]),r=sequential(arr2,meta.palette);
    legend_div.text=legendSequential(`GMT ${(Number(code)/10).toFixed(1)}°C kriging surface`,'mm',r.breaks,meta.palette,1);updateHistogram(arr2,'Tract precipitation (mm)',meta.palette[3],1);
    const labels={},lows=[-Infinity,...r.breaks],highs=[...r.breaks,Infinity];for(let i=0;i<meta.palette.length;i++)labels[String(i)]=i===0?`≤ ${fmt(highs[i],1)}`:i===meta.palette.length-1?`> ${fmt(lows[i],1)}`:`${fmt(lows[i],1)} – ${fmt(highs[i],1)}`;
    setLegendContext({layerId:id,source:tract_source,geometry:'polygon',classes:r.classes,labels:labels,baseAlpha:opacity,featureLabel:'census tracts',krigingLocator:true});
    legend_filter_status.text=`<span class='legend-help'>Click a raster class to locate census tracts in the corresponding precipitation range.</span>`;
  }else if(meta.source==='housing_points'){
    housing_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.24;
    legend_div.text=legendCategorical('Housing-stock locations',['Single-family','Multi-family'],{'Single-family':'#168C95','Multi-family':'#F16913'});
    hist_plot.visible=false;hist_summary.text='<p>Point display is optimized by viewport. The density layer uses every uploaded record.</p>';requestHousingPoints();
  }
  layer_info.text=layerInfoHTML(meta);map_guide.text=mapGuideHTML(meta);map_actions.text=actionHTML(meta,id);
  if(meta.source!=='housing_points')point_status.text='<span class="status-dot"></span>Click a tract for its profile, use ZIP/precinct locators, or click a legend class to locate matching features.';
}
function selectedPlace() {
  const mode=report_geography.value,td=tract_source.data;
  if(mode==='tract'){
    const inds=tract_source.selected.indices;if(!inds.length)return null;const i=inds[0];
    return {mode:'tract',label:`Census tract ${td.GEOID[i]}`,sub:td.NAME[i]||'',indices:[i],xs:td.xs[i],ys:td.ys[i],index:i};
  }
  if(mode==='zip'){
    const d=selected_zip_source.data;if(!d.ZIP||!d.ZIP.length)return null;
    return {mode:'zip',label:`ZIP ${d.ZIP[0]}`,sub:d.POSTAL[0]||'',indices:Array.from(d.tract_indices[0]||[]).map(Number),xs:d.xs[0],ys:d.ys[0]};
  }
  const d=selected_precinct_source.data;if(!d.PCT_NO||!d.PCT_NO.length)return null;
  return {mode:'precinct',label:`Commissioner Precinct ${d.PCT_NO[0]}`,sub:`${fmt(d.AREA_IN_MI[0])} square miles`,indices:Array.from(d.tract_indices[0]||[]).map(Number),xs:d.xs[0],ys:d.ys[0]};
}
function focusSelectedPlace() {
  const place=selectedPlace();
  if(!place){quick_decision_status.text=`<div class='quick-status error'><b>No ${esc(report_geography.value)} selection is available.</b><p>Use the corresponding locator first.</p></div>`;return;}
  fitBounds(boundsFromNested(place.xs,place.ys));
  if(place.mode==='tract')tract_source.selected.indices=[place.index];
  const d=tract_source.data,idx=place.indices;
  const chei=median(idx.map(i=>d.CHEI_2050[i])),svi=median(idx.map(i=>d.SVI[i]));
  const all3=idx.filter(i=>String(d.hotspot_combo[i])==='All three high').length;
  quick_decision_status.text=`<div class='quick-status success'><b>${esc(place.label)}</b><p>${place.mode==='tract'?'Exact tract values':`Screening summary across ${fmt(idx.length)} intersecting tracts`}: median CHEI 2050 <strong>${fmt(chei,3)}</strong>, median SVI <strong>${fmt(svi,3)}</strong>, and <strong>${fmt(all3)}</strong> all-three-high tract${all3===1?'':'s'}.</p></div>`;
}
function scheduleQuickLayer(layerId, legendKey) {
  layer_select.value = layerId;
  if (window.__cheiQuickTimer) clearTimeout(window.__cheiQuickTimer);
  window.__cheiQuickTimer = setTimeout(() => {
    updateLayer();
    selectLegend(legendKey);
  }, 80);
}
function quickDecision(id) {
  overlap_toggle.active=false;
  if(id==='exposure'){
    scheduleQuickLayer('chei_2050','4');
    quick_decision_status.text=`<div class='quick-status success'><b>Highest overall exposure</b><p>The highest CHEI 2050 class is highlighted. Use “Zoom to matches” in the legend panel to focus the map.</p></div>`;
  }else if(id==='overlap'){
    scheduleQuickLayer('hotspot','All three high');
    quick_decision_status.text=`<div class='quick-status success'><b>Three-factor overlap</b><p>Tracts meeting the high precipitation, household-growth, and SVI thresholds are highlighted.</p></div>`;
  }else if(id==='adaptation'){
    scheduleQuickLayer('adapt_gap','4');
    quick_decision_status.text=`<div class='quick-status success'><b>Emerging adaptation needs</b><p>The largest modeled CHEI increases from 2020 to 2050 are highlighted.</p></div>`;
  }else focusSelectedPlace();
}
function collectRings(xs,ys){const rings=[];function walk(x,y){if(!Array.isArray(x)||!Array.isArray(y))return;if(x.length&&typeof x[0]==='number')rings.push([x,y]);else for(let i=0;i<x.length;i++)walk(x[i],y[i]);}walk(xs,ys);return rings;}
function shapeSVG(xs,ys,label){const rings=collectRings(xs,ys);let minx=Infinity,miny=Infinity,maxx=-Infinity,maxy=-Infinity;for(const [x,y] of rings)for(let i=0;i<x.length;i++){const xx=Number(x[i]),yy=Number(y[i]);if(Number.isFinite(xx+yy)){minx=Math.min(minx,xx);maxx=Math.max(maxx,xx);miny=Math.min(miny,yy);maxy=Math.max(maxy,yy);}}const w=360,h=160,pad=10,dx=Math.max(maxx-minx,1),dy=Math.max(maxy-miny,1),scale=Math.min((w-2*pad)/dx,(h-2*pad)/dy),ox=(w-dx*scale)/2,oy=(h-dy*scale)/2;const paths=rings.map(([x,y])=>{let d='';for(let i=0;i<x.length;i++){const px=ox+(Number(x[i])-minx)*scale,py=h-(oy+(Number(y[i])-miny)*scale);d+=(i?'L':'M')+px.toFixed(1)+' '+py.toFixed(1)+' ';}return d+'Z';}).join(' ');return `<svg viewBox='0 0 ${w} ${h}' role='img' aria-label='${esc(label)} boundary'><rect width='${w}' height='${h}' fill='#f4f7f9'/><path d='${paths}' fill='#dceff0' stroke='#168c95' stroke-width='2' fill-rule='evenodd'/><text x='12' y='20' font-size='11' font-family='Arial' fill='#17324d'>Simplified boundary context</text></svg>`;}
function stats(indices,field){const vals=indices.map(i=>Number(tract_source.data[field][i])).filter(Number.isFinite);return {vals:vals,n:vals.length,median:median(vals),min:vals.length?Math.min(...vals):NaN,max:vals.length?Math.max(...vals):NaN};}
function statText(st,dec,exact){if(!st.n)return 'No data';return exact?fmt(st.median,dec):`${fmt(st.median,dec)} <small>[${fmt(st.min,dec)}–${fmt(st.max,dec)}]</small>`;}
function generateReport() {
  const place=selectedPlace();
  if(!place){report_status.text=`<span class='error-text'>Use the selected ${esc(report_geography.value)} locator before generating this report.</span>`;return;}
  const idx=place.indices,exact=place.mode==='tract',d=tract_source.data;
  if(!idx.length){report_status.text='<span class="error-text">No intersecting census tracts were identified.</span>';return;}
  const fields=[['CHEI 2020','CHEI_2020',3],['CHEI 2050','CHEI_2050',3],['CHEI adaptation gap','adapt_gap',3],['GMT +2.5°C precipitation','pr_25',1],['Social Vulnerability Index','SVI',3],['Population change, 2020–2050','pop_chg',0],['Household change, 2020–2050','hh_chg',0],['Employment change, 2020–2050','job_chg',0],['Single-family records, 2020','n_single_f',0],['Multi-family records, 2020','n_multi_fa',0]];
  const rows=fields.map(([label,field,dec])=>`<tr><th>${esc(label)}</th><td>${statText(stats(idx,field),dec,exact)}</td></tr>`).join('');
  const hazard=idx.filter(i=>Number(d.hazard_high[i])===1).length,growth=idx.filter(i=>Number(d.growth_high[i])===1).length,svi=idx.filter(i=>Number(d.svi_high[i])===1).length,all3=idx.filter(i=>String(d.hotspot_combo[i])==='All three high').length;
  const pct=n=>100*n/idx.length;
  const chei=stats(idx,'CHEI_2050'),gap=stats(idx,'adapt_gap'),hh=stats(idx,'hh_chg');
  const dominant={};idx.forEach(i=>{const k=String(d.hotspot_combo[i]);dominant[k]=(dominant[k]||0)+1;});const dominantEntry=Object.entries(dominant).sort((a,b)=>b[1]-a[1])[0]||['No data',0];
  const findings=exact?[
    `CHEI 2050 is ${fmt(chei.median,3)} and the adaptation gap is ${fmt(gap.median,3)}.`,
    `The tract's compound classification is ${d.hotspot_combo[idx[0]]}.`,
    `Projected household change is ${fmt(hh.median,0)} households from 2020 to 2050.`
  ]:[
    `Median CHEI 2050 is ${fmt(chei.median,3)}, with a range of ${fmt(chei.min,3)}–${fmt(chei.max,3)} across intersecting tracts.`,
    `${fmt(pct(all3),1)}% of intersecting tracts are all-three-high; the most common typology is ${dominantEntry[0]}.`,
    `Median projected household change is ${fmt(hh.median,0)}, with ${fmt(pct(growth),1)}% of tracts at or above the countywide high-growth threshold.`
  ];
  const layerTitle=META[layer_select.value]?titleOf(META[layer_select.value]):'Current dashboard view';
  const caveat=exact?'Values are exact for the selected census tract.':`This is a screening summary of ${fmt(idx.length)} census tracts that intersect the selected boundary. It is not an official ZIP- or precinct-level aggregation and should not be interpreted as one.`;
  const html=`<!doctype html><html><head><meta charset='utf-8'><title>${esc(place.label)} — Climate Housing Decision Brief</title><style>@page{size:letter portrait;margin:.35in}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#233746;margin:0;font-size:10px}.toolbar{display:flex;justify-content:flex-end;margin-bottom:7px}.toolbar button{background:#168c95;color:#fff;border:0;padding:8px 13px;font-weight:bold}.head{background:#17324d;color:white;padding:14px 17px;border-top:5px solid #4cb8be}.head small{letter-spacing:1.2px;color:#93dadd}.head h1{font-size:20px;margin:4px 0}.head p{margin:0;color:#d8e8ec}.grid{display:grid;grid-template-columns:42% 58%;gap:12px;margin-top:12px}.card{border:1px solid #cfdae0;padding:10px}.card h2{font-size:13px;color:#17324d;margin:0 0 7px;border-bottom:2px solid #4cb8be;padding-bottom:5px}.map svg{width:100%;height:150px}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:10px 0}.fact{background:#eef4f6;padding:7px}.fact b{display:block;font-size:14px;color:#17324d}.fact span{font-size:8px;text-transform:uppercase;color:#617382}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #e1e7ea;padding:4px 5px;text-align:left}th{width:58%;font-weight:600}td{font-weight:bold;color:#17324d}td small{font-weight:normal;color:#60727d}.findings ol{padding-left:17px;margin:5px 0}.findings li{margin:5px 0;line-height:1.35}.note{background:#fff4d9;border-left:4px solid #f2b134;padding:7px 9px;margin-top:8px;line-height:1.35}.foot{margin-top:10px;border-top:1px solid #cbd6dc;padding-top:6px;color:#60727d;display:flex;justify-content:space-between;gap:12px}.foot span:last-child{text-align:right}@media print{.toolbar{display:none}body{font-size:9.2px}.grid{gap:9px}.card{padding:8px}}</style></head><body><div class='toolbar'><button onclick='window.print()'>Print / Save as PDF</button></div><header class='head'><small>CLIMATE–HOUSING EXPOSURE INDEX DASHBOARD</small><h1>${esc(place.label)}</h1><p>${esc(place.sub)} · One-page decision brief · Harris County, Texas</p></header><div class='facts'><div class='fact'><b>${fmt(idx.length)}</b><span>${exact?'selected tract':'intersecting tracts'}</span></div><div class='fact'><b>${fmt(pct(hazard),1)}%</b><span>high precipitation</span></div><div class='fact'><b>${fmt(pct(growth),1)}%</b><span>high household growth</span></div><div class='fact'><b>${fmt(pct(svi),1)}%</b><span>high SVI</span></div></div><div class='grid'><section><div class='card map'><h2>Location context</h2>${shapeSVG(place.xs,place.ys,place.label)}</div><div class='card findings' style='margin-top:10px'><h2>Decision-oriented findings</h2><ol>${findings.map(x=>`<li>${esc(x)}</li>`).join('')}</ol><div class='note'><b>Interpretation:</b> ${esc(caveat)}</div></div></section><section class='card'><h2>Climate, housing, growth, and vulnerability profile</h2><table>${rows}</table><div class='note'><b>Compound-screening shares:</b> high precipitation ${fmt(pct(hazard),1)}%; high household growth ${fmt(pct(growth),1)}%; high SVI ${fmt(pct(svi),1)}%; all three high ${fmt(pct(all3),1)}%.</div><div class='note'><b>Dashboard context:</b> Active layer at report generation: ${esc(layerTitle)}. Values are modeled, estimated, or projected and require validation with authoritative local data.</div></section></div><footer class='foot'><span>Prepared from the Climate-Housing Exposure Index Dashboard<br>Research, education, and planning exploration only.</span><span>Kaifa Lu · CECREH<br>Kaifa.Lu@ttu.edu</span></footer></body></html>`;
  const w=window.open('','_blank');if(!w){report_status.text='<span class="error-text">The browser blocked the report window. Allow pop-ups for this site and try again.</span>';return;}w.document.open();w.document.write(html);w.document.close();
  report_status.text=`<span class='success-text'>Decision brief opened for <b>${esc(place.label)}</b>. Use Print / Save as PDF in the report window.</span>`;
}
window.CHEI={selectLegend:selectLegend,clearLegendFilter:clearLegendFilter,zoomLegendMatches:zoomLegendMatches,quickDecision:quickDecision,focusSelectedPlace:focusSelectedPlace,generateReport:generateReport,updateLayer:updateLayer,refreshHousingLegendContext:refreshHousingLegendContext};
updateLayer();

"""
    callback_code = (callback_code
        .replace("__META__", json.dumps(layer_meta))
        .replace("__SEQ_BLUE__", json.dumps(SEQ_BLUE))
        .replace("__DIVERGING__", json.dumps(DIVERGING))
        .replace("__BIVARIATE__", json.dumps(BIVARIATE))
        .replace("__HOTSPOT_FILLS__", json.dumps(HOTSPOT_NEUTRAL_FILLS))
        .replace("__HOTSPOT_PATTERN_STYLES__", json.dumps(HOTSPOT_PATTERN_STYLES))
        .replace("__HOTSPOT_ORDER__", json.dumps(HOTSPOT_ORDER)))

    callback_args = dict(
        tract_source=tract_source, parcel_source=parcel_source, climate_source=climate_source,
        climate_display_source=climate_display_source, grid_source=grid_source,
        housing_sample=housing_sample_source, housing_point_source=housing_point_source,
        selected_zip_source=selected_zip_source, selected_precinct_source=selected_precinct_source,
        legend_mask_source=legend_mask_source,
        legend_highlight_polygon_source=legend_highlight_polygon_source,
        legend_highlight_point_source=legend_highlight_point_source,
        legend_mask_renderer=legend_mask_renderer,
        legend_highlight_polygon_renderer=legend_highlight_polygon_renderer,
        legend_highlight_point_renderer=legend_highlight_point_renderer,
        tract_renderer=tract_renderer, parcel_renderer=parcel_renderer, climate_renderer=climate_renderer,
        grid_renderer=grid_renderer, housing_renderer=housing_point_renderer,
        hotspot_pattern_renderers=hotspot_pattern_renderers,
        kr15=kriging_renderers["15"], kr20=kriging_renderers["20"], kr25=kriging_renderers["25"], kr30=kriging_renderers["30"],
        layer_select=layer_select, gmt_select=gmt_select, housing_select=housing_select,
        opacity_slider=opacity_slider, overlap_toggle=overlap_toggle, overlap_a=overlap_a,
        overlap_b=overlap_b, threshold_slider=threshold_slider, legend_div=legend_div,
        legend_filter_status=legend_filter_status, layer_info=layer_info,
        overlap_summary=overlap_summary, map_guide=map_guide,
        map_actions=map_actions, hist_source=hist_source, hist_plot=hist_plot, hist_xaxis=hist_plot.xaxis[0], hist_summary=hist_summary,
        point_status=point_status, map_plot=map_plot, quick_decision_status=quick_decision_status,
        report_geography=report_geography, report_status=report_status,
    )
    update_callback = CustomJS(args=callback_args, code=callback_code)
    map_plot.js_on_event(DocumentReady, update_callback)
    for widget, prop in [
        (layer_select, "value"), (gmt_select, "value"), (housing_select, "value"),
        (opacity_slider, "value_throttled"), (overlap_toggle, "active"),
        (overlap_a, "value"), (overlap_b, "value"), (threshold_slider, "value_throttled"),
    ]:
        widget.js_on_change(prop, update_callback)
    init_trigger.js_on_change("active", update_callback)

    range_callback = CustomJS(args=callback_args, code=r"""
if(window.__chei_point_timer)clearTimeout(window.__chei_point_timer);
window.__chei_point_timer=setTimeout(()=>{if(layer_select.value!=='housing_points'||window.location.protocol==='file:'||window.location.protocol==='about:'||window.location.protocol==='sandbox:'||!window.fetch)return;const xmin=map_plot.x_range.start,xmax=map_plot.x_range.end,ymin=map_plot.y_range.start,ymax=map_plot.y_range.end,url=`/api/housing-points?housing_type=${encodeURIComponent(housing_select.value)}&xmin=${xmin}&xmax=${xmax}&ymin=${ymin}&ymax=${ymax}&max_points=50000`;point_status.text='<span class="status-dot loading"></span>Refreshing housing-stock points for the current viewport…';fetch(url).then(r=>r.json()).then(d=>{const alpha=Math.min(opacity_slider.value,.72);housing_point_source.data={x:d.x,y:d.y,color:d.color,kind:d.kind,display_alpha:new Array(d.x.length).fill(alpha)};housing_point_source.change.emit();if(window.CHEI)window.CHEI.refreshHousingLegendContext();point_status.text=`<span class='status-dot'></span>Displaying ${d.n_returned.toLocaleString()} of ${d.n_total.toLocaleString()} source points in the current viewport.`;}).catch(()=>{});},350);
""")
    for rng in [map_plot.x_range, map_plot.y_range]:
        rng.js_on_change("start", range_callback)
        rng.js_on_change("end", range_callback)

    selection_callback = CustomJS(args=dict(
        source=tract_source, selected_div=selected_div,
        climate_profile_source=climate_profile_source, profile_source=profile_source,
    ), code=r"""
const inds=source.selected.indices;if(!inds.length)return;const i=inds[0],d=source.data;const fmt=(v,n=0)=>Number(v).toLocaleString(undefined,{minimumFractionDigits:n,maximumFractionDigits:n});
const on=(v)=>Number(v)===1?'on':'off';selected_div.text=`<div class='panel-eyebrow'>SELECTED CENSUS TRACT</div><h3>${d.NAME[i]||''} <span>${d.GEOID[i]}</span></h3><div class='selected-grid'><div><b>${fmt(d.CHEI_2050[i],3)}</b><span>CHEI 2050</span></div><div><b>${fmt(d.SVI[i],3)}</b><span>SVI 2020</span></div><div><b>${fmt(d.pop_chg[i])}</b><span>Population change</span></div><div><b>${fmt(d.hh_chg[i])}</b><span>Household change</span></div></div><p><strong>Compound hotspot:</strong> ${d.hotspot_combo[i]} (${fmt(d.hotspot_score[i])}/3)<br><strong>Parcel housing-unit change:</strong> ${fmt(d.parcel_hu_change[i])}</p><div class='selected-thresholds'><span class='${on(d.hazard_high[i])}'>Precipitation</span><span class='${on(d.growth_high[i])}'>Household growth</span><span class='${on(d.svi_high[i])}'>SVI</span></div>`;
climate_profile_source.data={gmt:[1.5,2.0,2.5,3.0],precip:[d.pr_15[i],d.pr_20[i],d.pr_25[i],d.pr_30[i]]};climate_profile_source.change.emit();profile_source.data={category:['Population','Households','Employment'],v2020:[d.hp_2020[i],d.hh_2020[i],d.j_2020[i]],v2050:[d.hp_2050[i],d.hh_2050[i],d.j_2050[i]]};profile_source.change.emit();
""")
    tract_source.selected.js_on_change("indices", selection_callback)

    search_callback = CustomJS(args=dict(
        source=tract_source, text=search_input, status=search_status,
        xr=map_plot.x_range, yr=map_plot.y_range, report_geography=report_geography,
    ), code=r"""
const q=String(text.value||'').trim(),d=source.data;let idx=-1;for(let i=0;i<d.GEOID.length;i++){if(String(d.GEOID[i])===q){idx=i;break;}}if(idx<0){status.text='<span class="error-text">No exact GEOID match was found.</span>';return;}source.selected.indices=[idx];source.selected.change.emit();const px=Math.max((d.bbox_maxx[idx]-d.bbox_minx[idx])*.35,2000),py=Math.max((d.bbox_maxy[idx]-d.bbox_miny[idx])*.35,2000);xr.start=d.bbox_minx[idx]-px;xr.end=d.bbox_maxx[idx]+px;yr.start=d.bbox_miny[idx]-py;yr.end=d.bbox_maxy[idx]+py;report_geography.value='tract';status.text='<span class="success-text">Tract located and selected.</span>';
""")
    search_button.js_on_click(search_callback)
    search_input.js_on_event("value_submit", search_callback)

    zip_search_callback = CustomJS(args=dict(
        source=zipcode_source, selected_source=selected_zip_source,
        text=zip_search_input, status=zip_search_status,
        xr=map_plot.x_range, yr=map_plot.y_range, report_geography=report_geography,
    ), code=r"""
const q=String(text.value||'').trim();
if(!/^\d{5}$/.test(q)){status.text='<span class="error-text">Enter a five-digit ZIP code.</span>';return;}
const d=source.data;let idx=-1;
for(let i=0;i<d.ZIP.length;i++){if(String(d.ZIP[i]).padStart(5,'0')===q){idx=i;break;}}
if(idx<0){status.text='<span class="error-text">No matching Harris County ZIP boundary was found.</span>';return;}
selected_source.data={xs:[d.xs[idx]],ys:[d.ys[idx]],ZIP:[d.ZIP[idx]],POSTAL:[d.POSTAL[idx]],STATE:[d.STATE[idx]],ZIP_TYPE:[d.ZIP_TYPE[idx]],tract_indices:[d.tract_indices[idx]]};
selected_source.change.emit();
const px=Math.max((d.bbox_maxx[idx]-d.bbox_minx[idx])*.22,1800),py=Math.max((d.bbox_maxy[idx]-d.bbox_miny[idx])*.22,1800);
xr.start=d.bbox_minx[idx]-px;xr.end=d.bbox_maxx[idx]+px;yr.start=d.bbox_miny[idx]-py;yr.end=d.bbox_maxy[idx]+py;
const postal=d.POSTAL[idx]?` · ${d.POSTAL[idx]}`:'';report_geography.value='zip';
status.text=`<span class="success-text"><b>ZIP ${q}</b>${postal} located.</span><br><span class="locator-note">Boundary shown for navigation; dashboard indicators remain at their source geographies.</span>`;
""")
    zip_search_button.js_on_click(zip_search_callback)
    zip_search_input.js_on_event("value_submit", zip_search_callback)

    show_all_zip_toggle.js_on_change("active", CustomJS(args=dict(
        toggle=show_all_zip_toggle, renderer=all_zip_renderer,
    ), code=r"""
renderer.visible=toggle.active;
toggle.label=toggle.active?'Hide all ZIP-code boundaries':'Show all ZIP-code boundaries';
"""))

    precinct_search_callback = CustomJS(args=dict(
        source=precinct_source, selected_source=selected_precinct_source,
        selector=precinct_select, status=precinct_search_status,
        xr=map_plot.x_range, yr=map_plot.y_range, report_geography=report_geography,
    ), code=r"""
const q=String(selector.value||'').trim(),d=source.data;let idx=-1;
for(let i=0;i<d.PCT_NO.length;i++){if(String(d.PCT_NO[i])===q){idx=i;break;}}
if(idx<0){status.text='<span class="error-text">No matching commissioner precinct was found.</span>';return;}
selected_source.data={xs:[d.xs[idx]],ys:[d.ys[idx]],PCT_NO:[d.PCT_NO[idx]],AREA_IN_MI:[d.AREA_IN_MI[idx]],tract_indices:[d.tract_indices[idx]]};selected_source.change.emit();
const px=Math.max((d.bbox_maxx[idx]-d.bbox_minx[idx])*.10,2500),py=Math.max((d.bbox_maxy[idx]-d.bbox_miny[idx])*.10,2500);
xr.start=d.bbox_minx[idx]-px;xr.end=d.bbox_maxx[idx]+px;yr.start=d.bbox_miny[idx]-py;yr.end=d.bbox_maxy[idx]+py;report_geography.value='precinct';
status.text=`<span class="success-text"><b>Commissioner Precinct ${q}</b> located.</span><br><span class="locator-note">Boundary shown for navigation; reports summarize intersecting census tracts rather than creating an official precinct aggregate.</span>`;
""")
    precinct_find_button.js_on_click(precinct_search_callback)

    show_all_precinct_toggle.js_on_change("active", CustomJS(args=dict(
        toggle=show_all_precinct_toggle, renderer=all_precinct_renderer,
    ), code=r"""
renderer.visible=toggle.active;
toggle.label=toggle.active?'Hide all commissioner precinct boundaries':'Show all commissioner precinct boundaries';
"""))

    quick_exposure_button.js_on_click(CustomJS(code="if(window.CHEI)window.CHEI.quickDecision('exposure');"))
    quick_overlap_button.js_on_click(CustomJS(code="if(window.CHEI)window.CHEI.quickDecision('overlap');"))
    quick_adaptation_button.js_on_click(CustomJS(code="if(window.CHEI)window.CHEI.quickDecision('adaptation');"))
    quick_selected_button.js_on_click(CustomJS(code="if(window.CHEI)window.CHEI.quickDecision('selected');"))
    report_button.js_on_click(CustomJS(code="if(window.CHEI)window.CHEI.generateReport();"))

    reset_button.js_on_click(CustomJS(args=dict(xr=map_plot.x_range, yr=map_plot.y_range), code=f"xr.start={minx-padx};xr.end={maxx+padx};yr.start={miny-pady};yr.end={maxy+pady};"))

    header = Div(text=f"""
    <header class='site-header'>
      <div class='brand-mark'><div class='county-shape'>HC</div></div>
      <div class='brand-copy'><div class='brand-line'>HARRIS COUNTY, TEXAS</div><div class='brand-sub'>Climate + Housing Exposure</div></div>
      <div class='header-tag'>Research &amp; Planning Dashboard</div>
    </header>
    <section class='hero'>
      <div><div class='hero-kicker'>CLIMATE HOUSING EXPOSURE INDEX</div>
      <h1>Where extreme precipitation, growth, housing, and vulnerability overlap</h1>
      <p>An interactive platform connecting GMT threshold-based precipitation extremes with housing, population, employment, social vulnerability, and land-use change to support place-based climate-risk assessment in Harris County.</p></div>
      <div class='hero-badge'><b>2020</b><span>baseline</span><i>→</i><b>2050</b><span>projection</span></div>
    </section>
    """, width=PAGE_WIDTH, css_classes=["header-wrapper"])

    overview = Div(text="""
    <section class='overview-band'>
      <details open>
        <summary><span><b>About this dashboard</b><small>Overview, functions, audiences, and practical applications</small></span><i>Expand / collapse</i></summary>
        <div class='overview-grid'>
          <article><div class='overview-number'>01</div><h3>Dashboard Overview</h3><p>The Climate-Housing Exposure Index Dashboard is an interactive web-based platform for Harris County, Texas. It visualizes how future precipitation extremes intersect with housing, population, employment, social vulnerability, and land-use change.</p></article>
          <article><div class='overview-number'>02</div><h3>Key Functions</h3><p>Explore extreme precipitation under 1.5°C, 2.0°C, 2.5°C, and 3.0°C warming scenarios; compare 2020 and 2050 conditions; examine CHEI, housing, land use, growth, and patterned compound hotspots; filter maps by clicking legend classes; locate places by tract, ZIP code, or commissioner precinct; and generate a one-page decision brief.</p></article>
          <article><div class='overview-number'>03</div><h3>Potential Audiences</h3><p>Designed for researchers, planners, local governments, housing and community-development agencies, emergency managers, policymakers, nonprofit organizations, and community stakeholders.</p></article>
          <article><div class='overview-number'>04</div><h3>Practical Applications</h3><p>Supports climate adaptation, housing resilience, growth management, infrastructure investment, vulnerability assessment, and environmental-justice research by highlighting areas of overlapping future pressures.</p></article>
        </div>
      </details>
    </section>
    """, width=PAGE_WIDTH, css_classes=["overview-wrapper"])

    kpis = Div(text=f"""
    <div class='kpi-grid'>
      <div class='kpi-card'><div class='kpi-icon'>P</div><div><b>{totals['population_2050']/1_000_000:.2f}M</b><span>Projected population, 2050</span><small>+{totals['population_change']/1_000_000:.2f}M from 2020</small></div></div>
      <div class='kpi-card'><div class='kpi-icon'>H</div><div><b>{totals['household_change']/1000:,.0f}K</b><span>Projected household growth</span><small>2020–2050</small></div></div>
      <div class='kpi-card'><div class='kpi-icon'>J</div><div><b>{totals['employment_2050']/1_000_000:.2f}M</b><span>Projected employment, 2050</span><small>+{totals['employment_change']/1_000_000:.2f}M jobs</small></div></div>
      <div class='kpi-card alert'><div class='kpi-icon'>!</div><div><b>{counts_report['all_three_high_hotspots']}</b><span>All-three-high hotspot tracts</span><small>Hazard + growth + vulnerability</small></div></div>
    </div>
    """, width=PAGE_WIDTH, css_classes=["kpi-wrapper"])

    controls = column(
        init_trigger,
        Div(text="<div class='section-title'><span>01</span> Explore layers</div>", width=CONTROL_CONTENT_WIDTH),
        layer_select, row(gmt_select, housing_select, width=CONTROL_CONTENT_WIDTH), opacity_slider,
        Div(text="<div class='section-title top-space'><span>02</span> Screen overlap</div>", width=CONTROL_CONTENT_WIDTH),
        overlap_toggle, overlap_a, overlap_b, threshold_slider, overlap_summary,
        Div(text="<div class='section-title top-space'><span>03</span> Locate a tract</div>", width=CONTROL_CONTENT_WIDTH),
        row(search_input, search_button, width=CONTROL_CONTENT_WIDTH), search_status,
        Div(text="<div class='section-title top-space'><span>04</span> Locate a ZIP code</div>", width=CONTROL_CONTENT_WIDTH),
        row(zip_search_input, zip_search_button, width=CONTROL_CONTENT_WIDTH),
        zip_search_status, show_all_zip_toggle,
        Div(text="<div class='section-title top-space'><span>05</span> Locate a commissioner precinct</div>", width=CONTROL_CONTENT_WIDTH),
        row(precinct_select, precinct_find_button, width=CONTROL_CONTENT_WIDTH),
        precinct_search_status, show_all_precinct_toggle, reset_button,
        legend_div, legend_filter_status, layer_info, hist_plot, hist_summary,
        width=CONTROL_COLUMN_WIDTH, css_classes=["controls-column"],
    )
    map_column = column(map_plot, point_status, map_guide, map_actions, width=MAP_COLUMN_WIDTH, css_classes=["map-column"])
    insights = column(
        Div(text="<div class='insight-section-title'><span>QUICK DECISION VIEW</span><h3>Start with a planning question</h3></div>", width=INSIGHT_CONTENT_WIDTH),
        row(quick_exposure_button, quick_overlap_button, width=INSIGHT_CONTENT_WIDTH),
        row(quick_adaptation_button, quick_selected_button, width=INSIGHT_CONTENT_WIDTH),
        quick_decision_status, selected_div,
        Div(text="<div class='insight-section-title report-title'><span>ONE-PAGE DECISION BRIEF</span><h3>Turn the dashboard into a shareable tool</h3></div>", width=INSIGHT_CONTENT_WIDTH),
        report_geography, report_button, report_status,
        climate_profile, profile_plot,
        Div(text="<div class='insight-note'><b>Interpretation reminder</b><p>This dashboard supports screening and exploration. Modeled and projected values should be validated with authoritative local data before decisions are made.</p><ul><li>Click a legend class to locate matches.</li><li>Click a tract for its exact profile.</li><li>Locate familiar areas by ZIP code or commissioner precinct.</li><li>Generate a print-ready decision brief for a selected geography.</li></ul></div>", width=INSIGHT_CONTENT_WIDTH),
        width=INSIGHTS_COLUMN_WIDTH, css_classes=["insights-column"],
    )
    explore_row = row(controls, map_column, insights, width=PAGE_WIDTH, css_classes=["explore-row"])
    explore_layout = column(kpis, explore_row, width=PAGE_WIDTH, css_classes=["explore-layout"])

    inventory_rows = "".join(
        f"<tr><td><code>{html_lib.escape(str(r.gdb_layer))}</code></td><td>{int(r.feature_count):,}</td><td>{html_lib.escape(str(r.geometry_type))}</td></tr>"
        for r in inventory.itertuples(index=False)
    )
    methods_html = f"""
    <div class='content-page'>
      <div class='content-eyebrow'>DATA &amp; METHODS</div>
      <h2>Dashboard architecture and reproducibility</h2>
      <div class='method-grid'>
        <section><h3>Climate precipitation</h3><p>Four GMT thresholds—1.5°C, 2.0°C, 2.5°C, and 3.0°C relative to 1850–1899—are available as model points and tract aggregations. The uploaded GDB did not expose the four named kriging rasters to the open-source FileGDB reader, so the preprocessing script derives ordinary-kriging display surfaces and records fitted semivariogram parameters.</p></section>
        <section><h3>Exposure and growth</h3><p>Tract geometry is consolidated once and joined to CHEI, SVI, precipitation, population, household, employment, and compound-hotspot attributes. Parcel housing-unit changes are spatially aggregated to tracts for overlap analysis.</p></section>
        <section><h3>Housing-stock performance</h3><p>The package retains all {counts_report['single_family_points']:,} single-family and {counts_report['multi_family_points']:,} multi-family source points in sorted NumPy arrays. The full server returns viewport-filtered points; the standalone HTML uses a complete 1 km density grid and representative point sample.</p></section>
        <section><h3>Geographic location and reporting</h3><p>The revised geodatabase includes {counts_report['zip_codes']:,} Harris County ZIP-code boundaries and {counts_report['commissioner_precincts']:,} commissioner precincts. Users can locate and outline either geography, optionally display all boundaries, and generate tract-based screening summaries without creating official ZIP- or precinct-level source aggregates.</p></section>
        <section><h3>Interactive legends and compound screening</h3><p>Every displayed legend class can be selected individually to highlight and zoom to matching tracts, parcels, cells, or points. For kriging surfaces, the clicked class locates census tracts in the corresponding precipitation range. The compound-hotspot typology is noncompensatory and retains all eight combinations generated by three countywide 80th-percentile conditions: GMT +2.5°C precipitation ≥ 203.603 mm, household growth ≥ 746, and SVI ≥ 0.88386. Diagonal lines represent hazard, vertical lines represent growth, and dots represent social vulnerability, allowing combinations to be interpreted without relying on color alone. A separate bivariate tool lets users select two factors and test alternative percentile cutoffs.</p></section>
      </div>
      <div class='notice'><b>Data audit.</b> The geodatabase contains {report['available_vector_layers']} exposed vector layers, including <code>Harris_County_Zipcodes</code> and <code>Harris_County_Commissioner_Precincts</code>. These boundaries support location, orientation, and transparent tract-based screening summaries; no official ZIP- or precinct-level aggregation is created. The two CHEI 2050 feature classes have identical index values and are consolidated. The supplied tract precipitation inventory uses “extreme_precipi,” whereas the actual GDB layer names use “extreme_precip.”</div>
      <h3>Uploaded geodatabase inventory</h3>
      <div class='table-wrap'><table class='data-table'><thead><tr><th>Layer</th><th>Features</th><th>Geometry</th></tr></thead><tbody>{inventory_rows}</tbody></table></div>
      <h3>Source organizations</h3>
      <p class='source-links'><a href='https://www.depts.ttu.edu/csc/' target='_blank'>Texas Tech University Climate Center</a> · <a href='https://www.h-gac.com/regional-growth-forecast' target='_blank'>H-GAC Regional Growth Forecast</a> · <a href='https://datalab.h-gac.com/rluis/' target='_blank'>H-GAC Land Use Dashboard</a> · <a href='https://hcad.org/hcad-online-services/pdata/' target='_blank'>Harris Central Appraisal District</a> · <a href='https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html' target='_blank'>CDC/ATSDR SVI</a></p>
    </div>
    """
    methods_div = Div(text=methods_html, width=PAGE_WIDTH, css_classes=["content-tab"])

    terms_html = """
    <div class='content-page terms-page'>
      <div class='content-eyebrow'>TERMS OF USE</div>
      <h2>Climate Housing Exposure Index Dashboard</h2>
      <p>This dashboard is developed to visualize and explore spatial data related to precipitation extremes, housing stocks, population, and land-use projections. The information provided is intended for research, educational, and informational purposes only.</p>
      <p>The data displayed in this dashboard are derived from multiple sources, including the <a href='https://www.depts.ttu.edu/csc/' target='_blank'>Texas Tech University Climate Science Center</a>, <a href='https://www.h-gac.com/regional-growth-forecast' target='_blank'>Houston-Galveston Area Council (H-GAC) Regional Growth Forecast</a>, <a href='https://datalab.h-gac.com/rluis/' target='_blank'>H-GAC Land Use Dashboard</a>, <a href='https://hcad.org/hcad-online-services/pdata/' target='_blank'>Harris Central Appraisal District (HCAD)</a>, and <a href='https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html' target='_blank'>CDC SVI Data</a>, and may include modeled, estimated, or projected values. While reasonable efforts have been made to ensure data accuracy and reliability, no guarantee is made regarding the completeness, accuracy, or timeliness of the information presented.</p>
      <p>Users should not rely solely on the information provided in this dashboard for decision-making. The creators and affiliated institutions assume no responsibility or liability for any errors, omissions, or damages arising from the use of this information.</p>
      <p>Unless otherwise noted, the data and visualizations are provided for non-commercial use. Proper attribution should be given when referencing or reproducing the materials.</p>
      <p>By accessing and using this dashboard, users acknowledge and agree to these terms.</p>
      <div class='contact-card'><div>QUESTIONS OR FEEDBACK</div><b>Kaifa Lu</b><span>CECREH</span><a href='mailto:Kaifa.Lu@ttu.edu'>Kaifa.Lu@ttu.edu</a></div>
    </div>
    """
    terms_div = Div(text=terms_html, width=PAGE_WIDTH, css_classes=["content-tab"])

    tabs = Tabs(tabs=[
        TabPanel(child=explore_layout, title="Explore Dashboard"),
        TabPanel(child=methods_div, title="Data & Methods"),
        TabPanel(child=terms_div, title="Terms of Use"),
    ], width=PAGE_WIDTH, css_classes=["main-tabs"])

    footer = Div(text="""
    <footer class='site-footer'>
      <div class='footer-brand'><b>Climate Housing Exposure Index Dashboard</b><span>Harris County, Texas</span></div>
      <div class='footer-purpose'><b>Research · Education · Planning</b><span>Exploratory climate, housing, growth, and vulnerability screening</span></div>
      <div class='footer-contact'><span>Questions or feedback</span><a href='mailto:Kaifa.Lu@ttu.edu'>Kaifa.Lu@ttu.edu</a><small>Kaifa Lu · CECREH</small></div>
    </footer>
    """, width=PAGE_WIDTH, css_classes=["footer-wrapper"])
    page = column(header, overview, tabs, footer, width=PAGE_WIDTH, css_classes=["dashboard-shell"])

    css_rules = f":root{{--navy:{NAVY};--deep:{DEEP_NAVY};--teal:{TEAL};--aqua:{AQUA};--gold:{GOLD};--light:{LIGHT};--text:{TEXT};--muted:{MUTED};}}\n" + r"""
    *{box-sizing:border-box}html,body{margin:0;padding:0;background:#edf2f5;color:var(--text);font-family:Inter,"Segoe UI",Arial,sans-serif}body{min-width:1180px;overflow-x:auto}
    :host(.dashboard-shell),.bk-Column.dashboard-shell{width:1760px!important;max-width:1760px!important;margin:0 auto!important;background:#fff!important;box-shadow:0 0 40px rgba(13,36,56,.16)}
    :host(.header-wrapper),:host(.overview-wrapper),:host(.footer-wrapper),:host(.kpi-wrapper),.header-wrapper,.overview-wrapper,.footer-wrapper,.kpi-wrapper{width:1760px!important;max-width:1760px!important}
    .site-header{height:88px;background:var(--deep);color:#fff;display:flex;align-items:center;padding:0 42px;gap:16px;border-bottom:5px solid var(--teal)}
    .brand-mark{width:56px;height:56px;border:2px solid rgba(255,255,255,.75);display:grid;place-items:center;transform:rotate(45deg);border-radius:8px;background:rgba(255,255,255,.06)}.county-shape{transform:rotate(-45deg);font-weight:800;letter-spacing:-1px;font-size:18px}.brand-copy{line-height:1.1}.brand-line{font-size:13px;letter-spacing:2.1px;color:#b8d7dd;font-weight:700}.brand-sub{font-size:24px;font-weight:650;margin-top:4px}.header-tag{margin-left:auto;padding:10px 16px;border:1px solid rgba(255,255,255,.25);border-radius:3px;font-size:13px;letter-spacing:.5px}
    .hero{background:linear-gradient(105deg,#17324d 0%,#1d5061 72%,#168c95 100%);color:#fff;padding:29px 46px 31px;display:flex;gap:40px;align-items:center;min-height:176px}.hero>div:first-child{max-width:1280px}.hero-kicker,.content-eyebrow,.panel-eyebrow{font-size:11px;letter-spacing:1.8px;font-weight:800;color:#43bcc4;margin-bottom:8px}.hero h1{font-size:33px;line-height:1.18;margin:0 0 11px;font-weight:680}.hero p{font-size:15px;line-height:1.55;color:#e1edf0;margin:0;max-width:1180px}.hero-badge{margin-left:auto;min-width:220px;display:grid;grid-template-columns:1fr auto 1fr;grid-template-rows:auto auto;align-items:center;text-align:center;border-left:1px solid rgba(255,255,255,.3);padding-left:36px}.hero-badge b{font-size:30px}.hero-badge span{font-size:11px;text-transform:uppercase;letter-spacing:1.3px;color:#c6e3e7}.hero-badge i{grid-row:1/3;grid-column:2;font-style:normal;font-size:24px;color:var(--gold);padding:0 9px}
    .overview-band{background:#edf4f6;border-bottom:1px solid #d7e2e7;padding:14px 28px 17px}.overview-band details{background:#fff;border:1px solid #d5e1e6;box-shadow:0 2px 8px rgba(23,50,77,.04)}.overview-band summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-left:5px solid var(--teal);color:var(--navy)}.overview-band summary::-webkit-details-marker{display:none}.overview-band summary span{display:flex;align-items:baseline;gap:13px}.overview-band summary b{font-size:15px}.overview-band summary small{font-size:11px;color:var(--muted);font-weight:500}.overview-band summary i{font-style:normal;font-size:10px;color:#4d6878;text-transform:uppercase;letter-spacing:.7px}.overview-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;padding:0 16px 16px}.overview-grid article{position:relative;background:#f6f9fa;border-top:3px solid var(--teal);padding:16px 16px 15px;min-height:165px}.overview-number{position:absolute;right:12px;top:9px;color:#c8d8de;font-size:23px;font-weight:800}.overview-grid h3{margin:0 0 9px;color:var(--navy);font-size:14px}.overview-grid p{margin:0;font-size:11.5px;line-height:1.55;color:#465a68}
    :host(.kpi-wrapper),.kpi-wrapper{padding:18px 28px 9px;background:#f4f7f9}.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}.kpi-card{background:#fff;border:1px solid #dae4e9;border-top:4px solid var(--teal);padding:16px 18px;display:flex;gap:13px;min-height:105px;box-shadow:0 2px 8px rgba(23,50,77,.05)}.kpi-card.alert{border-top-color:#c9463d}.kpi-icon{width:39px;height:39px;background:#e4f3f3;color:var(--teal);border-radius:50%;display:grid;place-items:center;font-weight:800;flex:0 0 auto}.kpi-card.alert .kpi-icon{background:#f9e5e2;color:#b2182b}.kpi-card b{display:block;font-size:25px;color:var(--navy);line-height:1}.kpi-card span{display:block;font-size:13px;font-weight:700;margin-top:7px}.kpi-card small{display:block;color:var(--muted);font-size:11px;margin-top:4px}
    :host(.explore-layout),.explore-layout{width:1760px!important;background:#f4f7f9}:host(.explore-row),.explore-row{width:1760px!important;align-items:flex-start!important}
    :host(.controls-column),:host(.map-column),:host(.insights-column),.controls-column,.map-column,.insights-column{padding:14px 10px 22px;background:#f4f7f9;align-self:flex-start!important}:host(.controls-column),.controls-column{padding-left:24px}:host(.insights-column),.insights-column{padding-right:24px}:host(.map-column),.map-column{padding-left:5px;padding-right:5px}.section-title{font-size:12px;text-transform:uppercase;letter-spacing:.9px;color:var(--navy);font-weight:800;border-bottom:1px solid #dbe4e9;padding:5px 0 9px;margin-bottom:8px}.section-title span{background:var(--teal);color:#fff;border-radius:12px;padding:3px 7px;margin-right:7px}.top-space{margin-top:10px}
    .chei-panel{background:#fff;border:1px solid #d8e2e8;border-left:4px solid var(--teal);padding:14px 16px;margin-top:9px;box-shadow:0 2px 6px rgba(23,50,77,.035);overflow:visible!important}.chei-panel h4{font-size:13px;line-height:1.35;margin:0 0 10px;color:var(--navy)}.chei-panel p{font-size:11.5px;line-height:1.5;margin:6px 0;color:#465a68}.legend-row{display:grid;grid-template-columns:27px minmax(0,1fr) auto;align-items:center;column-gap:9px;font-size:11px;margin:6px 0;min-height:15px}.legend-row span{width:27px;height:14px;border:1px solid rgba(0,0,0,.13);display:block}.legend-row b{font-weight:700;line-height:1.25;min-width:0}.legend-row em{font-style:normal;color:#627581;font-weight:700}.legend-unit{font-size:10px;color:var(--muted);margin-top:9px;text-transform:uppercase;letter-spacing:.7px}.legend-subtitle{font-size:9.5px;color:#607786;font-weight:800;letter-spacing:.75px;margin:14px 0 7px}.threshold-card{background:#f1f6f7;border:1px solid #d4e3e6;padding:10px 11px;margin:7px 0 12px}.threshold-card>div:not(.threshold-kicker){display:grid;grid-template-columns:1fr;gap:2px;padding:6px 0;border-bottom:1px solid #dce7ea}.threshold-card>div:last-child{border-bottom:0}.threshold-card b{font-size:10.5px;color:var(--navy)}.threshold-card span{font-size:10.5px;color:#4f6674}.threshold-kicker{font-size:9px;font-weight:800;letter-spacing:.65px;color:#087d88;margin-bottom:3px}.threshold-card.compact{margin-bottom:10px}.hotspot-row{grid-template-columns:36px minmax(0,1fr) auto;margin:6px 0;min-height:20px}.hotspot-row .pattern-swatch{width:36px;height:19px;border:1px solid #9aa8ae;background-repeat:repeat}.pattern-key{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;background:#f7f9fa;border:1px solid #dce5e9;padding:8px 9px;margin:7px 0 10px}.pattern-key>b{grid-column:1/4;font-size:9px;text-transform:uppercase;letter-spacing:.65px;color:#55707d}.pattern-key>span{display:flex;align-items:center;gap:5px;font-size:9.5px;font-weight:700;color:#334c5a}.mini-pattern{width:22px;height:14px;border:1px solid #9aa8ae;background-color:#eef2f3;display:inline-block;flex:0 0 auto}.hazard-pattern{background-image:repeating-linear-gradient(135deg,transparent 0,transparent 4px,#263b4a 4px,#263b4a 5.3px)}.growth-pattern{background-image:repeating-linear-gradient(90deg,transparent 0,transparent 4px,#263b4a 4px,#263b4a 5.3px)}.svi-pattern{background-image:radial-gradient(circle at 2px 2px,#263b4a 1px,transparent 1.2px);background-size:6px 6px}.layer-bullets{margin:10px 0 2px;padding-left:17px;color:#405664}.layer-bullets li{font-size:11px;line-height:1.45;margin:5px 0}.overlap-panel{border-left-color:#354a8c}.hist-summary{background:#fff;border:1px solid #d8e2e8;border-top:0;padding:5px 10px 7px}.hist-summary p{font-size:10.5px;line-height:1.45;color:var(--muted);margin:3px 0}.search-status{font-size:11px;padding:3px 1px;line-height:1.4}.zip-search-status{min-height:42px}.locator-note{font-size:10px;color:#6a7d87}.success-text{color:#168c60}.error-text{color:#b2182b}
    .legend-button{width:100%;border:1px solid transparent;background:transparent;text-align:left;padding:4px 5px;border-radius:2px;cursor:pointer;font-family:inherit;color:inherit}.legend-button:hover{background:#eef6f7;border-color:#b9d9dc}.legend-button:focus-visible{outline:2px solid var(--gold);outline-offset:1px}.legend-button.active{background:#fff4d9;border-color:#e3ad35;box-shadow:inset 3px 0 0 var(--gold)}.legend-button span{pointer-events:none}.legend-filter-status{background:#f7fafb;border:1px solid #d8e2e8;border-top:0;padding:8px 10px;margin-bottom:2px;font-size:10.5px;line-height:1.4}.legend-help{color:#5d707b}.legend-selection{display:grid;grid-template-columns:1fr auto;gap:3px 8px;align-items:center}.legend-selection b{color:var(--navy)}.legend-selection span{color:#5d707b;text-align:right}.legend-selection div{grid-column:1/3;display:flex;gap:6px;margin-top:4px}.legend-selection button{border:1px solid #a9bdc6;background:#fff;color:var(--navy);padding:4px 8px;font-size:9.5px;font-weight:700;cursor:pointer}.legend-selection button:first-child{background:var(--teal);color:#fff;border-color:var(--teal)}.precinct-search-status{min-height:42px}.insight-section-title{background:#fff;border:1px solid #d8e2e8;border-top:4px solid var(--teal);padding:11px 13px 10px;margin-bottom:4px}.insight-section-title span{font-size:9px;letter-spacing:1.1px;color:var(--teal);font-weight:800}.insight-section-title h3{font-size:14px;color:var(--navy);margin:4px 0 0}.insight-section-title.report-title{border-top-color:var(--gold);margin-top:7px}.insight-section-title.report-title span{color:#a56f05}:host(.quick-action) .bk-btn,.quick-action .bk-btn{white-space:normal!important;line-height:1.2!important;font-size:10.5px!important;font-weight:700!important;padding:6px 7px!important}.quick-decision-status,.report-status{background:#fff;border:1px solid #d8e2e8;padding:9px 11px;margin:3px 0 7px;font-size:10.5px;line-height:1.42}.quick-status b{color:var(--navy);font-size:11.5px}.quick-status p{margin:4px 0 0;color:#506572}.quick-status.success{border-left:3px solid #2ca25f;padding-left:8px}.quick-status.error{border-left:3px solid #b2182b;padding-left:8px}
    .map-status{background:#fff;border:1px solid #d8e2e8;padding:10px 14px;font-size:11px;color:#526673;margin-top:5px}.status-dot{display:inline-block;width:8px;height:8px;background:#2ca25f;border-radius:50%;margin-right:7px}.status-dot.loading{background:var(--gold)}code{font-family:Consolas,monospace;background:#eef2f4;padding:1px 4px;border-radius:3px}.map-guide-wrapper{margin-top:8px}.map-guide{background:#fff;border:1px solid #d8e2e8;border-top:4px solid var(--teal);padding:17px 19px 18px;box-shadow:0 2px 7px rgba(23,50,77,.04)}.guide-heading{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid #e1e8ec;padding-bottom:10px;margin-bottom:12px}.guide-heading span{font-size:9.5px;letter-spacing:1.2px;font-weight:800;color:var(--teal)}.guide-heading h3{font-size:16px;color:var(--navy);margin:0}.guide-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.guide-grid>div{background:#f3f7f8;padding:11px 12px;min-height:78px}.guide-grid b{font-size:11px;color:var(--navy)}.guide-grid p{font-size:10.5px;line-height:1.45;color:#4d6370;margin:5px 0 0}
    .map-actions-wrapper{margin-top:8px}.action-panel{background:#fff;border:1px solid #d8e2e8;border-top:4px solid var(--gold);padding:16px 19px 17px;box-shadow:0 2px 7px rgba(23,50,77,.04)}.action-heading{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid #e1e8ec;padding-bottom:9px;margin-bottom:11px}.action-heading span{font-size:9.5px;letter-spacing:1.2px;font-weight:800;color:#a56f05}.action-heading h3{font-size:15px;color:var(--navy);margin:0}.action-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.action-grid>div{position:relative;background:#f7f6f1;padding:11px 12px 11px 42px;min-height:80px}.action-grid i{position:absolute;left:11px;top:11px;width:22px;height:22px;border-radius:50%;background:var(--gold);color:var(--deep);font-style:normal;font-weight:800;font-size:11px;display:grid;place-items:center}.action-grid b{font-size:11px;color:var(--navy)}.action-grid p{font-size:10.5px;line-height:1.45;color:#4d6370;margin:5px 0 0}.hotspot-action{border-top-color:#8f1725}.hotspot-action .action-heading span{color:#8f1725}.hotspot-action .action-grid i{background:#8f1725;color:#fff}.action-note{font-size:10px;color:#5b6d77;background:#f2f5f6;margin-top:10px;padding:7px 9px;border-left:3px solid #8f1725}
    .selected-panel{border-left-color:var(--gold);padding:17px 18px}.selected-panel h3{font-size:17px;margin:0 0 13px;color:var(--navy)}.selected-panel h3 span{font-size:11px;color:var(--muted);font-weight:500;display:block;margin-top:3px}.selected-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.selected-grid>div{background:#f2f6f8;padding:9px}.selected-grid b{display:block;color:var(--navy);font-size:17px}.selected-grid span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}.selected-thresholds{display:flex;gap:5px;flex-wrap:wrap;margin-top:10px}.selected-thresholds span{font-size:9px;text-transform:uppercase;letter-spacing:.35px;border-radius:11px;padding:4px 7px;border:1px solid #cfdadd;color:#71818a;background:#f4f6f7}.selected-thresholds span.on{color:#fff;background:#8f1725;border-color:#8f1725}.insight-note{background:#eaf4f4;border:1px solid #c4dfdf;padding:15px;font-size:11.5px;line-height:1.45;color:#35545b}.insight-note p{margin:5px 0 7px}.insight-note ul{margin:5px 0 0;padding-left:17px}.insight-note li{margin:3px 0}
    .main-tabs{width:1760px!important}.main-tabs .bk-tab{font-weight:700;color:var(--navy);padding:10px 24px!important}.main-tabs .bk-tab.bk-active{background:var(--teal)!important;color:#fff!important}.main-tabs .bk-header{background:#fff;border-bottom:3px solid var(--teal)!important;padding-left:28px!important}:host(.content-tab),.content-tab{width:1760px!important;background:#f4f7f9;padding:28px 42px 42px}.content-page{max-width:1420px;margin:0 auto;background:#fff;border:1px solid #dbe4e9;padding:34px 40px;box-shadow:0 4px 14px rgba(23,50,77,.06)}.content-page h2{font-size:28px;color:var(--navy);margin:0 0 20px}.content-page h3{color:var(--navy);margin-top:26px}.content-page p{font-size:14px;line-height:1.65;color:#405562}.method-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.method-grid section{background:#f4f7f9;border-top:4px solid var(--teal);padding:17px}.method-grid h3{font-size:16px;margin:0 0 8px}.method-grid p{font-size:13px;margin:0}.notice{background:#fff4d9;border-left:5px solid var(--gold);padding:15px 17px;margin:20px 0;font-size:13px;line-height:1.5}.table-wrap{max-height:520px;overflow:auto;border:1px solid #dce5ea}.data-table{width:100%;border-collapse:collapse;font-size:12px}.data-table th{position:sticky;top:0;background:var(--navy);color:#fff;text-align:left;padding:10px}.data-table td{border-bottom:1px solid #e5ebef;padding:8px 10px}.data-table tr:nth-child(even){background:#f7f9fa}.source-links a,.content-page a{color:#087d88;text-decoration:none;font-weight:600}.source-links a:hover,.content-page a:hover{text-decoration:underline}.terms-page{max-width:1080px}.terms-page p{font-size:15px}.contact-card{margin-top:28px;background:var(--navy);color:#fff;padding:22px;display:grid;grid-template-columns:1fr 1fr;gap:5px 18px}.contact-card div{grid-column:1/3;font-size:11px;letter-spacing:1.5px;color:#7fd5d8}.contact-card b{font-size:19px}.contact-card span{text-align:right}.contact-card a{grid-column:1/3;color:#fff}
    .site-footer{width:1760px;background:var(--deep);color:#d7e6ea;padding:25px 38px;display:grid;grid-template-columns:1.15fr 1.45fr .9fr;gap:34px;align-items:center;font-size:12px;border-top:5px solid var(--teal)}.site-footer>div{min-width:0}.site-footer b,.site-footer span,.site-footer small{display:block}.footer-brand b{font-size:14px;color:#fff}.footer-brand span,.footer-purpose span,.footer-contact small{color:#9eb6c1;margin-top:4px}.footer-purpose{padding-left:26px;border-left:1px solid rgba(255,255,255,.16)}.footer-purpose b{color:#d9edf0}.footer-contact{text-align:right}.footer-contact span{text-transform:uppercase;letter-spacing:.8px;font-size:9px;color:#78ccd1}.site-footer a{color:#fff;text-decoration:none;font-weight:700;font-size:13px;margin-top:3px;display:block}.site-footer a:hover{text-decoration:underline}
    .bk-input,.bk-btn{border-radius:2px!important}.bk-btn-primary{background:var(--teal)!important;border-color:var(--teal)!important}.bk-slider-title{font-weight:600!important;color:#435969!important}.bk-input-group label{font-size:11px!important;text-transform:uppercase;letter-spacing:.4px;color:#506574!important;font-weight:700!important}
    @media(max-width:1500px){body{min-width:1180px}.site-header{padding:0 30px}.hero{padding-left:34px}.overview-grid p{font-size:11px}}
    """
    shared_stylesheet = InlineStyleSheet(css=css_rules)
    for model in list(page.references()):
        if "stylesheets" in model.properties():
            model.stylesheets = [*model.stylesheets, shared_stylesheet]

    html_text = file_html(page, INLINE, "Climate Housing Exposure Index Dashboard — Harris County, TX")
    global_css = "<meta name='viewport' content='width=device-width, initial-scale=1.0'><style>" + css_rules + "</style>"
    html_text = html_text.replace("</head>", global_css + "</head>")
    boot_script = r"""
<script>
(function(){
  let tries=0;
  function boot(){
    tries+=1;
    try{
      if(window.Bokeh&&Bokeh.documents&&Bokeh.documents.length){
        const trigger=Bokeh.documents[0].get_model_by_name('dashboard_init_trigger');
        if(trigger){trigger.active=!trigger.active;return;}
      }
    }catch(e){console.error('Dashboard initialization failed',e);}
    if(tries<80)setTimeout(boot,100);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,50));
  else setTimeout(boot,50);
})();
</script>
"""
    html_text = html_text.replace("</body>", boot_script + "</body>")
    OUTPUT.write_text(html_text, encoding="utf-8")
    LEGACY_OUTPUT.write_text(html_text, encoding="utf-8")
    print(f"Wrote {OUTPUT} and {LEGACY_OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MB each)")


if __name__ == "__main__":
    build_dashboard()
