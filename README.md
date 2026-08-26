# Climate-Housing Exposure Index Dashboard — Harris County, Texas

Public GitHub Pages project: `https://kaifalu.github.io/Climate-Housing-Exposure-Index-Dashboard/`

The **Climate-Housing Exposure Index (CHEI) Dashboard** is an interactive web platform for examining where future extreme precipitation intersects with housing, population, employment, social vulnerability, and land-use change across Harris County. It combines climate projections at multiple global mean temperature (GMT) thresholds with 2020 conditions and 2050 projections to support place-based climate-risk screening.

## Current release

This release retains the previous ZIP-code and pattern-based hotspot functions and adds four major decision-support improvements:

- a **Harris County Commissioner Precinct locator** for Precincts 1–4, including a selected-boundary highlight and an optional overlay of all precinct boundaries;
- **clickable map legends** that highlight one class at a time, fade nonmatching features, report the number of matches, and provide **Zoom to matches** and **Clear filter** actions;
- a secondary **Quick Decision View** organized around four plain-language planning questions; and
- a browser-generated **one-page decision brief** for a selected census tract, ZIP code, or commissioner precinct, with a **Print / Save as PDF** option.

ZIP codes and commissioner precincts are used as location and reporting boundaries. The dashboard does not create official ZIP- or precinct-level source aggregates. Reports for those geographies summarize the medians, ranges, and high-condition shares of intersecting census tracts and clearly identify the results as screening summaries.

## Open or publish the dashboard

### GitHub Pages entry file

`index.html` is the upload-ready GitHub Pages entry file. It contains the dashboard application, analytical layers, locator boundaries, patterns, charts, and reporting logic in one data-self-contained HTML file. The compatibility file `climate_housing_exposure_index_dashboard.html` is byte-for-byte identical.

A minimal GitHub Pages repository can contain:

```text
Climate-Housing-Exposure-Index-Dashboard/
├── index.html
└── .nojekyll
```

After uploading the files, open the repository's **Settings → Pages** page, choose **Deploy from a branch**, select the default branch and **/(root)**, and save. The only optional external web requests made by the static dashboard are the CARTO/OpenStreetMap basemap tiles; the analytical content remains embedded.

### Standalone local access

Open either HTML file in a modern browser. No Python server is required. The standalone point layer uses a deterministic 30,000-record single-family preview plus all multi-family points, while the 1 km housing-density grid is calculated from every housing record.

### Full-data local application

The FastAPI version provides viewport-filtered queries against all **1,093,063 single-family** and **11,572 multi-family** point locations.

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

## Dashboard functions

The Explore Dashboard tab provides:

- CHEI for 2020 and 2050 and the 2020–2050 adaptation gap;
- the complete eight-category, pattern-based compound climate-inequality hotspot typology;
- tract precipitation, model points, and derived kriging display surfaces at GMT increases of 1.5°C, 2.0°C, 2.5°C, and 3.0°C relative to 1850–1899;
- GMT +2.5°C versus +1.5°C precipitation percentage change;
- 2050 population, household, and employment projections and their 2020–2050 changes;
- 2020 Social Vulnerability Index and population density;
- tract, density-grid, and point views of single- and multi-family housing stocks;
- parcel housing-unit change and current/projected land-use views;
- configurable two-factor overlap screening using countywide percentile thresholds;
- exact 11-digit census-tract GEOID search;
- five-digit ZIP-code search, selected ZIP highlighting, and an optional all-ZIP-boundaries overlay;
- commissioner precinct selection, selected precinct highlighting, and an optional all-precinct-boundaries overlay;
- clickable legend classes for census tracts, parcels, grid cells, climate points, housing points, and categorical layers;
- a tract-based locator corresponding to each selected kriging legend range;
- selected-tract profiles and charts;
- four Quick Decision questions; and
- a print-ready one-page decision brief for selected tract, ZIP, or precinct geography.

## Clickable map legends

Every map legend row functions as a single-category filter. Clicking a range or category:

1. highlights matching features with a strong outline or point marker;
2. fades nonmatching features while preserving geographic context;
3. reports the number of matches;
4. enables **Zoom to matches**; and
5. can be cleared by clicking the active class again or choosing **Clear filter**.

