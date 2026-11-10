"""Build demo.html from demo-template.html and the cached evidence files.

Usage:  python build_demo.py            (writes demo.html)
        python build_demo.py --out x.html

Standard library only. Paths are relative to this folder. The script fails loudly if
any input is missing, empty or misaligned, rather than producing a half-working demo.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SITES = {
    "exploratory": {
        "coordinates": [55.14615, 25.033904],
        "project": None,
        "radar": "radar-exploratory-2026-10-28.json",
        "optical": "optical-monthly-exploratory-2026-10-28.json",
    },
    "verdes": {
        "coordinates": [55.3758125, 25.0798125],
        "project": "3189",
        "radar": "radar-verdes-candidate-2026-10-28.json",
        "optical": "optical-monthly-verdes-2026-10-28.json",
    },
    "orchid": {
        "coordinates": [55.1495641, 25.0318869],
        "project": "1513",
        "radar": "radar-orchid-control-candidate-2026-10-28.json",
        "optical": "optical-monthly-orchid-2026-10-28.json",
    },
    "village": {
        "coordinates": [55.117054, 25.034937],
        "project": None,
        "optical": "optical-village-sampled-2026-11-10.json",
    },
}
REGISTRY = "registry-evidence.json"
TIMELINE = "google-earth-timeline-manifest.json"
SITE_IMAGES = "wayback-sites-2026-11-10.json"
VISUAL_NOTES = "google-earth-visual-notes.json"  # optional; plain-language notes per frame
TEMPLATE = "demo-template.html"

# Frames are only shown if their provider was checked in Google Earth's
# "Data attribution" panel. The 2024-04-03 capture is also framed differently
# (wider viewport), so it stays out until it is re-captured and checked.
SKIP_UNVERIFIED_FRAMES = True


def load_json(name: str):
    path = ROOT / name
    if not path.is_file():
        raise SystemExit(f"Missing input: {name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data:
        raise SystemExit(f"Empty input: {name}")
    return data


def data_uri(name: str) -> str:
    path = ROOT / name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty image: {name}")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def months_of(collection: dict, name: str) -> list[str]:
    feats = collection.get("features") or []
    if not feats:
        raise SystemExit(f"No features in {name}")
    months = [f["properties"]["month"] for f in feats]
    if len(set(months)) != len(months):
        raise SystemExit(f"Duplicate months in {name}")
    return sorted(months)


def weekly_evidence(site, project, start):
    name = f"weekly-{site}.json"
    if not (ROOT / name).exists():
        return {"frames": [], "gaps": []}
    manifest = load_json(name)
    if (manifest["site"], manifest["project_number"], manifest["registry_start"]) != (site, project, start):
        raise SystemExit(f"Registry date or site mismatch in {name}")
    dates = []
    frames = []
    for frame in manifest["frames"]:
        capture = date.fromisoformat(frame["date"])
        first = date.fromisoformat(frame["window_start"])
        stop = date.fromisoformat(frame["window_end_exclusive"])
        filename = frame["file"]
        if not first <= capture < stop or not re.fullmatch(rf"weekly-{site}-[A-Za-z0-9_]+\.png", filename):
            raise SystemExit(f"Invalid capture or path in {name}: {filename}")
        if frame["resolution_m"] != 10 or frame["clear_fraction"] < manifest["minimum_local_clear_fraction"]:
            raise SystemExit(f"Invalid resolution or clear coverage in {name}")
        dates.append(capture)
        frames.append(dict(frame, image=data_uri(filename)))
    if dates != sorted(set(dates)):
        raise SystemExit(f"Duplicate or out-of-order dates in {name}")
    return {"frames": frames, "gaps": manifest["gaps"], "through": manifest["through"]}


def month_range(first, last):
    year, month = map(int, first.split("-"))
    while (key := f"{year:04d}-{month:02d}") <= last:
        yield key
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="demo.html")
    parser.add_argument("--with-local-imagery", action="store_true", help="Include authorised local archive assets")
    args = parser.parse_args()

    radar, optical = {}, {}
    reference_months = None
    for site, files in SITES.items():
        if site == "village":
            radar[site] = {"features": []}
            optical[site] = load_json(files["optical"])
            if not set(months_of(optical[site], site)).issubset(reference_months):
                raise SystemExit("Villa observations fall outside the shared timeline")
            continue
        radar[site] = load_json(files["radar"])
        optical[site] = load_json(files["optical"])
        for kind, coll, fname in (("radar", radar[site], files["radar"]), ("optical", optical[site], files["optical"])):
            m = months_of(coll, fname)
            if reference_months is None:
                reference_months = m
            elif m != reference_months:
                raise SystemExit(f"Month mismatch in {fname}: {m[0]}..{m[-1]} ({len(m)}) vs reference")

    registry = load_json(REGISTRY)
    if not registry.get("projects"):
        raise SystemExit("Registry has no projects")

    records = {str(record["number"]): record for record in registry["projects"]}
    mapping = {}
    site_images = load_json(SITE_IMAGES) if args.with_local_imagery else {site: [] for site in SITES}
    if set(site_images) != set(SITES):
        raise SystemExit("Imagery manifest does not match the configured sites")
    for site, config in SITES.items():
        project = config["project"]
        if project is not None and project not in records:
            raise SystemExit(f"Missing registry project {project} for {site}")
        frames = sorted(
            (frame for frame in site_images[site] if frame["date"]),
            key=lambda frame: frame["date"],
        )
        dates = [frame["date"] for frame in frames]
        if (args.with_local_imagery and len(dates) < 2) or len(dates) != len(set(dates)):
            raise SystemExit(f"Missing or duplicate acquisition dates for {site}")
        start = records.get(project, {}).get("start") or None
        mapping[site] = {
            "coordinates": config["coordinates"],
            "outer_radius_m": 60,
            "inset_m": 10,
            "project": project,
            "registry_start": start,
            "frames": [dict(frame, image=data_uri(frame["file"])) for frame in frames],
            "weekly": weekly_evidence(site, project, start),
        }
    village = load_json("village-project-wayback-2026-11-10.json")
    window = (village["start"], village["end"])
    village_frames = village["frames"] if args.with_local_imagery else []
    dates = [frame["date"] for frame in village_frames]
    if (village["site"] != "village" or (args.with_local_imagery and not dates) or dates != sorted(set(dates))
            or any(not window[0] <= d <= window[1] for d in dates)):
        raise SystemExit("Invalid Jebel Ali Village project-window imagery")
    mapping["village"]["frames"] = [dict(frame, image=data_uri(frame["file"])) for frame in village_frames]
    mapping["village"]["window"] = list(window)

    manifest = load_json(TIMELINE) if args.with_local_imagery else {"frames": []}
    notes = {}
    if (ROOT / VISUAL_NOTES).is_file():
        notes = load_json(VISUAL_NOTES).get("notes", {})
    history, skipped = [], []
    for frame in manifest["frames"]:
        if SKIP_UNVERIFIED_FRAMES and "UNVERIFIED" in frame["provider"].upper():
            skipped.append(frame["date"])
            continue
        history.append({
            "date": frame["date"],
            "provider": frame["provider"],
            "url": frame["url"],
            "note": notes.get(frame["date"], ""),
            "image": data_uri(frame["file"]),
        })
    if args.with_local_imagery and not history:
        raise SystemExit("No Google Earth frames to show")
    history.sort(key=lambda f: f["date"])

    imagery_months = [f["date"][:7] for f in history]
    for item in mapping.values():
        imagery_months.extend(f["date"][:7] for f in item["frames"] + item["weekly"]["frames"])
        if item["weekly"].get("through"):
            imagery_months.append(item["weekly"]["through"][:7])
    all_months = reference_months + imagery_months
    payload = {
        "months": list(month_range(min(all_months), max(all_months))),
        "registry": registry,
        "mapping": mapping,
        "radar": radar,
        "optical": optical,
        "history": history,
    }

    template = (ROOT / TEMPLATE).read_text(encoding="utf-8")
    if template.count("@@DATA@@") != 1:
        raise SystemExit("Template must contain exactly one @@DATA@@ placeholder")
    # Escape "</" so the JSON cannot close the <script> tag early.
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = ROOT / args.out
    out.write_text(template.replace("@@DATA@@", blob), encoding="utf-8")

    print(f"Wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"Months: {reference_months[0]} to {reference_months[-1]} ({len(reference_months)})")
    print(f"Google Earth frames: {', '.join(f['date'] for f in history)}")
    if skipped:
        print(f"Skipped (provider not verified): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
