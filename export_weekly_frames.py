"""Export dated, cloud-masked Sentinel-2 thumbnails with Earth Engine."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from urllib.request import urlopen

from build_demo import ROOT, SITES, REGISTRY, load_json

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
ARCHIVE_START = date(2017, 3, 28)
SOURCE = "Copernicus Sentinel-2 L2A via Google Earth Engine"
SIZE = 320
MIN_CLEAR = 0.80
DAY = timedelta(days=1)
WEEK = 7 * DAY


def windows(start, through, include_baseline):
    if include_baseline:
        for i in (2, 1):
            yield start - i * 30 * DAY, start - (i - 1) * 30 * DAY, "baseline"
    first = start
    while first <= through:
        yield first, min(first + WEEK, through + DAY), "weekly"
        first += WEEK


def clear_image(ee, image):
    scl = image.select("SCL")
    clear = scl.remap([4, 5, 6], [1, 1, 1], 0).eq(1)
    rgb = image.select(["B4", "B3", "B2"])
    valid = clear.And(rgb.mask().reduce(ee.Reducer.min()))
    return rgb.updateMask(valid)


def export_site(ee, site, start, through, registry_start, project_number):
    lon, lat = SITES[site]["coordinates"]
    projection = ee.Projection("EPSG:32640")
    bounds = ee.Geometry.Point([lon, lat]).buffer(600, 1, projection).bounds(1, projection)
    collection = ee.ImageCollection(COLLECTION).filterBounds(bounds)
    frames, gaps = [], []

    def score(image):
        clear = clear_image(ee, image).select("B4").mask().unmask(0, False)
        fraction = clear.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=bounds, scale=20,
            crs=projection, maxPixels=100000,
        ).get("B4")
        return image.set("local_clear_fraction", fraction)

    for first, stop, kind in windows(start, through, registry_start == start):
        window = {"window_start": first.isoformat(), "window_end_exclusive": stop.isoformat()}
        if stop <= ARCHIVE_START:
            gaps.append(dict(window, kind=kind, reason="before Sentinel-2 L2A archive"))
            continue
        images = collection.filterDate(max(first, ARCHIVE_START).isoformat(), stop.isoformat())
        ranked = images.map(score).filter(ee.Filter.gte("local_clear_fraction", MIN_CLEAR))
        # Sort on clear fraction, then acquisition time for deterministic ties.
        ranked = ranked.map(lambda im: im.set("rank", ee.Number(im.get("local_clear_fraction"))
                            .multiply(1e15).add(ee.Number(im.get("system:time_start")).divide(1e6))))
        best = ranked.sort("rank", False).limit(1)
        best = best.map(lambda im: im.set("capture", im.date().format("YYYY-MM-dd")))
        selected = ee.Dictionary({
            "scenes": best.aggregate_array("system:index"),
            "dates": best.aggregate_array("capture"),
            "fractions": best.aggregate_array("local_clear_fraction"),
        }).getInfo()
        if not selected["scenes"]:
            gaps.append(dict(window, kind=kind, reason="no acquisition met the local clear-pixel threshold"))
            continue
        scene = selected["scenes"][0]
        capture = selected["dates"][0]
        fraction = selected["fractions"][0]
        if not re.fullmatch(r"[A-Za-z0-9_]+", scene):
            raise ValueError(f"Unexpected Earth Engine scene ID: {scene!r}")
        name = f"weekly-{site}-{scene}.png"
        target = ROOT / name
        if not target.exists() or target.stat().st_size == 0:
            rgb = clear_image(ee, ee.Image(f"{COLLECTION}/{scene}"))
            url = rgb.getThumbURL({
                "region": bounds, "crs": "EPSG:32640", "dimensions": f"{SIZE}x{SIZE}",
                "min": 0, "max": 3500, "format": "png",
            })
            with urlopen(url, timeout=60) as response:
                content = response.read()
            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError(f"Unexpected image response for {scene}")
            target.with_suffix(".png.part").write_bytes(content)
            target.with_suffix(".png.part").replace(target)
        frames.append(dict(window, kind=kind, date=capture, source=SOURCE,
                           resolution_m=10, scene=scene, file=name, clear_fraction=fraction))
        print(f"{site} {capture} {fraction:.0%} clear", flush=True)

    manifest = {
        "site": site, "collection": COLLECTION, "project_number": project_number,
        "registry_start": registry_start.isoformat() if registry_start else None,
        "observation_start": start.isoformat(), "through": through.isoformat(),
        "width": SIZE, "height": SIZE, "minimum_local_clear_fraction": MIN_CLEAR,
        "frames": frames, "gaps": gaps,
    }
    path = ROOT / f"weekly-{site}.json"
    path.with_suffix(".json.part").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    path.with_suffix(".json.part").replace(path)
    print(f"{len(frames)} captures and {len(gaps)} gaps in {path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", choices=SITES)
    parser.add_argument("--project", required=True, help="Authorised Google Cloud project for Earth Engine")
    parser.add_argument("--through", type=date.fromisoformat, default=date.today())
    parser.add_argument("--from", dest="start", type=date.fromisoformat,
                        help="Observation window start for a site without a matched DLD record")
    args = parser.parse_args()
    project_number = SITES[args.site]["project"]
    rows = load_json(REGISTRY)["projects"]
    record = next((r for r in rows if str(r["number"]) == project_number), {})
    value = record.get("start")
    registry_start = date.fromisoformat(value) if value else None
    if registry_start and args.start:
        parser.error("--from is only for sites without a registry start")
    start = registry_start or args.start
    if not start:
        parser.error("No matched registry start. Supply --from to export an observation window.")
    if start > args.through:
        parser.error("Start follows the export cutoff")
    try:
        import ee
    except ImportError:
        parser.exit(1, "Install earthengine-api in an authorised Python environment before exporting.\n")
    try:
        ee.Initialize(project=args.project)
    except ee.EEException as exc:
        parser.exit(1, f"Earth Engine initialisation failed. Authenticate the authorised account first. ({exc})\n")
    export_site(ee, args.site, start, args.through, registry_start, project_number)


if __name__ == "__main__":
    main()
