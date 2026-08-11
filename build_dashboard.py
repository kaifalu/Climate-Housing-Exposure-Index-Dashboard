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
HOTSPOT_COMBO_COLORS = {
    "None high": "#E6E9EC",
    "Hazard only": "#2B8CBE",
    "Growth only": "#F2A654",
    "SVI only": "#9A73B8",
    "Hazard + growth": "#E76445",
    "Hazard + SVI": "#6653A3",
    "Growth + SVI": "#C84D82",
    "All three high": "#8F1725",
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
    housing_grid = load_geojson("housing_grid.geojson")
    climate = pd.read_csv(DATA / "climate_points.csv")
    sf_sample = pd.read_csv(DATA / "sf_sample.csv")
    mf_points = pd.read_csv(DATA / "mf_points.csv")

    tract_xs, tract_ys = to_multipolygon_arrays(tracts.geometry)
    parcel_xs, parcel_ys = to_multipolygon_arrays(parcels.geometry)
    county_xs, county_ys = to_multipolygon_arrays(county.geometry)
    grid_xs, grid_ys = to_multipolygon_arrays(housing_grid.geometry)

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

    tract_data["fill_color"] = initial_quantile_colors(tract_data["CHEI_2050"], SEQ_BLUE)
    tract_data["display_label"] = ["Climate Housing Exposure Index, 2050"] * len(tracts)
    tract_data["display_value"] = [f"{v:.3f}" if np.isfinite(v) else "No data" for v in tract_data["CHEI_2050"]]
    tract_source = ColumnDataSource(tract_data, name="tract_source")

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
    }, name="housing_point_source")
    county_source = ColumnDataSource({"xs": county_xs, "ys": county_ys}, name="county_source")

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
    climate_renderer = map_plot.scatter(
        x="x", y="y", source=climate_display_source, marker="circle", size=8,
        fill_color="color", fill_alpha=0.90, line_color="#ffffff", line_width=0.7,
        visible=False, name="climate_points",
    )
    housing_point_renderer = map_plot.scatter(
        x="x", y="y", source=housing_point_source, marker="circle", size=3.2,
        fill_color="color", fill_alpha=0.58, line_color=None,
        visible=False, name="housing_points",
    )
    map_plot.multi_polygons(
        xs="xs", ys="ys", source=county_source, fill_alpha=0.0,
        line_color=NAVY, line_width=2.3, line_alpha=0.96, name="county_boundary",
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
        "hotspot": ["One point is assigned for each high condition; the score is noncompensatory.", "All eight combinations are retained, not only the 0–3 score classes.", "The 80th-percentile cutoffs are transparent screening conventions, not natural risk boundaries."],
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

    layer_select = Select(title="Primary map layer", value="chei_2050", options=[(k, v["label"]) for k, v in layer_meta.items()], width=CONTROL_CONTENT_WIDTH)
    gmt_select = Select(title="GMT threshold", value="25", options=[("15", "1.5°C"), ("20", "2.0°C"), ("25", "2.5°C"), ("30", "3.0°C")], width=158, visible=False)
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
    search_input = TextInput(title="Find census tract GEOID", placeholder="e.g., 48201342001", width=250)
    search_button = Button(label="Find", button_type="primary", width=75)
    reset_button = Button(label="Reset map extent", width=CONTROL_CONTENT_WIDTH)

    legend_div = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=180, css_classes=["chei-panel", "legend-panel"])
    layer_info = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=175, css_classes=["chei-panel", "info-panel"])
    overlap_summary = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=165, visible=False, css_classes=["chei-panel", "overlap-panel"])
    point_status = Div(text="", width=MAP_PLOT_WIDTH, min_height=42, css_classes=["map-status"])
    map_guide = Div(text="", width=MAP_PLOT_WIDTH, min_height=180, css_classes=["map-guide-wrapper"])
    map_actions = Div(text="", width=MAP_PLOT_WIDTH, min_height=175, css_classes=["map-actions-wrapper"])
    search_status = Div(text="", width=CONTROL_CONTENT_WIDTH, min_height=28, css_classes=["search-status"])

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
    point_status.text = '<span class="status-dot"></span>Click a census tract to update the profile panel. Use the overlap switch to screen co-exposure.'
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
const HOTSPOT_COLORS = __HOTSPOT_COLORS__;
const HOTSPOT_ORDER = __HOTSPOT_ORDER__;
const HOTSPOT_THRESHOLDS = {precip:203.603, households:746, svi:0.88386};
const LAND_COLORS = {'Residential':'#2ca25f','Commercial':'#fdae6b','Vacant Developable (includes Farming)':'#bdbdbd','Multiple':'#756bb1','Industrial':'#e6550d','Unknown':'#969696','Other':'#6baed6','Gov/Med/Edu':'#3182bd'};
const FACTOR_LABELS = {'pr_15':'GMT +1.5°C precipitation','pr_20':'GMT +2.0°C precipitation','pr_25':'GMT +2.5°C precipitation','pr_30':'GMT +3.0°C precipitation','SVI':'Social Vulnerability Index','CHEI_2050':'CHEI 2050','pop_chg':'Population growth','hh_chg':'Household growth','job_chg':'Employment growth','parcel_hu_change':'Parcel housing-unit change'};
const FACTOR_DECIMALS = {'pr_15':3,'pr_20':3,'pr_25':3,'pr_30':3,'SVI':5,'CHEI_2050':3,'pop_chg':0,'hh_chg':0,'job_chg':0,'parcel_hu_change':0};
function finiteValues(arr){return Array.from(arr).filter(v=>Number.isFinite(Number(v))).map(Number);}
function quantile(arr,q){const a=finiteValues(arr).sort((x,y)=>x-y);if(!a.length)return NaN;const p=(a.length-1)*q,l=Math.floor(p),h=Math.ceil(p);return l===h?a[l]:a[l]+(a[h]-a[l])*(p-l);}
function fmt(v,d=0){const n=Number(v);if(!Number.isFinite(n))return 'No data';return n.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});}
function esc(s){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function titleOf(meta){return meta.label.split('•').pop().trim();}
function sequential(arr,palette){const b=[quantile(arr,.2),quantile(arr,.4),quantile(arr,.6),quantile(arr,.8)];const colors=Array.from(arr).map(v=>{const n=Number(v);if(!Number.isFinite(n))return '#d9d9d9';let i=0;while(i<b.length&&n>b[i])i++;return palette[i];});return {colors:colors,breaks:b};}
function diverging(arr){const av=finiteValues(arr).map(Math.abs),lim=Math.max(quantile(av,.95),1e-9);const colors=Array.from(arr).map(v=>{const n=Number(v);if(!Number.isFinite(n))return '#d9d9d9';if(n<=-lim/2)return DIVERGING[0];if(n<0)return DIVERGING[1];if(n===0)return DIVERGING[2];if(n<lim/2)return DIVERGING[3];return DIVERGING[4];});return {colors:colors,lim:lim};}
function setAllInvisible(){parcel_renderer.visible=false;climate_renderer.visible=false;grid_renderer.visible=false;housing_renderer.visible=false;kr15.visible=false;kr20.visible=false;kr25.visible=false;kr30.visible=false;}
function legendSequential(label,unit,breaks,palette,decimals){const lows=[-Infinity,...breaks],highs=[...breaks,Infinity];let rows='';for(let i=0;i<palette.length;i++){let txt='';if(i===0)txt='≤ '+fmt(highs[i],decimals);else if(i===palette.length-1)txt='> '+fmt(lows[i],decimals);else txt=fmt(lows[i],decimals)+' – '+fmt(highs[i],decimals);rows+=`<div class='legend-row'><span style='background:${palette[i]}'></span><b>${txt}</b></div>`;}return `<div class='panel-eyebrow'>MAP LEGEND</div><h4>${esc(label)}</h4>${rows}<div class='legend-unit'>${esc(unit||'')}</div>`;}
function legendHotspot(arr){const counts={};HOTSPOT_ORDER.forEach(k=>counts[k]=0);Array.from(arr).forEach(v=>counts[v]=(counts[v]||0)+1);const rows=HOTSPOT_ORDER.map(k=>`<div class='legend-row hotspot-row'><span style='background:${HOTSPOT_COLORS[k]}'></span><b>${esc(k)}</b><em>${fmt(counts[k])}</em></div>`).join('');return `<div class='panel-eyebrow'>MAP LEGEND</div><h4>Compound-hotspot typology</h4><div class='threshold-card'><div class='threshold-kicker'>HIGH = COUNTY 80TH PERCENTILE OR ABOVE</div><div><b>Extreme precipitation</b><span>≥ 203.603 mm at GMT +2.5°C</span></div><div><b>Household growth</b><span>≥ 746 households, 2020–2050</span></div><div><b>Social vulnerability</b><span>SVI ≥ 0.88386</span></div></div><div class='legend-subtitle'>CONDITION COMBINATION · TRACT COUNT</div>${rows}`;}
function layerInfoHTML(meta){const bullets=(meta.bullets||[]).map(x=>`<li>${esc(x)}</li>`).join('');return `<div class='panel-eyebrow'>ABOUT THIS LAYER</div><h4>${esc(titleOf(meta))}</h4><p>${esc(meta.description)}</p><ul class='layer-bullets'>${bullets}</ul>`;}
function mapGuideHTML(meta){const b=meta.bullets||[];return `<div class='map-guide'><div class='guide-heading'><span>READING THE CURRENT LAYER</span><h3>${esc(titleOf(meta))}</h3></div><div class='guide-grid'><div><b>Scope</b><p>${esc(b[0]||meta.description)}</p></div><div><b>Interpretation</b><p>${esc(b[1]||'Compare values and patterns across Harris County.')}</p></div><div><b>Planning use</b><p>${esc(b[2]||'Use as an exploratory screening layer and verify with authoritative local data.')}</p></div></div></div>`;}
function actionHTML(meta,id){if(id==='hotspot')return `<div class='action-panel hotspot-action'><div class='action-heading'><span>FROM TYPOLOGY TO PRIORITY</span><h3>Use combinations to distinguish planning needs</h3></div><div class='action-grid'><div><i>1</i><b>Corrective review</b><p>Hazard and SVI combinations can flag existing exposure and vulnerability.</p></div><div><i>2</i><b>Preventive review</b><p>Growth combinations can flag future development pressure before build-out.</p></div><div><i>3</i><b>Coordinated action</b><p>All-three-high tracts warrant integrated climate, housing, and equity review.</p></div></div><div class='action-note'>The thresholds are transparent screening conventions rather than natural discontinuities in risk.</div></div>`;return `<div class='action-panel'><div class='action-heading'><span>FROM MAP TO USE</span><h3>A three-step exploratory workflow</h3></div><div class='action-grid'><div><i>1</i><b>Screen</b><p>Locate tracts, parcels, points, or cells with higher relative values.</p></div><div><i>2</i><b>Diagnose</b><p>Hover and select features; compare the mapped pattern with related layers.</p></div><div><i>3</i><b>Validate</b><p>Confirm modeled or projected findings with authoritative local data before action.</p></div></div></div>`;}
function updateHistogram(arr,label,color,decimals){const a=finiteValues(arr);hist_plot.visible=true;if(!a.length){hist_plot.visible=false;hist_summary.text='<p>No numeric distribution is available for this layer.</p>';return;}const min=Math.min(...a),max=Math.max(...a),bins=12,width=(max-min||1)/bins,counts=new Array(bins).fill(0);for(const v of a){let i=Math.floor((v-min)/width);if(i>=bins)i=bins-1;if(i<0)i=0;counts[i]++;}const left=[],right=[];for(let i=0;i<bins;i++){left.push(min+i*width);right.push(min+(i+1)*width);}hist_source.data={left:left,right:right,top:counts,color:new Array(bins).fill(color)};hist_source.change.emit();hist_plot.title.text='Distribution · '+fmt(a.length,0)+' features';hist_xaxis.axis_label=label;hist_summary.text=`<p><strong>Median:</strong> ${fmt(quantile(a,.5),decimals)}<br><strong>Range:</strong> ${fmt(min,decimals)} to ${fmt(max,decimals)}</p>`;}
function sampleHousing(){const mode=housing_select.value,s=housing_sample.data,sx=(s.sf_x&&s.sf_x.length)?Array.from(s.sf_x[0]):[],sy=(s.sf_y&&s.sf_y.length)?Array.from(s.sf_y[0]):[],mx=(s.mf_x&&s.mf_x.length)?Array.from(s.mf_x[0]):[],my=(s.mf_y&&s.mf_y.length)?Array.from(s.mf_y[0]):[];let x=[],y=[],color=[],kind=[];if(mode==='single'||mode==='combined'){x=x.concat(sx);y=y.concat(sy);color=color.concat(new Array(sx.length).fill('#168C95'));kind=kind.concat(new Array(sx.length).fill('Single-family'));}if(mode==='multi'||mode==='combined'){x=x.concat(mx);y=y.concat(my);color=color.concat(new Array(mx.length).fill('#F16913'));kind=kind.concat(new Array(mx.length).fill('Multi-family'));}housing_point_source.data={x:x,y:y,color:color,kind:kind};housing_point_source.change.emit();point_status.text=`<span class='status-dot'></span>Standalone preview: displaying ${fmt(x.length,0)} points. Start <code>server.py</code> for viewport queries against all source points.`;}
function requestHousingPoints(){if(layer_select.value!=='housing_points')return;if(window.location.protocol==='file:'||window.location.protocol==='about:'||window.location.protocol==='sandbox:'||!window.fetch){sampleHousing();return;}const xmin=map_plot.x_range.start,xmax=map_plot.x_range.end,ymin=map_plot.y_range.start,ymax=map_plot.y_range.end,url=`/api/housing-points?housing_type=${encodeURIComponent(housing_select.value)}&xmin=${xmin}&xmax=${xmax}&ymin=${ymin}&ymax=${ymax}&max_points=50000`;point_status.text='<span class="status-dot loading"></span>Loading housing-stock points for the current viewport…';fetch(url).then(r=>{if(!r.ok)throw new Error(r.statusText);return r.json();}).then(d=>{housing_point_source.data={x:d.x,y:d.y,color:d.color,kind:d.kind};housing_point_source.change.emit();point_status.text=`<span class='status-dot'></span>Displaying ${fmt(d.n_returned,0)} of ${fmt(d.n_total,0)} source points in the current viewport.`;}).catch(()=>sampleHousing());}
function applyOverlap(){const d=tract_source.data,a=Array.from(d[overlap_a.value]),b=Array.from(d[overlap_b.value]),q=threshold_slider.value/100,ta=quantile(a,q),tb=quantile(b,q),colors=[],labels=[],counts=[0,0,0,0];let bothPop=0,bothHH=0,bothJobs=0;const la=FACTOR_LABELS[overlap_a.value]||overlap_a.value,lb=FACTOR_LABELS[overlap_b.value]||overlap_b.value,da=FACTOR_DECIMALS[overlap_a.value]??2,db=FACTOR_DECIMALS[overlap_b.value]??2;for(let i=0;i<a.length;i++){const ah=Number(a[i])>=ta,bh=Number(b[i])>=tb,c=(ah?1:0)+(bh?2:0);colors.push(BIVARIATE[c]);counts[c]++;labels.push(['Neither high',`${la} high`,`${lb} high`,'Both high'][c]);if(c===3){bothPop+=Number(d.hp_2050[i])||0;bothHH+=Number(d.hh_2050[i])||0;bothJobs+=Number(d.j_2050[i])||0;}}d.fill_color=colors;d.display_label=new Array(a.length).fill('High–high overlap class');d.display_value=labels;tract_source.change.emit();legend_div.text=`<div class='panel-eyebrow'>MAP LEGEND</div><h4>Bivariate high-value overlap</h4><div class='threshold-card compact'><div class='threshold-kicker'>${fmt(threshold_slider.value)}TH-PERCENTILE CUTOFFS</div><div><b>${esc(la)}</b><span>High at ≥ ${fmt(ta,da)}</span></div><div><b>${esc(lb)}</b><span>High at ≥ ${fmt(tb,db)}</span></div></div><div class='legend-row'><span style='background:${BIVARIATE[0]}'></span><b>Neither high</b><em>${fmt(counts[0])}</em></div><div class='legend-row'><span style='background:${BIVARIATE[1]}'></span><b>${esc(la)} only</b><em>${fmt(counts[1])}</em></div><div class='legend-row'><span style='background:${BIVARIATE[2]}'></span><b>${esc(lb)} only</b><em>${fmt(counts[2])}</em></div><div class='legend-row'><span style='background:${BIVARIATE[3]}'></span><b>Both high</b><em>${fmt(counts[3])}</em></div>`;overlap_summary.text=`<div class='panel-eyebrow'>BOTH HIGH</div><h4>${fmt(counts[3])} census tracts</h4><p><b>${fmt(bothPop)}</b> projected residents<br><b>${fmt(bothHH)}</b> projected households<br><b>${fmt(bothJobs)}</b> projected jobs</p><div class='legend-unit'>Cutoffs: ${esc(la)} ≥ ${fmt(ta,da)} · ${esc(lb)} ≥ ${fmt(tb,db)}</div>`;hist_plot.visible=false;hist_summary.text='<p>Overlap mode compares two factors; numeric cutoffs are shown in the legend.</p>';layer_info.text=`<div class='panel-eyebrow'>ABOUT THIS VIEW</div><h4>Transparent overlap screening</h4><p>Each factor is compared with its own countywide percentile cutoff.</p><ul class='layer-bullets'><li>The darkest class is high on both selected factors.</li><li>Actual cutoff values update whenever the percentile or factor changes.</li><li>This is an exploratory screen, not a causal or regulatory classification.</li></ul>`;map_guide.text=`<div class='map-guide'><div class='guide-heading'><span>READING THE OVERLAP VIEW</span><h3>${esc(la)} × ${esc(lb)}</h3></div><div class='guide-grid'><div><b>Factor A cutoff</b><p>${esc(la)} is high at ${fmt(ta,da)} or above.</p></div><div><b>Factor B cutoff</b><p>${esc(lb)} is high at ${fmt(tb,db)} or above.</p></div><div><b>Interpretation</b><p>Darkest tracts meet both cutoffs and may warrant coordinated review.</p></div></div></div>`;map_actions.text=`<div class='action-panel'><div class='action-heading'><span>USING THE OVERLAP SCREEN</span><h3>Test sensitivity before prioritizing</h3></div><div class='action-grid'><div><i>1</i><b>Compare</b><p>Change factors to examine different forms of co-exposure.</p></div><div><i>2</i><b>Test</b><p>Move the percentile threshold to assess classification sensitivity.</p></div><div><i>3</i><b>Validate</b><p>Review both-high tracts with local evidence and stakeholder knowledge.</p></div></div></div>`;point_status.text='<span class="status-dot"></span>Overlap screening is active. Change factors or the percentile threshold to test alternatives.';}
function updateLayer(){setAllInvisible();const active=overlap_toggle.active;layer_select.disabled=active;overlap_a.visible=active;overlap_b.visible=active;threshold_slider.visible=active;overlap_summary.visible=active;gmt_select.visible=!active&&['pr_tract','pr_points','pr_kriging'].includes(layer_select.value);housing_select.visible=!active&&['housing_density','housing_points'].includes(layer_select.value);const opacity=opacity_slider.value;tract_renderer.glyph.fill_alpha=opacity;tract_renderer.nonselection_glyph.fill_alpha=opacity;parcel_renderer.glyph.fill_alpha=opacity;grid_renderer.glyph.fill_alpha=opacity;climate_renderer.glyph.fill_alpha=opacity;housing_renderer.glyph.fill_alpha=Math.min(opacity,.72);kr15.glyph.global_alpha=opacity;kr20.glyph.global_alpha=opacity;kr25.glyph.global_alpha=opacity;kr30.glyph.global_alpha=opacity;tract_renderer.visible=true;tract_renderer.glyph.line_alpha=.75;tract_renderer.glyph.line_width=.55;if(active){applyOverlap();return;}const id=layer_select.value,meta=META[id],d=tract_source.data;let field=meta.field,arr=null,result=null;if(id==='pr_tract'||id==='pr_kriging')field='pr_'+gmt_select.value;if(meta.source==='tract'){arr=Array.from(d[field]);if(meta.kind==='seq')result=sequential(arr,meta.palette);else if(meta.kind==='div')result=diverging(arr);else if(meta.kind==='cat_hotspot')result={colors:arr.map(v=>HOTSPOT_COLORS[v]||'#d9d9d9')};d.fill_color=result.colors;d.display_label=new Array(arr.length).fill(titleOf(meta));d.display_value=arr.map(v=>(meta.kind==='cat_hotspot')?String(v):fmt(v,meta.decimals));tract_source.change.emit();if(meta.kind==='seq'){legend_div.text=legendSequential(titleOf(meta),meta.unit,result.breaks,meta.palette,meta.decimals);updateHistogram(arr,meta.short,meta.palette[3],meta.decimals);}else if(meta.kind==='div'){legend_div.text=`<div class='panel-eyebrow'>MAP LEGEND</div><h4>${esc(titleOf(meta))}</h4><div class='legend-row'><span style='background:${DIVERGING[0]}'></span><b>Large decrease</b></div><div class='legend-row'><span style='background:${DIVERGING[1]}'></span><b>Decrease</b></div><div class='legend-row'><span style='background:${DIVERGING[2]}'></span><b>Near zero</b></div><div class='legend-row'><span style='background:${DIVERGING[3]}'></span><b>Increase</b></div><div class='legend-row'><span style='background:${DIVERGING[4]}'></span><b>Large increase</b></div><div class='legend-unit'>${esc(meta.unit||'')}</div>`;updateHistogram(arr,meta.short,DIVERGING[4],meta.decimals);}else{legend_div.text=legendHotspot(arr);hist_plot.visible=false;hist_summary.text='<p><strong>Noncompensatory typology:</strong> every tract is assigned to one of eight condition combinations. The legend reports tract counts and exact high-value thresholds.</p>';}}else if(meta.source==='parcel'){parcel_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.30;const p=parcel_source.data;arr=Array.from(p[field]);if(meta.kind==='seq'){result=sequential(arr,meta.palette);p.fill_color=result.colors;p.display_value=arr.map(v=>fmt(v,meta.decimals));legend_div.text=legendSequential(titleOf(meta),meta.unit,result.breaks,meta.palette,meta.decimals);updateHistogram(arr,meta.short,meta.palette[3],meta.decimals);}else{p.fill_color=arr.map(v=>LAND_COLORS[v]||'#969696');p.display_value=arr.map(String);const cats={};arr.forEach(v=>cats[v]=(cats[v]||0)+1);legend_div.text=`<div class='panel-eyebrow'>MAP LEGEND</div><h4>${esc(titleOf(meta))}</h4>`+Object.entries(cats).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([k,n])=>`<div class='legend-row'><span style='background:${LAND_COLORS[k]||'#969696'}'></span><b>${esc(k)}</b><em>${fmt(n)}</em></div>`).join('');hist_plot.visible=false;hist_summary.text='<p>Categorical parcel layer; feature counts are shown in the legend.</p>';}parcel_source.change.emit();}else if(meta.source==='grid'){grid_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.28;const gd=grid_source.data;field=housing_select.value==='single'?'sf_count':housing_select.value==='multi'?'mf_count':'total_count';arr=Array.from(gd[field]);result=sequential(arr,meta.palette);gd.fill_color=result.colors;gd.display_value=arr.map(v=>fmt(v,0));grid_source.change.emit();legend_div.text=legendSequential((housing_select.value==='single'?'Single-family':housing_select.value==='multi'?'Multi-family':'Combined')+' housing-stock density','records per 1 km cell',result.breaks,meta.palette,0);updateHistogram(arr,'Housing records per cell',meta.palette[3],0);}else if(meta.source==='climate_points'){climate_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.30;const cm=climate_source.data,g=Number(gmt_select.value)/10,x=[],y=[],v=[];for(let i=0;i<cm.gmt.length;i++)if(Number(cm.gmt[i])===g){x.push(cm.x[i]);y.push(cm.y[i]);v.push(cm.precip[i]);}result=sequential(v,meta.palette);climate_display_source.data={x:x,y:y,gmt:new Array(x.length).fill(g),precip:v,color:result.colors};climate_display_source.change.emit();legend_div.text=legendSequential(`GMT ${g.toFixed(1)}°C climate points`,meta.unit,result.breaks,meta.palette,meta.decimals);updateHistogram(v,'3-day precipitation (mm)',meta.palette[3],1);}else if(meta.source==='kriging'){tract_renderer.glyph.fill_alpha=0;tract_renderer.nonselection_glyph.fill_alpha=0;tract_renderer.glyph.line_alpha=.50;tract_renderer.glyph.line_width=.40;const code=gmt_select.value;({'15':kr15,'20':kr20,'25':kr25,'30':kr30})[code].visible=true;const arr2=Array.from(d['pr_'+code]),r=sequential(arr2,meta.palette);legend_div.text=legendSequential(`GMT ${(Number(code)/10).toFixed(1)}°C kriging surface`,'mm',r.breaks,meta.palette,1);updateHistogram(arr2,'Tract precipitation (mm)',meta.palette[3],1);}else if(meta.source==='housing_points'){housing_renderer.visible=true;tract_renderer.glyph.fill_alpha=.01;tract_renderer.nonselection_glyph.fill_alpha=.01;tract_renderer.glyph.line_alpha=.24;legend_div.text=`<div class='panel-eyebrow'>MAP LEGEND</div><h4>Housing-stock locations</h4><div class='legend-row'><span style='background:#168C95'></span><b>Single-family</b></div><div class='legend-row'><span style='background:#F16913'></span><b>Multi-family</b></div>`;hist_plot.visible=false;hist_summary.text='<p>Point display is optimized by viewport. The density layer uses every uploaded record.</p>';requestHousingPoints();}layer_info.text=layerInfoHTML(meta);map_guide.text=mapGuideHTML(meta);map_actions.text=actionHTML(meta,id);if(meta.source!=='housing_points')point_status.text='<span class="status-dot"></span>Click a census tract to update the profile panel. Use the overlap switch to screen co-exposure.';}
updateLayer();
"""
    callback_code = (callback_code
        .replace("__META__", json.dumps(layer_meta))
        .replace("__SEQ_BLUE__", json.dumps(SEQ_BLUE))
        .replace("__DIVERGING__", json.dumps(DIVERGING))
        .replace("__BIVARIATE__", json.dumps(BIVARIATE))
        .replace("__HOTSPOT_COLORS__", json.dumps(HOTSPOT_COMBO_COLORS))
        .replace("__HOTSPOT_ORDER__", json.dumps(HOTSPOT_ORDER)))

    callback_args = dict(
        tract_source=tract_source, parcel_source=parcel_source, climate_source=climate_source,
        climate_display_source=climate_display_source, grid_source=grid_source,
        housing_sample=housing_sample_source, housing_point_source=housing_point_source,
        tract_renderer=tract_renderer, parcel_renderer=parcel_renderer, climate_renderer=climate_renderer,
        grid_renderer=grid_renderer, housing_renderer=housing_point_renderer,
        kr15=kriging_renderers["15"], kr20=kriging_renderers["20"], kr25=kriging_renderers["25"], kr30=kriging_renderers["30"],
        layer_select=layer_select, gmt_select=gmt_select, housing_select=housing_select,
        opacity_slider=opacity_slider, overlap_toggle=overlap_toggle, overlap_a=overlap_a,
        overlap_b=overlap_b, threshold_slider=threshold_slider, legend_div=legend_div,
        layer_info=layer_info, overlap_summary=overlap_summary, map_guide=map_guide,
        map_actions=map_actions, hist_source=hist_source, hist_plot=hist_plot, hist_xaxis=hist_plot.xaxis[0], hist_summary=hist_summary,
        point_status=point_status, map_plot=map_plot,
    )
    update_callback = CustomJS(args=callback_args, code=callback_code)
    for widget, prop in [
        (layer_select, "value"), (gmt_select, "value"), (housing_select, "value"),
        (opacity_slider, "value_throttled"), (overlap_toggle, "active"),
        (overlap_a, "value"), (overlap_b, "value"), (threshold_slider, "value_throttled"),
    ]:
        widget.js_on_change(prop, update_callback)

    range_callback = CustomJS(args=callback_args, code=r"""
