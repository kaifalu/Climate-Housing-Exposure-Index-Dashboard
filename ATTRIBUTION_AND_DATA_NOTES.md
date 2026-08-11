# Attribution and Data Notes

Source organizations referenced by the dashboard:

- Texas Tech University Climate Center: https://www.depts.ttu.edu/csc/
- Houston-Galveston Area Council Regional Growth Forecast: https://www.h-gac.com/regional-growth-forecast
- H-GAC Regional Land Use Information System: https://datalab.h-gac.com/rluis/
- Harris Central Appraisal District public data: https://hcad.org/hcad-online-services/pdata/
- CDC/ATSDR Social Vulnerability Index: https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html

## Important implementation note

The uploaded File Geodatabase exposed 30 vector layers through the open-source FileGDB reader. It did not expose the four user-listed `gmt_*_pr_Kriging` datasets. The reproducible preprocessing script therefore creates clearly described ordinary-kriging display surfaces from each corresponding uploaded GMT point layer. The original point and tract-level precipitation layers remain available in the dashboard.

The two CHEI 2050 feature classes contain identical CHEI values and are consolidated into one user-facing map option. The dashboard does not export HCAD account IDs, mailing addresses, or related property-owner fields; only housing locations and aggregate counts are used.
