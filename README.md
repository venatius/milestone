# Milestone

Milestone is a CSIT321 capstone prototype that explores how dated satellite measurements and property registry records can support construction progress review. The demo contains four exploratory study areas in Dubai and stage evidence notes.

## Run locally

Python 3.11 or later is sufficient for the chart and registry demo.

```sh
python build_demo.py
python serve.py --port 4861
```

Open [the local demo](http://127.0.0.1:4861/demo.html), or [open Jebel Ali Village directly](http://127.0.0.1:4861/demo.html?site=village). The build includes cached Sentinel measurements and a reduced registry sample. The plot geometry is exploratory and the stage notes are provisional.

## Data and imagery

- The registry sample is from [Dubai Land Department open data](https://dubailand.gov.ae/en/open-data/real-estate-data/). For a local refresh, place the official project and land CSVs at `projects.csv` and `land_registry.csv`, then run `python build_registry.py`.
- The source includes Earth Engine extraction scripts and the dated thumbnail exporter. Install `earthengine-api` and authenticate your authorised Earth Engine account to run the exporter. Use `python export_weekly_frames.py --help` for the required arguments.
- The local research build can use separately authorised historical imagery with `python build_demo.py --with-local-imagery` and the corresponding local manifests and image files. This public source snapshot excludes cached Esri and Google Earth imagery. See [Esri Wayback export terms](https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/wayback-export) and [Google's imagery guidelines](https://about.google/brand-resource-center/products-and-services/geo-guidelines/).
- Sentinel measurements use [Copernicus data through Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED) and [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/catalog). The repository does not grant rights to third-party datasets.

The prototype was developed by Team Origin with AI coding assistance. The team is responsible for checking data and interpretations.
