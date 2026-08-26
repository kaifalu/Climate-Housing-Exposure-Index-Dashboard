# Revision Notes — August 26, 2026

## Commissioner precinct location and boundary display

- Added a new **05 Locate a Commissioner Precinct** control beneath the census-tract and ZIP-code locators.
- Users select Precinct 1, 2, 3, or 4 from a dropdown and click **Find** to zoom to and highlight the selected boundary.
- Added an optional **Show all commissioner precinct boundaries** toggle for countywide orientation.
- Retained all four features from `Harris_County_Commissioner_Precincts` in the embedded dashboard data.
- Precinct numbers are used instead of officeholder names to avoid future interface obsolescence.
- Precinct geometry is used for location, orientation, and tract-based screening summaries; no official precinct-level source aggregation is produced.

## Clickable legend filtering

- Converted every map legend row into a clickable single-category filter.
- Matching tracts, parcels, grid cells, climate points, or housing points are emphasized, while nonmatching features are faded.
- Added live match counts, **Zoom to matches**, and **Clear filter** actions.
- Clicking the active class again restores the complete map.
- Only one class may be active at a time to maintain a simple workflow for users with limited time or data literacy.
- Kriging legend ranges use the corresponding tract-level precipitation bins to locate census tracts represented by the selected raster range.
- Resolved an overlay-rendering race condition by hiding legend overlay renderers before clearing their data sources.

## Quick Decision View

Added four secondary decision-oriented actions:

1. **Highest overall exposure** — activates CHEI 2050 and highlights its highest class.
2. **Three-factor overlap** — activates the compound-hotspot layer and highlights all-three-high tracts.
3. **Emerging adaptation needs** — activates the CHEI adaptation-gap layer and highlights its largest-increase class.
4. **Selected-place conditions** — summarizes the currently selected tract, ZIP code, or commissioner precinct.

A short scheduling safeguard ensures the intended legend selection remains active after layer switching.

## One-page decision brief

- Added a browser-generated, print-ready one-page report for a selected census tract, ZIP code, or commissioner precinct.
- Census-tract reports use exact tract values.
- ZIP and precinct reports summarize intersecting census tracts using medians, ranges, high-condition shares, and tract counts.
- Reports include a simplified boundary map, CHEI, precipitation, SVI, growth, housing-stock context, compound-screening shares, decision-oriented findings, and interpretation limitations.
- Added a **Print / Save as PDF** button that works without a server or external PDF library.
- ZIP and precinct reports explicitly state that the result is a screening summary rather than an official aggregate.

## Existing functions retained

- Five-digit ZIP-code locator and optional all-ZIP-boundaries overlay.
- Eight-category, pattern-based compound climate-inequality hotspot map.
- Exact countywide 80th-percentile hotspot thresholds.
- Contained legends, unclipped distribution charts, active-layer guidance, four-part dashboard introduction, and organized footer.
- Byte-identical `index.html` and compatibility HTML files.

## Validation completed

The final package verifies:

- 32 exposed geodatabase layers;
- 1,115 census tracts, 155 ZIP boundaries, four commissioner precincts, and 20,344 changed parcels;
- full single-family and multi-family point-array dimensions and sort order;
- unique five-digit ZIP values and stable precinct identifiers 1–4;
- valid locator geometries and nonempty tract intersections for every ZIP and precinct;
- exact hotspot score equivalence under the documented thresholds;
- all eight hotspot combinations and five all-three-high tracts;
- clickable legend behavior across tract, parcel, grid, climate-point, housing-point, hotspot, and kriging views;
- tract, ZIP, and precinct report generation;
- all four Quick Decision actions;
- a one-page letter-size report rendering without clipping; and
- no JavaScript exceptions in the completed browser smoke tests.
