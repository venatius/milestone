"""Measure BSI and visible brightness for the existing Village optical scenes."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('panel', ROOT / 'sample-panel-sentinel.py')
panel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(panel)


def measure(row):
    keys = ['B02', 'B03', 'B04', 'B08', 'B11']
    blue, green, red, nir, swir, scl = panel.bands(
        row['bbox'], 'sentinel-2-l2a', row['scene'], [*keys, 'SCL'])
    metadata = panel.get('/stac/v1/collections/sentinel-2-l2a/items/' + row['scene']).json()
    baseline = float(metadata['properties']['s2:processing_baseline'])
    bands = [blue, green, red, nir, swir]
    reflectance = []
    for key, samples in zip(keys, bands):
        offset = metadata['assets'][key].get('raster:bands', [{}])[0].get('offset')
        if offset is None:
            offset = -0.1 if baseline >= 4 else 0
        if offset == -1000:
            offset = -0.1
        if offset not in (0, -0.1):
            raise ValueError(f'Unexpected reflectance offset for {key}: {offset}')
        reflectance.append(samples / 10000 + offset)
    b, g, r, n, s = reflectance
    clear = np.isin(scl, [4, 5, 6, 7])
    denominator = s + r + n + b
    soil_mask = clear & (blue > 0) & (red > 0) & (nir > 0) & (swir > 0) & (denominator > 0)
    bsi = ((s + r - n - b)[soil_mask] / denominator[soil_mask])
    bsi = bsi[np.abs(bsi) <= 1]
    visible_mask = clear & (blue > 0) & (green > 0) & (red > 0)
    brightness = ((b + g + r) / 3)[visible_mask]
    return {**row, 'BSI_mean': float(bsi.mean()) if bsi.size >= 30 else None,
            'brightness_mean': float(brightness.mean()) if brightness.size >= 30 else None}


if __name__ == '__main__':
    village = json.loads((ROOT / 'sentinel-village-monthly-2026-11-16.json').read_text())['sites']['village']
    original = village['optical']
    with ThreadPoolExecutor(max_workers=12) as pool:
        village['optical'] = list(pool.map(measure, original))
    for key in ('BSI_mean', 'brightness_mean'):
        count = sum(row[key] is not None for row in village['optical'])
        if not count:
            raise ValueError(f'No valid observations for {key}')
        print(f'{key}: {count}/{len(original)} scenes', flush=True)
    out = ROOT / 'sentinel-village-monthly-2026-11-20.json'
    out.write_text(json.dumps({'sites': {'village': village}}, allow_nan=False, indent=2), encoding='utf-8')