Only one legend class is active at a time. For derived kriging surfaces, the selected raster range is translated into the corresponding census-tract precipitation class so users can locate tracts represented by that range.

## Quick Decision View

The secondary Quick Decision View provides four low-barrier entry points:

1. **Highest overall exposure** — activates CHEI 2050 and highlights the highest class.
2. **Three-factor overlap** — activates the compound-hotspot map and highlights all-three-high tracts.
3. **Emerging adaptation needs** — activates the CHEI adaptation-gap layer and highlights the largest increases.
4. **Selected-place conditions** — summarizes the currently selected tract, ZIP code, or commissioner precinct.

These functions do not replace the full layer explorer; they provide a faster route from a planning question to a focused map result.

## One-page decision brief

The dashboard can generate a browser-based, print-ready report for:

- a selected census tract — exact tract values;
- a selected ZIP code — screening summary of intersecting census tracts; or
- a selected commissioner precinct — screening summary of intersecting census tracts.

The report includes a simplified boundary map, CHEI 2020 and 2050, adaptation gap, GMT +2.5°C precipitation, SVI, population/household/employment change, housing-stock context, compound-screening shares, and three decision-oriented findings. Choose **Print / Save as PDF** in the report window. ZIP and precinct reports display medians, ranges, and shares rather than presenting estimated official totals.

## Compound-hotspot definition

The compound-hotspot classification is noncompensatory. A tract receives one high-condition flag for each threshold it meets or exceeds.

| Factor | High screening threshold |
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

The map uses diagonal lines for precipitation hazard, vertical lines for projected household growth, and dots for social vulnerability. Combined categories overlay the relevant patterns. The thresholds are countywide 80th-percentile screening conventions rather than natural discontinuities in risk.

## Geographic locators

### Census tracts

Enter an exact 11-digit GEOID or click a tract on the map. The selected tract drives the profile charts and can be used for an exact one-page report.

### ZIP codes

Enter a five-digit Harris County ZIP code to zoom to and highlight its boundary. The optional toggle displays all **155 ZIP boundaries**. ZIP geometry is a navigation and screening-summary boundary only; no CHEI, SVI, climate, growth, housing, or hotspot indicator is officially re-aggregated to ZIP geography.

### Commissioner precincts

Select Precinct 1, 2, 3, or 4 and click **Find** to zoom to and highlight the boundary. The optional toggle displays all four boundaries. Precinct numbers are used instead of officeholder names so the interface remains stable when officeholders change. No official precinct-level source aggregation is created.

## Potential audiences and applications

The dashboard is designed for researchers, planners, local governments, housing and community-development agencies, emergency managers, policymakers, nonprofit organizations, and community stakeholders. It can support climate adaptation planning, housing resilience, land-use and growth management, infrastructure investment, vulnerability assessment, and environmental-justice research. Results are exploratory and should be validated with authoritative local data before decisions are made.

## Rebuild from the File Geodatabase

1. Extract `Climate_Housing_Exposure_Index_Dashboard.gdb_boundary.zip` so that the `.gdb` directory is available.
2. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

3. Run preprocessing:

```bash
python preprocess_data.py \
  --gdb "/path/to/Climate_Housing_Exposure_Index_Dashboard.gdb" \
  --output data
```

4. Rebuild both data-self-contained HTML files:

```bash
python build_dashboard.py
```

5. Validate and run:

```bash
python scripts/validate_dashboard.py
python server.py
```

An optional headless-browser smoke test is also included. It requires Playwright, which is intentionally not part of the runtime requirements:

```bash
pip install playwright
playwright install chromium
python scripts/browser_smoke_test.py
```

The preprocessing script does not modify the source geodatabase.

## Data architecture