if(window.__chei_point_timer)clearTimeout(window.__chei_point_timer);
window.__chei_point_timer=setTimeout(()=>{if(layer_select.value!=='housing_points'||window.location.protocol==='file:'||window.location.protocol==='about:'||window.location.protocol==='sandbox:'||!window.fetch)return;const xmin=map_plot.x_range.start,xmax=map_plot.x_range.end,ymin=map_plot.y_range.start,ymax=map_plot.y_range.end,url=`/api/housing-points?housing_type=${encodeURIComponent(housing_select.value)}&xmin=${xmin}&xmax=${xmax}&ymin=${ymin}&ymax=${ymax}&max_points=50000`;point_status.text='<span class="status-dot loading"></span>Refreshing housing-stock points for the current viewport…';fetch(url).then(r=>r.json()).then(d=>{housing_point_source.data={x:d.x,y:d.y,color:d.color,kind:d.kind};housing_point_source.change.emit();point_status.text=`<span class='status-dot'></span>Displaying ${d.n_returned.toLocaleString()} of ${d.n_total.toLocaleString()} source points in the current viewport.`;}).catch(()=>{});},350);
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
        xr=map_plot.x_range, yr=map_plot.y_range,
    ), code=r"""
const q=String(text.value||'').trim(),d=source.data;let idx=-1;for(let i=0;i<d.GEOID.length;i++){if(String(d.GEOID[i])===q){idx=i;break;}}if(idx<0){status.text='<span class="error-text">No exact GEOID match was found.</span>';return;}source.selected.indices=[idx];source.selected.change.emit();const px=Math.max((d.bbox_maxx[idx]-d.bbox_minx[idx])*.35,2000),py=Math.max((d.bbox_maxy[idx]-d.bbox_miny[idx])*.35,2000);xr.start=d.bbox_minx[idx]-px;xr.end=d.bbox_maxx[idx]+px;yr.start=d.bbox_miny[idx]-py;yr.end=d.bbox_maxy[idx]+py;status.text='<span class="success-text">Tract located and selected.</span>';
""")
    search_button.js_on_click(search_callback)
    search_input.js_on_event("value_submit", search_callback)
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
          <article><div class='overview-number'>02</div><h3>Key Functions</h3><p>Explore extreme precipitation under 1.5°C, 2.0°C, 2.5°C, and 3.0°C warming scenarios; compare 2020 and 2050 conditions; and examine CHEI, housing stocks, land use, growth, and compound hotspots.</p></article>
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
        Div(text="<div class='section-title'><span>01</span> Explore layers</div>", width=CONTROL_CONTENT_WIDTH),
        layer_select, row(gmt_select, housing_select, width=CONTROL_CONTENT_WIDTH), opacity_slider,
        Div(text="<div class='section-title top-space'><span>02</span> Screen overlap</div>", width=CONTROL_CONTENT_WIDTH),
        overlap_toggle, overlap_a, overlap_b, threshold_slider, overlap_summary,
        Div(text="<div class='section-title top-space'><span>03</span> Locate a tract</div>", width=CONTROL_CONTENT_WIDTH),
        row(search_input, search_button, width=CONTROL_CONTENT_WIDTH), search_status, reset_button,
        legend_div, layer_info, hist_plot, hist_summary,
        width=CONTROL_COLUMN_WIDTH, css_classes=["controls-column"],
    )
    map_column = column(map_plot, point_status, map_guide, map_actions, width=MAP_COLUMN_WIDTH, css_classes=["map-column"])
    insights = column(
        selected_div, climate_profile, profile_plot,
        Div(text="<div class='insight-note'><b>Interpretation reminder</b><p>This dashboard supports screening and exploration. Modeled and projected values should be validated with authoritative local data before decisions are made.</p><ul><li>Hover for feature values.</li><li>Click a tract for its profile.</li><li>Use overlap mode to test co-exposure.</li></ul></div>", width=INSIGHT_CONTENT_WIDTH),
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
        <section><h3>Compound hotspots and overlap</h3><p>The compound-hotspot typology is noncompensatory and retains all eight combinations generated by three countywide 80th-percentile conditions: GMT +2.5°C precipitation ≥ 203.603 mm, household growth ≥ 746, and SVI ≥ 0.88386. A separate bivariate tool lets users select two factors and test alternative percentile cutoffs.</p></section>
      </div>
      <div class='notice'><b>Data audit.</b> The geodatabase contains {report['available_vector_layers']} exposed vector layers. The two CHEI 2050 feature classes have identical index values and are consolidated. The supplied tract precipitation inventory uses “extreme_precipi,” whereas the actual GDB layer names use “extreme_precip.”</div>
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
    .chei-panel{background:#fff;border:1px solid #d8e2e8;border-left:4px solid var(--teal);padding:14px 16px;margin-top:9px;box-shadow:0 2px 6px rgba(23,50,77,.035);overflow:visible!important}.chei-panel h4{font-size:13px;line-height:1.35;margin:0 0 10px;color:var(--navy)}.chei-panel p{font-size:11.5px;line-height:1.5;margin:6px 0;color:#465a68}.legend-row{display:grid;grid-template-columns:27px minmax(0,1fr) auto;align-items:center;column-gap:9px;font-size:11px;margin:6px 0;min-height:15px}.legend-row span{width:27px;height:14px;border:1px solid rgba(0,0,0,.13);display:block}.legend-row b{font-weight:700;line-height:1.25;min-width:0}.legend-row em{font-style:normal;color:#627581;font-weight:700}.legend-unit{font-size:10px;color:var(--muted);margin-top:9px;text-transform:uppercase;letter-spacing:.7px}.legend-subtitle{font-size:9.5px;color:#607786;font-weight:800;letter-spacing:.75px;margin:14px 0 7px}.threshold-card{background:#f1f6f7;border:1px solid #d4e3e6;padding:10px 11px;margin:7px 0 12px}.threshold-card>div:not(.threshold-kicker){display:grid;grid-template-columns:1fr;gap:2px;padding:6px 0;border-bottom:1px solid #dce7ea}.threshold-card>div:last-child{border-bottom:0}.threshold-card b{font-size:10.5px;color:var(--navy)}.threshold-card span{font-size:10.5px;color:#4f6674}.threshold-kicker{font-size:9px;font-weight:800;letter-spacing:.65px;color:#087d88;margin-bottom:3px}.threshold-card.compact{margin-bottom:10px}.hotspot-row{margin:5px 0}.layer-bullets{margin:10px 0 2px;padding-left:17px;color:#405664}.layer-bullets li{font-size:11px;line-height:1.45;margin:5px 0}.overlap-panel{border-left-color:#354a8c}.hist-summary{background:#fff;border:1px solid #d8e2e8;border-top:0;padding:5px 10px 7px}.hist-summary p{font-size:10.5px;line-height:1.45;color:var(--muted);margin:3px 0}.search-status{font-size:11px;padding:3px 1px}.success-text{color:#168c60}.error-text{color:#b2182b}
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
    OUTPUT.write_text(html_text, encoding="utf-8")
    LEGACY_OUTPUT.write_text(html_text, encoding="utf-8")
    print(f"Wrote {OUTPUT} and {LEGACY_OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MB each)")


if __name__ == "__main__":
    build_dashboard()
