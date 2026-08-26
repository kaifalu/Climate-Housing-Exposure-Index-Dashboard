#!/usr/bin/env python3
"""Prepare web-ready assets for the Harris County Climate Housing Exposure dashboard.

The script reads the uploaded Esri File Geodatabase, consolidates tract metrics,
prepares simplified parcel, tract, county, ZIP-code, and commissioner-precinct geometry, builds a complete
housing density grid, stores point arrays for viewport queries, and derives
ordinary-kriging surfaces when the four named GDB kriging rasters are
unavailable to the open-source FileGDB reader.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
from matplotlib import colormaps
from matplotlib.colors import Normalize
from scipy.optimize import curve_fit
from scipy.spatial.distance import cdist, pdist, squareform
from shapely.geometry import box

DEFAULT_GDB = Path("/mnt/data/chei_work/Climate_Housing_Exposure_Index_Dashboard.gdb")
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data"
GMT_CODES = {"15": 1.5, "20": 2.0, "25": 2.5, "30": 3.0}


def read_layer(gdb: Path, layer: str, columns: list[str] | None = None) -> gpd.GeoDataFrame:
    return pyogrio.read_dataframe(gdb, layer=layer, columns=columns)


def ensure_geoid_text(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if "GEOID" in out:
        out["GEOID"] = out["GEOID"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(11)
    return out


def join_fields(base: gpd.GeoDataFrame, other: gpd.GeoDataFrame, fields: Iterable[str]) -> gpd.GeoDataFrame:
    cols = ["GEOID"] + [f for f in fields if f in other.columns]
    rhs = ensure_geoid_text(other[cols].copy()).drop_duplicates("GEOID")
    return base.merge(rhs, on="GEOID", how="left", suffixes=("", "_joined"))


def exponential_variogram(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
    return nugget + sill * (1.0 - np.exp(-h / np.maximum(range_, 1e-9)))


def fit_variogram(xy: np.ndarray, z: np.ndarray) -> dict[str, float]:
    distances = pdist(xy)
    semivar = 0.5 * pdist(z[:, None], metric="sqeuclidean")
    positive = distances > 0
    distances, semivar = distances[positive], semivar[positive]
    max_d = float(np.quantile(distances, 0.90))
    edges = np.linspace(0, max_d, 15)
    centers, values = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (distances >= lo) & (distances < hi)
        if mask.sum() >= 8:
            centers.append(float(np.mean(distances[mask])))
            values.append(float(np.mean(semivar[mask])))
    centers_arr = np.asarray(centers)
    values_arr = np.asarray(values)
    variance = float(np.var(z))
    p0 = [max(float(values_arr.min()) * 0.10, 0.0), max(variance, 1e-6), max_d / 3.0]
    bounds = ([0.0, 1e-9, max_d / 100.0], [max(variance * 2, 1.0), max(variance * 5, 1.0), max_d * 3.0])
    try:
        pars, _ = curve_fit(exponential_variogram, centers_arr, values_arr, p0=p0, bounds=bounds, maxfev=20000)
    except Exception:
        pars = np.asarray(p0)
    return {"nugget": float(pars[0]), "sill": float(pars[1]), "range": float(pars[2]), "max_fit_distance": max_d}


def ordinary_kriging_grid(
    xy: np.ndarray,
    z: np.ndarray,
    bounds: tuple[float, float, float, float],
    county_geom,
    nx: int = 220,
    ny: int = 170,
) -> tuple[np.ndarray, dict[str, float]]:
    params = fit_variogram(xy, z)
    minx, miny, maxx, maxy = bounds
    gx = np.linspace(minx, maxx, nx)
    gy = np.linspace(miny, maxy, ny)
    xx, yy = np.meshgrid(gx, gy)
    targets = np.column_stack([xx.ravel(), yy.ravel()])

    gamma_pp = exponential_variogram(squareform(pdist(xy)), params["nugget"], params["sill"], params["range"])
    np.fill_diagonal(gamma_pp, 0.0)
    n = len(xy)
    system = np.zeros((n + 1, n + 1), dtype=float)
    system[:n, :n] = gamma_pp
    system[:n, n] = 1.0
    system[n, :n] = 1.0
    inverse = np.linalg.pinv(system, rcond=1e-10)

    estimates = np.empty(len(targets), dtype=float)
    chunk = 6000
    for start in range(0, len(targets), chunk):
        t = targets[start : start + chunk]
        rhs = np.vstack([
            exponential_variogram(cdist(xy, t), params["nugget"], params["sill"], params["range"]),
            np.ones((1, len(t))),
        ])
        weights = inverse @ rhs
        estimates[start : start + len(t)] = z @ weights[:n, :]
    values = estimates.reshape(ny, nx)

    # Mask grid-cell centers outside Harris County.
    points = gpd.GeoSeries(gpd.points_from_xy(xx.ravel(), yy.ravel()), crs="EPSG:3857")
    inside = points.within(county_geom).to_numpy().reshape(ny, nx)
    values[~inside] = np.nan
    params.update({"nx": nx, "ny": ny, "minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy})
    return values, params


def rgba_from_values(values: np.ndarray) -> np.ndarray:
    finite = values[np.isfinite(values)]
    low, high = np.quantile(finite, [0.02, 0.98])
    norm = Normalize(vmin=float(low), vmax=float(high), clip=True)
    rgba = (colormaps["Blues"](norm(np.nan_to_num(values, nan=low))) * 255).astype(np.uint8)
    rgba[..., 3] = np.where(np.isfinite(values), 225, 0).astype(np.uint8)
    packed = (
        rgba[..., 0].astype(np.uint32)
        | (rgba[..., 1].astype(np.uint32) << 8)
        | (rgba[..., 2].astype(np.uint32) << 16)
        | (rgba[..., 3].astype(np.uint32) << 24)
    )
    # The grid y coordinates are ascending, so NumPy row 0 already represents
    # the lower edge expected by Bokeh image_rgba.
    return packed


def save_surface_png(values: np.ndarray, bounds: tuple[float, float, float, float], out: Path, gmt: float) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    im = ax.imshow(values, extent=bounds, origin="lower", cmap="Blues")
    ax.set_axis_off()
    cb = fig.colorbar(im, ax=ax, shrink=0.88)
    cb.set_label("Average 3-day extreme precipitation sum (mm)")
    ax.set_title(f"Derived ordinary-kriging precipitation surface: GMT +{gmt:.1f}°C")
    fig.tight_layout()
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gdb", type=Path, default=DEFAULT_GDB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sf-sample", type=int, default=30000)
    args = parser.parse_args()
    gdb = args.gdb.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    layer_rows = []
    for layer, geometry_type in pyogrio.list_layers(gdb):
        info = pyogrio.read_info(gdb, layer=layer)
        layer_rows.append({
            "gdb_layer": layer,
            "feature_count": int(info["features"]),
            "geometry_type": geometry_type,
            "crs": str(info.get("crs") or ""),
        })
    inventory = pd.DataFrame(layer_rows)
    inventory.to_csv(out / "gdb_layer_inventory.csv", index=False)

    # Consolidated tract layer.
    base_fields = [
        "GEOID", "NAME", "LOCATION", "pop_den", "n_single_f", "n_multi_fa",
        "hh_2020", "hh_2050", "hp_2020", "hp_2050", "j_2020", "j_2050",
    ]
    tracts = ensure_geoid_text(read_layer(gdb, "harris_census_tract_employment_proj_2050", base_fields))
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_CHEI_2050", ["GEOID", "CHEI_2020", "CHEI_2050", "adapt_gap"]), ["CHEI_2020", "CHEI_2050", "adapt_gap"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_social_vulnerability_index_2020", ["GEOID", "SVI"]), ["SVI"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_extreme_precip_gmt_30", ["GEOID", "pr_15", "pr_20", "pr_25", "pr_30"]), ["pr_15", "pr_20", "pr_25", "pr_30"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_extreme_precip_gmt_25_vs_15", ["GEOID", "delta_mm", "sens_pct"]), ["delta_mm", "sens_pct"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_compound_climate_inequality_hotspots_2050", ["GEOID", "hotspot_sc", "hotspot_ca"]), ["hotspot_sc", "hotspot_ca"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_population_growth_2020_2050", ["GEOID", "pop_chg"]), ["pop_chg"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_household_growth_2020_2050", ["GEOID", "hh_chg"]), ["hh_chg"])
    tracts = join_fields(tracts, read_layer(gdb, "harris_census_tract_employment_growth_2020_2050", ["GEOID", "job_chg"]), ["job_chg"])
    tracts = tracts.to_crs(3857)

    # Parcel layer and tract aggregation.
    parcel_fields = [
        "ParcelID", "Label_Current_Land_Use", "Label_Land_Use_2050",
        "Housing_Units_Current", "Housing_Units_2050",
    ]
    parcels = read_layer(gdb, "harris_housing_unit_change_2020_2050", parcel_fields).to_crs(3857)
    parcels["hu_change"] = pd.to_numeric(parcels["Housing_Units_2050"], errors="coerce").fillna(0) - pd.to_numeric(parcels["Housing_Units_Current"], errors="coerce").fillna(0)
    centroids = parcels[["hu_change", "geometry"]].copy()
    centroids.geometry = centroids.geometry.representative_point()
    joined = gpd.sjoin(centroids, tracts[["GEOID", "geometry"]], how="left", predicate="within")
    parcel_agg = joined.groupby("GEOID", dropna=True)["hu_change"].sum().rename("parcel_hu_change")
    tracts = tracts.merge(parcel_agg, on="GEOID", how="left")
    tracts["parcel_hu_change"] = tracts["parcel_hu_change"].fillna(0)

    bounds_df = tracts.geometry.bounds.rename(columns={"minx": "bbox_minx", "miny": "bbox_miny", "maxx": "bbox_maxx", "maxy": "bbox_maxy"})
    cent = tracts.geometry.centroid
    tracts = pd.concat([tracts.reset_index(drop=True), bounds_df.reset_index(drop=True)], axis=1)
    tracts["centroid_x"] = cent.x.to_numpy()
    tracts["centroid_y"] = cent.y.to_numpy()

    county = read_layer(gdb, "Harris_County").to_crs(3857)
    county_geom = county.geometry.union_all()
    bounds = tuple(map(float, county.total_bounds))

    # ZIP-code boundaries are used only for map navigation and geographic
    # reference. Dashboard indicators remain at their original tract, parcel,
    # point, or grid geographies; no ZIP-level analytical aggregation is made.
    zip_fields = ["ZIP", "POSTAL", "STATE", "ZIP_TYPE"]
    zipcodes = read_layer(gdb, "Harris_County_Zipcodes", zip_fields).to_crs(3857)
    zipcodes["ZIP"] = zipcodes["ZIP"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
    zipcodes["POSTAL"] = zipcodes["POSTAL"].fillna("").astype(str)
    zipcodes["STATE"] = zipcodes["STATE"].fillna("TX").astype(str)
    zipcodes["ZIP_TYPE"] = zipcodes["ZIP_TYPE"].fillna("").astype(str)
    zip_bounds = zipcodes.geometry.bounds.rename(columns={
        "minx": "bbox_minx", "miny": "bbox_miny",
        "maxx": "bbox_maxx", "maxy": "bbox_maxy",
    })
    zip_points = zipcodes.geometry.representative_point()
    zipcodes = pd.concat([zipcodes.reset_index(drop=True), zip_bounds.reset_index(drop=True)], axis=1)
    zipcodes["label_x"] = zip_points.x.to_numpy()
    zipcodes["label_y"] = zip_points.y.to_numpy()

    # Harris County commissioner precincts are used for location, orientation,
    # and tract-based screening summaries. No precinct-level analytical
    # aggregation is created in the source data.
    precinct_fields = ["PCT_NO", "AREA_IN_MI"]
    precincts = read_layer(gdb, "Harris_County_Commissioner_Precincts", precinct_fields).to_crs(3857)
    precincts["PCT_NO"] = pd.to_numeric(precincts["PCT_NO"], errors="coerce").astype("Int64")
    precincts["AREA_IN_MI"] = pd.to_numeric(precincts["AREA_IN_MI"], errors="coerce")
    precinct_bounds = precincts.geometry.bounds.rename(columns={
        "minx": "bbox_minx", "miny": "bbox_miny",
        "maxx": "bbox_maxx", "maxy": "bbox_maxy",
    })
    precinct_points = precincts.geometry.representative_point()
    precincts = pd.concat([precincts.reset_index(drop=True), precinct_bounds.reset_index(drop=True)], axis=1)
    precincts["label_x"] = precinct_points.x.to_numpy()
    precincts["label_y"] = precinct_points.y.to_numpy()

    tracts_web = tracts.copy()
    tracts_web.geometry = tracts_web.geometry.simplify(30, preserve_topology=True)
    tracts_web.to_file(out / "tracts_web.geojson", driver="GeoJSON")
    parcels_web = parcels.copy()
    parcels_web.geometry = parcels_web.geometry.simplify(2.5, preserve_topology=True)
    parcels_web.to_file(out / "parcels_web.geojson", driver="GeoJSON")
    county_web = county.copy()
    county_web.geometry = county_web.geometry.simplify(55, preserve_topology=True)
    county_web.to_file(out / "county_web.geojson", driver="GeoJSON")
    zipcodes_web = zipcodes.copy()
    zipcodes_web.geometry = zipcodes_web.geometry.simplify(20, preserve_topology=True)
    zipcodes_web.to_file(out / "zipcodes_web.geojson", driver="GeoJSON")
    precincts_web = precincts.copy()
    precincts_web.geometry = precincts_web.geometry.simplify(28, preserve_topology=True)
    precincts_web.to_file(out / "commissioner_precincts_web.geojson", driver="GeoJSON")

    # Climate point layers.
    climate_parts = []
    for code, gmt in GMT_CODES.items():
        lyr = read_layer(gdb, f"gmt_{code}_model_pr_ssp_mean", ["F3_day_precipitation_sum", "gmt"]).to_crs(3857)
        climate_parts.append(pd.DataFrame({
            "x": lyr.geometry.x,
            "y": lyr.geometry.y,
            "gmt": gmt,
            "precip_mm": pd.to_numeric(lyr["F3_day_precipitation_sum"], errors="coerce"),
        }))
    climate = pd.concat(climate_parts, ignore_index=True)
    climate.to_csv(out / "climate_points.csv", index=False)

    # Complete housing point arrays and web samples.
    sf = read_layer(gdb, "harris_single_family_2020", []).to_crs(3857)
    mf = read_layer(gdb, "harris_multi_family_2020", []).to_crs(3857)
    sf_xy = np.column_stack([sf.geometry.x.to_numpy(dtype=float), sf.geometry.y.to_numpy(dtype=float)])
    mf_xy = np.column_stack([mf.geometry.x.to_numpy(dtype=float), mf.geometry.y.to_numpy(dtype=float)])
    sf_xy = sf_xy[np.isfinite(sf_xy).all(axis=1)]
    mf_xy = mf_xy[np.isfinite(mf_xy).all(axis=1)]
    sf_sorted = sf_xy[np.argsort(sf_xy[:, 0])]
    mf_sorted = mf_xy[np.argsort(mf_xy[:, 0])]
    np.save(out / "sf_points_sorted.npy", sf_sorted)
    np.save(out / "mf_points_sorted.npy", mf_sorted)
    pd.DataFrame(mf_xy, columns=["x", "y"]).to_csv(out / "mf_points.csv", index=False)
    rng = np.random.default_rng(20260806)
    sample_n = min(args.sf_sample, len(sf_xy))
    sample_idx = np.sort(rng.choice(len(sf_xy), sample_n, replace=False))
    pd.DataFrame(sf_xy[sample_idx], columns=["x", "y"]).to_csv(out / "sf_sample.csv", index=False)

    # Full-record 1 km grid.
    minx, miny, maxx, maxy = bounds
    cell = 1000.0
    nx = int(math.ceil((maxx - minx) / cell))
    ny = int(math.ceil((maxy - miny) / cell))
    def grid_counts(xy: np.ndarray) -> np.ndarray:
        ix = np.floor((xy[:, 0] - minx) / cell).astype(int)
        iy = np.floor((xy[:, 1] - miny) / cell).astype(int)
        valid = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        flat = iy[valid] * nx + ix[valid]
        return np.bincount(flat, minlength=nx * ny).reshape(ny, nx)
    sf_counts, mf_counts = grid_counts(sf_xy), grid_counts(mf_xy)
    total_counts = sf_counts + mf_counts
    rows = []
    for iy, ix in np.argwhere(total_counts > 0):
        x0, y0 = minx + ix * cell, miny + iy * cell
        rows.append({
            "grid_id": f"{ix}_{iy}", "sf_count": int(sf_counts[iy, ix]),
            "mf_count": int(mf_counts[iy, ix]), "total_count": int(total_counts[iy, ix]),
            "geometry": box(x0, y0, x0 + cell, y0 + cell),
        })
    housing_grid = gpd.GeoDataFrame(rows, crs=3857)
    housing_grid.to_file(out / "housing_grid.geojson", driver="GeoJSON")

    # Derived kriging surfaces.
    kriging_meta: dict[str, object] = {"method": "ordinary kriging with fitted exponential semivariogram", "surfaces": {}}
    for code, gmt in GMT_CODES.items():
        pts = climate.loc[np.isclose(climate["gmt"], gmt)].dropna(subset=["x", "y", "precip_mm"])
        xy = pts[["x", "y"]].to_numpy(dtype=float)
        z = pts["precip_mm"].to_numpy(dtype=float)
        values, params = ordinary_kriging_grid(xy, z, bounds, county_geom)
        rgba = rgba_from_values(values)
        np.save(out / f"kriging_gmt_{code}_values.npy", values)
        np.save(out / f"kriging_gmt_{code}_rgba.npy", rgba)
        save_surface_png(values, bounds, out / f"kriging_gmt_{code}.png", gmt)
        kriging_meta["surfaces"][code] = params
    (out / "kriging_metadata.json").write_text(json.dumps(kriging_meta, indent=2), encoding="utf-8")

    # Data audit and dashboard summary.
    chei_a = ensure_geoid_text(read_layer(gdb, "harris_census_tract_CHEI_2050", ["GEOID", "CHEI_2050"]))[["GEOID", "CHEI_2050"]]
    chei_b = ensure_geoid_text(read_layer(gdb, "harris_census_tract_climate_housing_exposure_index_2050", ["GEOID", "CHEI"]))[["GEOID", "CHEI"]]
    compare = chei_a.merge(chei_b, on="GEOID", how="inner")
    max_chei_diff = float(np.nanmax(np.abs(pd.to_numeric(compare["CHEI_2050"], errors="coerce") - pd.to_numeric(compare["CHEI"], errors="coerce"))))
    available = set(inventory["gdb_layer"])
    requested_kriging = [f"gmt_{code}_pr_Kriging" for code in GMT_CODES]
    report = {
        "source_geodatabase": gdb.name,
        "available_vector_layers": int(len(inventory)),
        "requested_kriging_layers_not_exposed": [x for x in requested_kriging if x not in available],
        "kriging_display_substitution": "Derived ordinary-kriging surfaces from the corresponding uploaded GMT point layers.",
        "counts": {
            "census_tracts": int(len(tracts)), "zip_codes": int(len(zipcodes)),
            "commissioner_precincts": int(len(precincts)), "parcels": int(len(parcels)),
            "single_family_points": int(len(sf_xy)), "multi_family_points": int(len(mf_xy)),
            "housing_grid_cells": int(len(housing_grid)),
            "all_three_high_hotspots": int((tracts["hotspot_ca"].astype(str) == "All Three High").sum()),
        },
        "totals": {
            "population_2020": float(pd.to_numeric(tracts["hp_2020"], errors="coerce").sum()),
            "population_2050": float(pd.to_numeric(tracts["hp_2050"], errors="coerce").sum()),
            "population_change": float(pd.to_numeric(tracts["pop_chg"], errors="coerce").sum()),
            "households_2020": float(pd.to_numeric(tracts["hh_2020"], errors="coerce").sum()),
            "households_2050": float(pd.to_numeric(tracts["hh_2050"], errors="coerce").sum()),
            "household_change": float(pd.to_numeric(tracts["hh_chg"], errors="coerce").sum()),
            "employment_2020": float(pd.to_numeric(tracts["j_2020"], errors="coerce").sum()),
            "employment_2050": float(pd.to_numeric(tracts["j_2050"], errors="coerce").sum()),
            "employment_change": float(pd.to_numeric(tracts["job_chg"], errors="coerce").sum()),
        },
        "duplicate_CHEI_2050_max_abs_difference": max_chei_diff,
        "field_name_note": "Actual GDB tract layers use extreme_precip rather than the extreme_precipi spelling in the supplied inventory text.",
        "zip_code_note": "Harris_County_Zipcodes is included for boundary display and search only; no ZIP-level indicator aggregation is produced.",
        "commissioner_precinct_note": "Harris_County_Commissioner_Precincts is included for boundary display, search, and tract-based screening summaries only; no precinct-level source aggregation is produced.",
        "privacy_note": "The dashboard exports housing locations/counts only; property account and mailing fields are not included in web assets.",
    }
    (out / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
