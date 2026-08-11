# Revision Notes — August 2026

## Visual and layout improvements

- Increased the effective dashboard width and rebalanced the left, map, and profile columns.
- Removed fixed-height constraints that caused long legends to overflow their cards.
- Enlarged the distribution chart and adjusted plot margins, labels, and title sizing to prevent clipping.
- Added active-layer interpretation bullets and a three-step “From map to use” panel.
- Replaced the undersized footer with a full-width, three-part footer for project identity, purpose, and contact information.
- Added a collapsible four-card introduction near the top of the dashboard covering the overview, key functions, audiences, and practical applications.

## Compound-hotspot improvements

The former score-only legend has been replaced with the complete noncompensatory typology:

- None high
- Hazard only
- Growth only
- SVI only
- Hazard + growth
- Hazard + SVI
- Growth + SVI
- All three high

The legend now reports tract counts and displays the exact “high” thresholds:

- GMT +2.5°C precipitation ≥ 203.603 mm
- Projected household growth, 2020–2050 ≥ 746 households
- SVI ≥ 0.88386

The selected-tract profile also reports the combination, score, and active high-condition flags.

## Analytical and interaction improvements

- Added numeric threshold reporting to the configurable two-factor overlap mode.
- Added more useful explanatory text for numeric, categorical, point, grid, and surface layers.
- Preserved the original analytical data and layer menu while improving interpretability.
- Added `index.html` as the GitHub Pages entry file while retaining the original standalone filename as an identical compatibility copy.

## Validation

The revised package verifies:

- required static, source, and data files;
- 1,115 census tracts and 30 exposed geodatabase layers;
- full single-family and multi-family point-array dimensions and sort order;
- exact hotspot score equivalence under the documented thresholds;
- all eight hotspot combinations and the five all-three-high tracts;
- presence of the revised overview, guidance, footer, and threshold content; and
- byte-for-byte identity of the two standalone HTML entry files.
