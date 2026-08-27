# Climate-Housing Exposure Index Dashboard — GitHub Pages Release

This folder is ready for static GitHub Pages publication. The primary entry file, **`index.html`**, is data-self-contained: tract, parcel, climate, housing-preview, kriging, ZIP-boundary, commissioner-precinct, legend-filter, Quick Decision, and one-page reporting data and logic are embedded in the HTML together with BokehJS.

## Publish

1. Create or open the intended GitHub repository.
2. Upload `index.html` and `.nojekyll` to the repository root. Uploading the complete GitHub Pages package is recommended when source code and documentation should remain publicly available.
3. Open the repository's **Settings → Pages** page.
4. Under **Build and deployment**, select **Deploy from a branch**, then choose the default branch and **/(root)**.
5. Save and wait for GitHub to display the public HTTPS URL.

The dashboard does not require Python or separate analytical-data requests. Internet access is used only for optional CARTO/OpenStreetMap basemap tiles.

## Static-dashboard functions

- Use a consistently aligned page shell with content-driven Explore, Data & Methods, and Terms of Use sections.
- Explore CHEI, precipitation, growth, SVI, housing, land-use, parcel, kriging, and patterned hotspot layers.
- Review an expanded Layer Reference for the selected map layer, including source layer, geography, reference period, measurement, interpretation, planning use, and limitation.
- Search an exact census-tract GEOID or a five-digit Harris County ZIP code.
- Select and locate Harris County Commissioner Precinct 1–4.
- Optionally display all ZIP or all commissioner-precinct boundaries.
- Click one map-legend class to highlight matching features, zoom to matches, or clear the filter.
- Use four Quick Decision questions to activate focused analytical views.
- Generate a one-page tract, ZIP, or precinct decision brief and use the browser's **Print / Save as PDF** function.

ZIP and precinct reports are screening summaries of intersecting census tracts, not official ZIP- or precinct-level aggregates.

## Repository structure

Minimal publication:

```text
repository-root/
├── index.html
└── .nojekyll
```

Complete publication:

```text
repository-root/
├── index.html
├── climate_housing_exposure_index_dashboard.html
├── .nojekyll
├── README.md
├── GITHUB_PAGES_DEPLOYMENT.md
├── REVISION_NOTES.md
├── build_dashboard.py
├── preprocess_data.py
├── server.py
├── data/
├── scripts/
├── docs/
└── screenshots/
```

The complete deployment archive retains all processed data and server files. The full reproducibility archive additionally retains the revised source geodatabase.

Generated: 2026-08-27 UTC