```text
File Geodatabase
    ├── Tract metrics ──────────────────┐
    ├── Parcel land use/change ─────────┤
    ├── Climate GMT points ─────────────┤
    ├── Housing-stock points ───────────┤
    ├── ZIP-code boundaries ────────────┤
    ├── Commissioner precincts ─────────┤
    └── County boundary ────────────────┘
                     │
                     └── preprocess_data.py
                             ├── GeoJSON web geometry
                             ├── CSV / NumPy point assets
                             ├── kriging arrays
                             └── data-quality report
                                      │
                           build_dashboard.py
                             ├── index.html
                             └── compatibility HTML
                                      │
                               server.py
                             └── full-point viewport API
```

## Kriging substitution and audit findings

The revised geodatabase exposes **32 vector layers** through the open-source FileGDB reader, including `Harris_County_Zipcodes` and `Harris_County_Commissioner_Precincts`. It does not expose the four user-listed `gmt_15_pr_Kriging`, `gmt_20_pr_Kriging`, `gmt_25_pr_Kriging`, and `gmt_30_pr_Kriging` datasets. `preprocess_data.py` therefore derives ordinary-kriging display surfaces from the corresponding GMT point layers using a fitted exponential semivariogram. The dashboard labels these surfaces as derived, while retaining the original model points and tract aggregations.

The two CHEI 2050 feature classes contain identical CHEI values and are consolidated in the interface. Actual tract precipitation layer names use `extreme_precip`, while the supplied inventory text used `extreme_precipi` for several names.

## Performance and privacy

- Tract, ZIP, precinct, parcel, grid, and county geometries are simplified for web display while the source geodatabase remains unchanged.
- The 1 km housing-density grid is calculated from all housing records.
- Full housing coordinates are stored as x-sorted NumPy arrays; `server.py` uses binary search and y filtering to query the current viewport.
- Point responses are deterministically capped to prevent browser overload.
- Web assets exclude HCAD account IDs, mailing fields, assessed values, and other unused property attributes.
- ZIP and precinct boundaries contain only the fields required for geographic navigation, area context, and tract-intersection reporting.

## Key files

| File | Purpose |
|---|---|
| `index.html` | Primary standalone dashboard and GitHub Pages entry file |
| `climate_housing_exposure_index_dashboard.html` | Identical compatibility copy |
| `.nojekyll` | Prevents GitHub Pages from applying Jekyll processing |
| `server.py` | FastAPI application and full housing-point viewport endpoint |
| `preprocess_data.py` | Rebuilds prepared web data from the FileGDB |
| `build_dashboard.py` | Rebuilds both standalone HTML files and all browser interactions |
| `scripts/validate_dashboard.py` | Validates source counts, locators, hotspot logic, HTML functions, and package consistency |
| `scripts/browser_smoke_test.py` | Optional Playwright test for precinct location, legend filtering, Quick Decision, and one-page reporting |
| `data/data_quality_report.json` | Automated audit and summary totals |
| `data/gdb_layer_inventory.csv` | Inventory of 32 exposed geodatabase layers |
| `data/zipcodes_web.geojson` | Simplified 155-feature ZIP locator layer |
| `data/commissioner_precincts_web.geojson` | Simplified four-feature commissioner precinct locator layer |
| `docs/Climate_Housing_Exposure_Index_Dashboard_Reproducibility_Guide.docx` / `.pdf` | Illustrated implementation and deployment guide |
| `REVISION_NOTES.md` | Detailed release record |
| `TERMS_OF_USE.md` | Dashboard terms of use |

## Source organizations

- Texas Tech University Climate Center: `https://www.depts.ttu.edu/csc/`
- H-GAC Regional Growth Forecast: `https://www.h-gac.com/regional-growth-forecast`
- H-GAC Regional Land Use Information System: `https://datalab.h-gac.com/rluis/`
- Harris Central Appraisal District public data: `https://hcad.org/hcad-online-services/pdata/`
- CDC/ATSDR Social Vulnerability Index: `https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html`

## Terms and contact

The dashboard is intended for research, educational, and informational use. It includes modeled, estimated, and projected values and should not be the sole basis for decisions. Unless otherwise noted, data and visualizations are provided for non-commercial use with proper attribution. See `TERMS_OF_USE.md` for the complete terms.

Questions or feedback: **Kaifa Lu / CECREH / Kaifa.Lu@ttu.edu**
