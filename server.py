#!/usr/bin/env python3
"""FastAPI server for the Climate Housing Exposure Index dashboard.

The standalone HTML works without this server. Running server.py adds efficient,
viewport-filtered access to all 1.09M+ housing point locations.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DASHBOARD = ROOT / "index.html"
LEGACY_DASHBOARD = ROOT / "climate_housing_exposure_index_dashboard.html"

app = FastAPI(
    title="Climate Housing Exposure Index Dashboard",
    description="Harris County climate-housing dashboard with tract, ZIP, and precinct navigation; clickable legends; decision briefs; patterned hotspots; and a viewport housing-point API",
    version="1.2.0",
)
app.mount("/data", StaticFiles(directory=DATA), name="data")


@lru_cache(maxsize=2)
def load_points(kind: Literal["single", "multi"]) -> np.ndarray:
    filename = "sf_points_sorted.npy" if kind == "single" else "mf_points_sorted.npy"
    return np.load(DATA / filename, mmap_mode="r")


def viewport_points(points: np.ndarray, xmin: float, xmax: float, ymin: float, ymax: float) -> np.ndarray:
    """Filter an x-sorted point array without scanning the full dataset."""
    lo = int(np.searchsorted(points[:, 0], xmin, side="left"))
    hi = int(np.searchsorted(points[:, 0], xmax, side="right"))
    candidate = points[lo:hi]
    return np.asarray(candidate[(candidate[:, 1] >= ymin) & (candidate[:, 1] <= ymax)])


def deterministic_cap(points: np.ndarray, max_points: int) -> np.ndarray:
    if len(points) <= max_points:
        return points
    idx = np.linspace(0, len(points) - 1, max_points, dtype=np.int64)
    return points[idx]


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    target = DASHBOARD if DASHBOARD.exists() else LEGACY_DASHBOARD
    return FileResponse(target, media_type="text/html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "dashboard": DASHBOARD.exists() or LEGACY_DASHBOARD.exists(),
        "dashboard_file": DASHBOARD.name if DASHBOARD.exists() else LEGACY_DASHBOARD.name,
        "single_family_points": int(load_points("single").shape[0]),
        "multi_family_points": int(load_points("multi").shape[0]),
    }


@app.get("/api/metadata")
def metadata() -> FileResponse:
    return FileResponse(DATA / "data_quality_report.json", media_type="application/json")


@app.get("/api/housing-points")
def housing_points(
    housing_type: Literal["single", "multi", "combined"] = "combined",
    xmin: float = Query(...),
    xmax: float = Query(...),
    ymin: float = Query(...),
    ymax: float = Query(...),
    max_points: int = Query(50000, ge=100, le=100000),
) -> JSONResponse:
    values = [xmin, xmax, ymin, ymax]
    if not all(math.isfinite(v) for v in values) or xmin >= xmax or ymin >= ymax:
        raise HTTPException(status_code=422, detail="Viewport bounds must be finite and ordered.")

    selected: list[tuple[str, np.ndarray]] = []
    if housing_type in {"single", "combined"}:
        selected.append(("Single-family", viewport_points(load_points("single"), xmin, xmax, ymin, ymax)))
    if housing_type in {"multi", "combined"}:
        selected.append(("Multi-family", viewport_points(load_points("multi"), xmin, xmax, ymin, ymax)))

    total = sum(len(points) for _, points in selected)
    if total == 0:
        return JSONResponse({"x": [], "y": [], "color": [], "kind": [], "n_total": 0, "n_returned": 0})

    # Preserve each type in combined views, then enforce one overall cap.
    rows: list[np.ndarray] = []
    kinds: list[str] = []
    if housing_type == "combined":
        for label, points in selected:
            allocation = max(1, round(max_points * len(points) / total))
            subset = deterministic_cap(points, allocation)
            rows.append(subset)
            kinds.extend([label] * len(subset))
    else:
        label, points = selected[0]
        subset = deterministic_cap(points, max_points)
        rows.append(subset)
        kinds.extend([label] * len(subset))

    combined = np.vstack(rows) if rows else np.empty((0, 2), dtype=float)
    if len(combined) > max_points:
        idx = np.linspace(0, len(combined) - 1, max_points, dtype=np.int64)
        combined = combined[idx]
        kinds = [kinds[i] for i in idx]

    colors = ["#168C95" if kind == "Single-family" else "#F16913" for kind in kinds]
    payload = {
        "x": np.round(combined[:, 0], 2).tolist(),
        "y": np.round(combined[:, 1], 2).tolist(),
        "color": colors,
        "kind": kinds,
        "n_total": int(total),
        "n_returned": int(len(combined)),
    }
    return JSONResponse(payload)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8050"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
