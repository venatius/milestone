# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Milestone is a CSIT321 capstone prototype (Team Origin). It shows how dated satellite measurements (Sentinel-1 radar, Sentinel-2 optical) and Dubai Land Department (DLD) registry records can support review of construction progress for eight Dubai project sites. It is a shared team repository. Stage notes and plot geometry are provisional or exploratory, so treat interpretations in the data and UI text as claims the team must check.

## Commands

Python 3.11+. There is no package manifest, test suite, linter or formatter config.

```sh
python build_demo.py                        # demo-template.html + cached JSON -> demo.html (gitignored)
python build_demo.py --out other.html
python serve.py --port 4861                 # http://127.0.0.1:4861/demo.html  (?site=village for one site)
python build_registry.py                    # needs local projects.csv + land_registry.csv (gitignored DLD CSVs) -> registry-evidence.json
python inspect_registry.py <csv> [--area-column C --area-value V]   # schema/hash check of a raw registry CSV
python export_weekly_frames.py --help       # Earth Engine thumbnails; needs earthengine-api + authorised account
```

`build_demo.py` checks its inputs and fails loudly when one is missing, empty or misaligned. A successful build is the main check that a data or template change is consistent.

## Architecture

**Single-file demo build.** `build_demo.py` loads the cached evidence JSON files and assembles one `payload` dict (months, registry, mapping, radar, optical, history, construction, waybackIndex, sampled, villageMonthly). It serialises the dict into the single `@@DATA@@` placeholder inside `<script id="evidence" type="application/json">` in `demo-template.html`, escaping `</`. All UI and chart logic is inline in `demo-template.html` and reads that embedded JSON. It does not fetch data at runtime. If `milestone-dld-panel-crosswalk-2026-11-16.json` exists, the build also adds a DLD crosswalk table before `</body>`. A change to the payload shape needs matching changes in both `build_demo.py` and the template's JS.

**`SITES` in `build_demo.py` is the shared site registry.** It maps each site key to coordinates, a DLD project number and its radar/optical files. `index_wayback.py` and `export_weekly_frames.py` import it, and `index_wayback.py` adds extra centres (mall, como, naya, frond).

**Data files are dated, committed snapshots.** The date in each `*-YYYY-MM-DD.json` filename is when the data was extracted. Filenames are hardcoded in `build_demo.py`, so a data refresh means adding a new dated file and updating the reference to it. The producers are:
- `earthengine-*.js`: Earth Engine Code Editor scripts, run manually in the browser, not from this repo. They correspond to the `radar-*` and `optical-monthly-*` files by site name. They `print()` to the console rather than writing files.
- `sample-panel-sentinel.py` (Microsoft Planetary Computer; needs `numpy` and `requests`) → `sentinel-panel-sampled-2026-11-16.json`, or `sentinel-village-monthly-2026-11-16.json` with `--village-monthly`.
- `sample-village-optical-metrics.py` (reuses `sample-panel-sentinel.py` through importlib) → `sentinel-village-monthly-2026-11-20.json`.
- `index_wayback.py` (Esri Wayback metadata only, no tiles) → `wayback-capture-index-*.json`.
- `build_registry.py` → `registry-evidence.json`.

**Caution:** these sampling and indexing scripts write to fixed, already-committed filenames. Running one overwrites an existing snapshot instead of creating a new one.

**Local-only imagery.** `--with-local-imagery` adds Esri Wayback and Google Earth frames and weekly thumbnails as data URIs. Those images, their manifests (`google-earth-timeline-manifest.json`, `wayback-sites-2026-11-10.json`, `weekly-*.json`) and all `*.png`/`*.jpg` files are deliberately left out of the repo for licensing reasons (see README and `.gitignore`). Don't commit them or add them to the default build.

**`serve.py`** serves only files named in its `ALLOWED` set (plus `Milestone_Weekly_Progress_*.pdf`) on loopback. A new file that must be served directly needs an entry there. `demo.html` is self-contained, so the JSON inputs don't need entries.

## Conventions

- Coding style differs between files. Some scripts are compact one-space-indented code and others are PEP 8. Match the style of the file you edit and don't reformat it.
- Wording about the data should stay cautious: coordinates are "candidate" or "exploratory", registry links are "not verified keys", and dates refer to captures rather than to construction events. `IMAGERY.md` records the reviewed Village Wayback dates.
- Third-party data (Copernicus, DLD, Esri, Google) carries its own terms, and the repo grants no rights to it.
