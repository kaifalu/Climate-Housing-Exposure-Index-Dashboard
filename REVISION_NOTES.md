# Revision Notes — August 19, 2026

## ZIP-code location and boundary display

- Added a new **04 Locate a ZIP Code** control beneath the census-tract locator.
- Five-digit searches zoom to the matching `Harris_County_Zipcodes` feature and draw a prominent selected boundary.
- Added an optional **Show all ZIP-code boundaries** toggle for countywide orientation.
- Retained all 155 ZIP polygons and postal labels in the embedded dashboard data.
- ZIP geometry is used only for location and orientation; CHEI, precipitation, SVI, growth, housing, and hotspot indicators are not re-aggregated to ZIP geography.

## Pattern-based compound-hotspot map

The former color-dependent hotspot display has been replaced by a factor-based map and legend pattern system:

- diagonal lines — high GMT +2.5°C precipitation;
- vertical lines — high projected household growth;
- dots — high social vulnerability; and
- overlaid patterns — the corresponding two- or three-condition combinations.

The complete noncompensatory typology is retained: none high, hazard only, growth only, SVI only, hazard + growth, hazard + SVI, growth + SVI, and all three high. The implementation uses condition-filtered geometry sources so that the exact semantic overlays remain responsive in a data-self-contained browser application.

The legend reports tract counts and the documented countywide 80th-percentile screening thresholds:

- GMT +2.5°C precipitation ≥ 203.603 mm;
- projected household growth, 2020–2050 ≥ 746 households; and
- SVI ≥ 0.88386.

## Existing interface improvements retained

- Long legends remain inside their cards.
- Distribution charts use enlarged canvases and margins to avoid clipping.
- Active-layer interpretation bullets and the **From Map to Use** workflow remain available.
- The four-part dashboard introduction and organized full-width footer are retained.
- `index.html` remains the GitHub Pages entry file, and `climate_housing_exposure_index_dashboard.html` remains an identical compatibility copy.

## Validation

The final package verifies:

- 1,115 census tracts, 155 ZIP boundaries, and 31 exposed geodatabase layers;
- full single-family and multi-family point-array dimensions and sort order;
- unique five-digit ZIP values and a functional search example for ZIP 77007;
- exact hotspot score equivalence under the documented thresholds;
- all eight hotspot combinations and the five all-three-high tracts;
- presence of the ZIP controls, optional boundary toggle, pattern legend, factor thresholds, overview, guidance, and footer;
- byte-for-byte identity of the two data-self-contained HTML entry files; and
- browser interaction tests for hotspot switching, ZIP search, and all-ZIP-boundary display.
