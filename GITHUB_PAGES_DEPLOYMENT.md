# Climate-Housing Exposure Index Dashboard — GitHub Pages Release

This folder is ready for static GitHub Pages publication. The primary entry file, **`index.html`**, is a data-self-contained dashboard: tract, parcel, climate, housing-preview, kriging, and ZIP-boundary data are embedded in the HTML together with the Bokeh application code.

## Publish

1. Create or open the intended GitHub repository.
2. Upload `index.html` and `.nojekyll` to the repository root. Uploading the complete GitHub Pages package is also acceptable when the source code and documentation should remain publicly available.
3. Open the repository's **Settings → Pages** page.
4. Under **Build and deployment**, select **Deploy from a branch**, then select the default branch and **/(root)**.
5. Save and wait for GitHub to display the public HTTPS URL.

The analytical dashboard does not require Python or separate data-file requests. Internet access is used only for the CARTO/OpenStreetMap basemap tiles; the analytical layers, five-digit ZIP locator, optional all-ZIP-boundaries overlay, pattern-based compound-hotspot map, legends, charts, methods, and terms remain embedded in `index.html`.

## ZIP and hotspot behavior

- Enter a five-digit Harris County ZIP code to zoom to and highlight its boundary.
- Use **Show all ZIP-code boundaries** to display all 155 ZIP boundaries.
- ZIP geometry is used for navigation only; no indicator is re-aggregated to ZIP geography.
- The compound-hotspot map uses diagonal lines for precipitation hazard, vertical lines for household growth, and dots for social vulnerability; combinations overlay the corresponding patterns.

## Included source code

The final GitHub Pages archive retains all code under `source_code/`. The complete processed data needed to rebuild or run the server-backed version are included in the deployment archive, and the revised source geodatabase is included in the full reproducibility archive.

Generated: 2026-08-19 UTC
