"""Index distinct dated Wayback views without downloading imagery tiles."""
import concurrent.futures
import datetime
import json
import re
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from build_demo import SITES

ROOT = Path(__file__).resolve().parent
CENTRES = {key: value["coordinates"] for key, value in SITES.items()}
CENTRES.update(mall=[55.23968, 25.1016], como=[55.14543, 25.11116],
               naya=[55.287229, 25.157254], frond=[55.000749, 25.018663])
LOCATION_SOURCES = {
    "mall": "https://www.openstreetmap.org/way/797700047",
    "como": "https://www.openstreetmap.org/way/656917025",
    "naya": "https://www.madena.ae/projects/naya",
    "frond": "https://offplan.ae/projects/palm-jebel-ali-villas-frond-f",
}
LAYERS = {4: 19, 5: 17, 6: 17, 7: 16, 8: 15}


def inspect(job):
    site, release_id, release = job
    lon, lat = CENTRES[site]
    params = urlencode({
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
        "sr": 4326, "layers": "all:4,5,6,7,8", "tolerance": 0,
        "mapExtent": f"{lon-.015},{lat-.015},{lon+.015},{lat+.015}",
        "imageDisplay": "512,512,96", "returnGeometry": "false", "f": "json",
    })
    url = release["metadataLayerUrl"] + "/identify?" + params
    for _ in range(2):
        try:
            with urlopen(url, timeout=8) as response:
                payload = json.load(response)
            hits = payload["results"]
            break
        except (OSError, ValueError, KeyError):
            continue
    else:
        return site, None
    frames = []
    release_date = release["itemTitle"][-11:-1]
    for hit in hits:
        attrs = hit["attributes"]
        raw = attrs.get("SRC_DATE", "")
        if not re.fullmatch(r"\d{8}", raw):
            continue
        try:
            date = datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:])).isoformat()
            zoom = LAYERS[hit["layerId"]]
        except (ValueError, KeyError):
            continue
        if date > release_date:
            continue
        frames.append({
            "date": date, "release": release_date, "zoom": zoom,
            "provider": attrs.get("NICE_DESC") or attrs.get("SRC_DESC"),
            "resolution": attrs.get("SRC_RES"), "metadata": url,
            "url": "https://livingatlas.arcgis.com/wayback/#" + urlencode({
                "active": release_id, "mapCenter": f"{lon},{lat},{zoom}",
            }),
        })
    return site, frames


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    releases = {v["metadataLayerUrl"]: (key, v) for key, v in config.items()}
    stride = int(os.environ.get("MILESTONE_ARCHIVE_STRIDE", "1"))
    index = {key: {"centre": point, "locationSource": LOCATION_SOURCES.get(key),
                   "failures": 0, "checked": 0, "captures": {}}
             for key, point in CENTRES.items()}
    if len(sys.argv) > 2:
        index = {site: index[site] for site in sys.argv[2:]}
    jobs = [(site, key, release) for key, release in list(releases.values())[::stride] for site in index]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(inspect, job) for job in jobs]
        for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
            site, frames = future.result()
            item = index[site]
            item["checked"] += 1
            if completed % 50 == 0:
                print(f"Checked {completed}/{len(jobs)} location/release pairs", flush=True)
            if frames is None:
                item["failures"] += 1
                continue
            for frame in frames:
                old = item["captures"].get(frame["date"])
                if not old or (frame["zoom"], frame["release"]) > (old["zoom"], old["release"]):
                    item["captures"][frame["date"]] = frame
    for site, item in index.items():
        item["captures"] = sorted(item["captures"].values(), key=lambda frame: frame["date"])
        print(site, item["checked"], item["failures"], len(item["captures"]))
    filename = "wayback-capture-index-2026-11-15"
    if len(sys.argv) > 2:
        filename += "-" + "-".join(index)
    if stride > 1:
        filename += f"-stride-{stride}"
    (ROOT / (filename + ".json")).write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
