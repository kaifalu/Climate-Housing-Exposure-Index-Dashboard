# Attribution and Data Notes

Source organizations referenced by the dashboard:

- Texas Tech University Climate Center: https://www.depts.ttu.edu/csc/
- Houston-Galveston Area Council Regional Growth Forecast: https://www.h-gac.com/regional-growth-forecast
- H-GAC Regional Land Use Information System: https://datalab.h-gac.com/rluis/
- Harris Central Appraisal District public data: https://hcad.org/hcad-online-services/pdata/
- CDC/ATSDR Social Vulnerability Index: https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html

## Important implementation notes

The revised File Geodatabase exposes **32 vector layers** through the open-source FileGDB reader, including **155 `Harris_County_Zipcodes` polygons** and **four `Harris_County_Commissioner_Precincts` polygons**.

ZIP and commissioner-precinct geometries are simplified for web display and used for search or selection, map zoom, selected-boundary highlighting, optional all-boundaries overlays, and tract-based screening summaries. No CHEI, climate, vulnerability, growth, housing, land-use, or hotspot indicator is officially re-aggregated to ZIP or precinct geography. A ZIP or precinct decision brief reports medians, ranges, high-condition shares, and the number of intersecting census tracts and clearly labels the output as a screening summary.

The reader does not expose the four user-listed `gmt_*_pr_Kriging` datasets. The reproducible preprocessing script therefore creates clearly described ordinary-kriging display surfaces from each corresponding uploaded GMT point layer. Original point and tract-level precipitation layers remain available. When users click a kriging legend range, the dashboard locates census tracts in the corresponding tract-level precipitation range.

The two CHEI 2050 feature classes contain identical CHEI values and are consolidated into one user-facing map option. The compound-hotspot layer retains all eight combinations and uses diagonal, vertical, and dot patterns to encode precipitation hazard, household growth, and social vulnerability without relying on color alone.

The dashboard does not export HCAD account IDs, property mailing addresses, property mailing ZIP fields, assessed values, or related owner attributes. Only housing locations, aggregate counts, and the public reference geometries needed for navigation and screening are used.
