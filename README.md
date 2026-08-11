# Climate-Housing Exposure Index Dashboard — Harris County, Texas

The **Climate-Housing Exposure Index (CHEI) Dashboard** is an interactive web platform for examining where future extreme precipitation intersects with housing, population, employment, social vulnerability, and land-use change across Harris County. It combines climate projections at multiple global mean temperature (GMT) thresholds with current and projected community conditions to support place-based climate-risk screening.

## Revised interface

This release incorporates the requested GitHub Pages and visual-design revisions:

- legends remain fully contained within their panels, including long categorical legends;
- distribution charts use a wider canvas and adjusted margins so titles, axes, labels, and bars are visible in full;
- each active layer includes concise interpretation bullets and a short map-to-action workflow;
- unused lower-page space is reduced through a more balanced three-column layout and additional explanatory content;
- the footer is reorganized into clearly separated project, purpose, and contact sections;
- the top of the dashboard now includes four concise sections: **Dashboard Overview**, **Key Functions**, **Potential Audiences**, and **Practical Applications**;
- the compound-hotspot layer now retains all eight underlying factor combinations rather than showing only a 0–3 score; and
- the hotspot legend displays the exact countywide 80th-percentile screening thresholds used to define “high.”

## Open or publish the dashboard

### GitHub Pages entry file

`index.html` is the upload-ready GitHub Pages entry file. It is self-contained and does not require Python.

A minimal GitHub Pages repository can contain:

```text
climate-housing-exposure-index/
├── index.html
└── .nojekyll
```

After placing these files in the repository root, enable GitHub Pages for the repository’s default branch and root folder. GitHub will then provide the public HTTPS address associated with that repository.

### Standalone local access

Open either of these files in a modern browser:

- `index.html` — recommended entry file;
- `climate_housing_exposure_index_dashboard.html` — compatibility copy with identical content.

The static dashboard embeds the prepared analytical layers and Bokeh JavaScript. Its housing-point view uses a deterministic 30,000-record single-family preview sample plus all multi-family points, while the 1 km housing-density grid is based on every source housing record.

### Full-data local application

The FastAPI version adds viewport-filtered queries against all **1,093,063 single-family** and **11,572 multi-family** point locations.

Windows:

```bat
run_dashboard.bat
```

macOS/Linux:

```bash
./run_dashboard.sh
```

Or run directly:

```bash
python server.py
```

Then open `http://127.0.0.1:8050`. The health endpoint is `http://127.0.0.1:8050/api/health`.

## Dashboard overview

The dashboard visualizes how future climate-related precipitation extremes intersect with housing, population, employment, social vulnerability, and land-use change. It integrates climate projections under GMT increases of **1.5°C, 2.0°C, 2.5°C, and 3.0°C** relative to 1850–1899 with 2020 conditions and 2050 projections.

## Key functions

The Explore Dashboard tab provides:

- CHEI for 2020 and 2050 and the 2020–2050 adaptation gap;
- the complete eight-category compound-hotspot typology;
- tract precipitation, model points, and derived kriging surfaces at four GMT thresholds;
- GMT +2.5°C versus +1.5°C precipitation percentage change;
- 2050 population, household, and employment projections and their 2020–2050 changes;
- 2020 SVI and population density;
- tract, density-grid, and point views of single- and multi-family housing stocks;
- parcel housing-unit change and current/projected land-use views;
- configurable two-factor overlap screening using countywide percentile thresholds;
- exact GEOID search, hover details, tract selection, distribution charts, and selected-tract profiles; and
- contextual explanations, interpretation reminders, methods, data sources, and terms of use.

## Compound-hotspot definition

The compound-hotspot classification is noncompensatory: a tract receives one high-condition flag for each threshold it meets or exceeds.

| Factor | “High” screening threshold |
|---|---:|
| Extreme precipitation | GMT +2.5°C average 3-day precipitation sum **≥ 203.603 mm** |
| Projected household growth | 2020–2050 change **≥ 746 households** |
| Social vulnerability | 2020 SVI **≥ 0.88386** |

The dashboard retains all eight combinations:

1. None high
2. Hazard only
3. Growth only
4. SVI only
5. Hazard + growth
6. Hazard + SVI
7. Growth + SVI
8. All three high

These thresholds represent countywide 80th-percentile screening conventions rather than natural discontinuities in risk.

## Potential audiences and applications

The dashboard is designed for researchers, planners, local governments, housing and community-development agencies, emergency managers, policymakers, nonprofit organizations, and community stakeholders. It can support climate adaptation planning, housing resilience, land-use and growth management, infrastructure investment, vulnerability assessment, and environmental-justice research. The results are exploratory and should be validated with authoritative local data before decisions are made.

## Environment setup

Python virtual environment:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Conda:

```bash
conda env create -f environment.yml
conda activate climate-housing-dashboard
python server.py
```

## Rebuild from the File Geodatabase

1. Extract `Climate_Housing_Exposure_Index_Dashboard.gdb.zip` so that the `.gdb` directory is available.
2. Run preprocessing:

```bash
python preprocess_data.py \
  --gdb "/path/to/Climate_Housing_Exposure_Index_Dashboard.gdb" \
  --output data
```

3. Rebuild both standalone HTML entry files:

```bash
python build_dashboard.py
```

4. Validate and run:

```bash
python scripts/validate_dashboard.py
python server.py
```

The preprocessing script does not modify the source geodatabase.

## Data architecture

```text
File Geodatabase
    ├── Tract metrics ────────────┐
    ├── Parcel land use/change ───┼── preprocess_data.py ── prepared web assets
    ├── Climate GMT points ───────┤                          ├── GeoJSON
    ├── Housing-stock points ─────┤                          ├── CSV / NPY
    └── County boundary ──────────┘                          └── kriging arrays
                                                               │
                           build_dashboard.py ───────────────────┤
                                                               ├── index.html
                                                               └── compatibility HTML
                           server.py ─────────────────────────────┘
                                                               └── full-point API
```

## Kriging substitution and audit findings

The uploaded geodatabase exposed 30 vector layers through the open-source FileGDB reader. It did not expose the four user-listed `gmt_15_pr_Kriging`, `gmt_20_pr_Kriging`, `gmt_25_pr_Kriging`, and `gmt_30_pr_Kriging` datasets. `preprocess_data.py` therefore derives ordinary-kriging display surfaces from the corresponding GMT point layers using a fitted exponential semivariogram. The dashboard explicitly labels these surfaces as derived; the original model points and tract aggregations remain available.

The two CHEI 2050 feature classes contain identical CHEI values and are consolidated in the interface. The actual tract precipitation layer names use `extreme_precip`, while the supplied inventory text used `extreme_precipi` for several names.

## Performance and privacy

- Tract and parcel geometries are simplified for web display while the source geodatabase remains unchanged.
- The 1 km housing-density grid is calculated from all housing records.
- Full housing coordinates are stored as x-sorted NumPy arrays; `server.py` uses binary search and y filtering to query only the current map viewport.
- Point responses are deterministically capped to prevent browser overload.
- Web assets exclude HCAD account IDs, mailing-city/state/ZIP fields, assessed values, and other unused property attributes.

## Deployment options

### Static GitHub Pages

Use `index.html` and `.nojekyll`. This option provides all tract, parcel, climate, chart, methods, and interpretation functions, plus the optimized housing-point preview.

### Full-data container service

The included `Dockerfile` runs the FastAPI application on a compatible container platform. `render.yaml` provides an example service definition.

```bash
docker build -t climate-housing-exposure-index .
docker run --rm -p 8050:8050 climate-housing-exposure-index
```

The application exposes `/api/health` for service monitoring.

## Key files

| File | Purpose |
|---|---|
| `index.html` | Primary standalone dashboard and GitHub Pages entry file |
| `climate_housing_exposure_index_dashboard.html` | Identical compatibility copy |
| `.nojekyll` | Prevents GitHub Pages from applying Jekyll processing |
| `server.py` | FastAPI application and full housing-point viewport endpoint |
| `preprocess_data.py` | Rebuilds prepared web data from the FileGDB |
| `build_dashboard.py` | Rebuilds both standalone HTML files |
| `scripts/validate_dashboard.py` | Validates files, counts, hotspot logic, and revised interface identifiers |
| `data/data_quality_report.json` | Automated audit and summary totals |
| `data/gdb_layer_inventory.csv` | Exposed geodatabase layer inventory |
| `Dockerfile`, `render.yaml` | Container deployment examples |
| `REVISION_NOTES.md` | Detailed record of the interface and analytical revisions |
| `TERMS_OF_USE.md` | Dashboard terms supplied for the project |
| `docs/Climate_Housing_Exposure_Index_Dashboard_Reproducibility_Guide.docx` | Illustrated implementation guide |

## Source organizations

- Texas Tech University Climate Center: https://www.depts.ttu.edu/csc/
- H-GAC Regional Growth Forecast: https://www.h-gac.com/regional-growth-forecast
- H-GAC Regional Land Use Information System: https://datalab.h-gac.com/rluis/
- Harris Central Appraisal District public data: https://hcad.org/hcad-online-services/pdata/
- CDC/ATSDR Social Vulnerability Index: https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html

## Terms and contact

The dashboard is intended for research, educational, and informational use. It contains modeled, estimated, and projected values and should not be the sole basis for decisions. Unless otherwise noted, data and visualizations are provided for non-commercial use with proper attribution. See `TERMS_OF_USE.md` for the complete terms.

Questions or feedback: **Kaifa Lu / CECREH / Kaifa.Lu@ttu.edu**
